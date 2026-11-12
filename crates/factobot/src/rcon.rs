//! Minimal Source RCON client for Factorio.
//!
//! Factorio answers each command with exactly one response packet, however
//! large the body (a 300 KB `rcon.print` arrives as one packet). It does not
//! echo the empty "end of response" marker some RCON servers support, so a
//! response is matched to its request by packet id alone.
//!
//! A timeout before any response byte leaves the stream framed, and a late
//! reply is skipped by packet id. A timeout after a byte has been read, or
//! any I/O error, makes the stream unusable: the next command opens a new
//! connection instead of parsing the rest of that packet as a new header.

use std::time::Duration;

use thiserror::Error;
#[cfg(test)]
use tokio::io::AsyncRead;
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::net::TcpStream;

const TYPE_AUTH: i32 = 3;
const TYPE_EXEC_COMMAND: i32 = 2;
const TYPE_AUTH_RESPONSE: i32 = 2;
const TYPE_RESPONSE_VALUE: i32 = 0;
/// Factorio's own cap is far larger than any sane response; this only stops a
/// corrupt length prefix from allocating gigabytes.
const MAX_PACKET_LEN: usize = 64 * 1024 * 1024;

#[derive(Debug, Error)]
pub enum RconError {
    #[error("rcon i/o: {0}")]
    Io(#[from] std::io::Error),
    #[error("rcon authentication rejected")]
    AuthRejected,
    #[error("rcon protocol violation: {0}")]
    Protocol(String),
    #[error("rcon timed out after {0:?}")]
    Timeout(Duration),
}

#[derive(Debug, PartialEq, Eq)]
struct Packet {
    id: i32,
    kind: i32,
    body: String,
}

fn encode(id: i32, kind: i32, body: &str) -> Vec<u8> {
    let len = 4 + 4 + body.len() + 2;
    let mut buf = Vec::with_capacity(4 + len);
    buf.extend_from_slice(&i32::try_from(len).unwrap_or(i32::MAX).to_le_bytes());
    buf.extend_from_slice(&id.to_le_bytes());
    buf.extend_from_slice(&kind.to_le_bytes());
    buf.extend_from_slice(body.as_bytes());
    buf.extend_from_slice(&[0, 0]);
    buf
}

#[cfg(test)]
async fn read_packet<R: AsyncRead + Unpin>(reader: &mut R) -> Result<Packet, RconError> {
    let len = reader.read_i32_le().await?;
    let len = usize::try_from(len)
        .ok()
        .filter(|len| (10..=MAX_PACKET_LEN).contains(len))
        .ok_or_else(|| RconError::Protocol(format!("bad packet length {len}")))?;
    let mut payload = vec![0u8; len];
    reader.read_exact(&mut payload).await?;
    decode_packet(&payload)
}

pub struct Rcon {
    stream: TcpStream,
    next_id: i32,
    timeout: Duration,
    addr: String,
    password: String,
    /// The stream has lost packet framing. The next `exec` connects again.
    broken: bool,
}

impl Rcon {
    pub async fn connect(addr: &str, password: &str, timeout: Duration) -> Result<Self, RconError> {
        let stream = connect_stream(addr, timeout).await?;
        let mut rcon = Self {
            stream,
            next_id: 1,
            timeout,
            addr: addr.to_owned(),
            password: password.to_owned(),
            broken: false,
        };
        rcon.authenticate().await?;
        Ok(rcon)
    }

    /// Run one console command and return what it printed via `rcon.print`.
    pub async fn exec(&mut self, command: &str) -> Result<String, RconError> {
        if self.broken {
            self.reconnect().await?;
        }
        let id = match self.send(TYPE_EXEC_COMMAND, command).await {
            Ok(id) => id,
            Err(err) => {
                self.broken = true;
                return Err(err);
            }
        };
        loop {
            let reply = self.receive().await?;
            // A reply to an earlier command that timed out arrives late;
            // drop it rather than mistaking it for this command's answer.
            if reply.id < id {
                continue;
            }
            if reply.id != id || reply.kind != TYPE_RESPONSE_VALUE {
                return Err(RconError::Protocol(format!(
                    "response (id {}, type {}) does not match request {id}",
                    reply.id, reply.kind
                )));
            }
            return Ok(reply.body);
        }
    }

    async fn reconnect(&mut self) -> Result<(), RconError> {
        match connect_stream(&self.addr, self.timeout).await {
            Ok(stream) => {
                self.stream = stream;
                self.next_id = 1;
                self.broken = false;
            }
            Err(err) => {
                self.broken = true;
                return Err(err);
            }
        }
        self.authenticate().await
    }

    async fn authenticate(&mut self) -> Result<(), RconError> {
        let password = self.password.clone();
        let id = match self.send(TYPE_AUTH, &password).await {
            Ok(id) => id,
            Err(err) => {
                self.broken = true;
                return Err(err);
            }
        };
        let reply = self.receive().await?;
        if reply.kind != TYPE_AUTH_RESPONSE {
            self.broken = true;
            return Err(RconError::Protocol(format!(
                "expected auth response, got packet type {}",
                reply.kind
            )));
        }
        if reply.id == -1 {
            self.broken = true;
            return Err(RconError::AuthRejected);
        }
        if reply.id != id {
            self.broken = true;
            return Err(RconError::Protocol(format!(
                "auth response id {} does not match request {id}",
                reply.id
            )));
        }
        Ok(())
    }

    async fn send(&mut self, kind: i32, body: &str) -> Result<i32, RconError> {
        let id = self.next_id;
        self.next_id = self.next_id.checked_add(1).unwrap_or(1);
        if let Err(err) = self.stream.write_all(&encode(id, kind, body)).await {
            self.broken = true;
            return Err(err.into());
        }
        Ok(id)
    }

    /// Read one packet. The timeout applies while no byte of it has arrived.
    /// After the first byte the rest of the packet is read within the same
    /// budget; if that fails the stream is marked broken, because those bytes
    /// are already consumed and the next header would be misaligned.
    async fn receive(&mut self) -> Result<Packet, RconError> {
        if self.broken {
            return Err(RconError::Protocol(
                "rcon connection is unusable after a partial read".into(),
            ));
        }
        let mut len_buf = [0u8; 4];
        match tokio::time::timeout(self.timeout, self.stream.read(&mut len_buf[..1])).await {
            Ok(Ok(0)) => {
                self.broken = true;
                return Err(unexpected_eof());
            }
            Ok(Ok(_)) => {}
            Ok(Err(err)) => {
                self.broken = true;
                return Err(err.into());
            }
            // No byte consumed: the stream is still framed.
            Err(_) => return Err(RconError::Timeout(self.timeout)),
        }
        if let Err(err) = self.read_exact_within(&mut len_buf[1..]).await {
            self.broken = true;
            return Err(err);
        }
        let len = i32::from_le_bytes(len_buf);
        let Some(len) = usize::try_from(len)
            .ok()
            .filter(|len| (10..=MAX_PACKET_LEN).contains(len))
        else {
            self.broken = true;
            return Err(RconError::Protocol(format!("bad packet length {len}")));
        };
        let mut payload = vec![0u8; len];
        if let Err(err) = self.read_exact_within(&mut payload).await {
            self.broken = true;
            return Err(err);
        }
        decode_packet(&payload)
    }

    async fn read_exact_within(&mut self, buf: &mut [u8]) -> Result<(), RconError> {
        let deadline = tokio::time::Instant::now() + self.timeout;
        let mut filled = 0;
        while filled < buf.len() {
            let left = deadline.saturating_duration_since(tokio::time::Instant::now());
            if left.is_zero() {
                return Err(RconError::Timeout(self.timeout));
            }
            match tokio::time::timeout(left, self.stream.read(&mut buf[filled..])).await {
                Ok(Ok(0)) => return Err(unexpected_eof()),
                Ok(Ok(n)) => filled += n,
                Ok(Err(err)) => return Err(err.into()),
                Err(_) => return Err(RconError::Timeout(self.timeout)),
            }
        }
        Ok(())
    }
}

async fn connect_stream(addr: &str, timeout: Duration) -> Result<TcpStream, RconError> {
    let stream = tokio::time::timeout(timeout, TcpStream::connect(addr))
        .await
        .map_err(|_| RconError::Timeout(timeout))??;
    stream.set_nodelay(true)?;
    Ok(stream)
}

fn unexpected_eof() -> RconError {
    RconError::Io(std::io::Error::new(
        std::io::ErrorKind::UnexpectedEof,
        "rcon closed",
    ))
}

fn decode_packet(payload: &[u8]) -> Result<Packet, RconError> {
    if payload.len() < 10 {
        return Err(RconError::Protocol(format!(
            "packet shorter than a header ({})",
            payload.len()
        )));
    }
    let id = i32::from_le_bytes(payload[0..4].try_into().expect("4 bytes"));
    let kind = i32::from_le_bytes(payload[4..8].try_into().expect("4 bytes"));
    let body = std::str::from_utf8(&payload[8..payload.len() - 2])
        .map_err(|_| RconError::Protocol("response body is not UTF-8".into()))?
        .to_owned();
    Ok(Packet { id, kind, body })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn reads_a_large_packet_split_across_reads() {
        let body = "x".repeat(300_000);
        let wire = encode(7, TYPE_RESPONSE_VALUE, &body);
        let (mut tx, mut rx) = tokio::io::duplex(4096);
        let writer = tokio::spawn(async move {
            for chunk in wire.chunks(1000) {
                tx.write_all(chunk).await.unwrap();
            }
        });
        let packet = read_packet(&mut rx).await.unwrap();
        writer.await.unwrap();
        assert_eq!(packet.id, 7);
        assert_eq!(packet.body.len(), 300_000);
    }

    #[tokio::test]
    async fn rejects_a_corrupt_length_prefix() {
        let mut wire = encode(1, TYPE_RESPONSE_VALUE, "ok");
        wire[0..4].copy_from_slice(&(-5i32).to_le_bytes());
        let err = read_packet(&mut wire.as_slice()).await.unwrap_err();
        assert!(matches!(err, RconError::Protocol(_)), "{err}");
    }

    /// Speaks just enough RCON for `connect` and `exec`: one command per connection.
    async fn serve_one(
        sock: &mut tokio::net::TcpStream,
        reply: impl AsyncFnOnce(Packet, &mut tokio::net::TcpStream),
    ) {
        let auth = read_packet(sock).await.unwrap();
        assert_eq!(auth.kind, TYPE_AUTH);
        sock.write_all(&encode(auth.id, TYPE_AUTH_RESPONSE, ""))
            .await
            .unwrap();
        let command = read_packet(sock).await.unwrap();
        reply(command, sock).await;
    }

    fn listen() -> (tokio::net::TcpListener, String) {
        let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
        listener.set_nonblocking(true).unwrap();
        let addr = listener.local_addr().unwrap().to_string();
        (tokio::net::TcpListener::from_std(listener).unwrap(), addr)
    }

    #[tokio::test]
    async fn a_timeout_mid_packet_reconnects_for_the_next_command() {
        let (listener, addr) = listen();
        let server = tokio::spawn(async move {
            let (mut sock, _) = listener.accept().await.unwrap();
            let partial = tokio::spawn(async move {
                serve_one(
                    &mut sock,
                    async |command, sock: &mut tokio::net::TcpStream| {
                        let packet = encode(command.id, TYPE_RESPONSE_VALUE, "cut-off");
                        sock.write_all(&packet[..2]).await.unwrap();
                        // Stay quiet so the client gives up mid-frame.
                        tokio::time::sleep(Duration::from_secs(5)).await;
                    },
                )
                .await;
            });

            let (mut sock, _) = listener.accept().await.unwrap();
            serve_one(
                &mut sock,
                async |command, sock: &mut tokio::net::TcpStream| {
                    assert_eq!(command.body, "next");
                    sock.write_all(&encode(command.id, TYPE_RESPONSE_VALUE, "ok"))
                        .await
                        .unwrap();
                },
            )
            .await;
            partial.abort();
        });

        let timeout = Duration::from_millis(1000);
        let mut rcon = Rcon::connect(&addr, "pw", timeout).await.unwrap();
        let err = rcon.exec("partial").await.unwrap_err();
        assert!(
            matches!(err, RconError::Timeout(got) if got == timeout),
            "{err}"
        );
        assert_eq!(rcon.exec("next").await.unwrap(), "ok");
        server.await.unwrap();
    }
}
