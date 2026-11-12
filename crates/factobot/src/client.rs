//! Socket client used by the `fac` agent commands.

use std::path::Path;
use std::time::Duration;

use anyhow::{Context, Result, bail};
use serde_json::Value;
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::net::UnixStream;
use tokio::time::timeout;

use crate::protocol::{PROTOCOL_VERSION, Request, Response};

/// How long connect, write and read may take together.
///
/// `--wait` runs for up to `protocol::WAIT_MAX_S` (600 s). A minute past that
/// is the 660 s a playtest harness gives each shell call, so a wait that runs
/// to its limit can still come back as a reply instead of a killed command.
const CALL_DEADLINE: Duration = Duration::from_secs(660);

pub async fn call(socket: &Path, method: &str, params: Value) -> Result<Response> {
    call_with_deadline(socket, method, params, CALL_DEADLINE).await
}

async fn call_with_deadline(
    socket: &Path,
    method: &str,
    params: Value,
    deadline: Duration,
) -> Result<Response> {
    match timeout(deadline, exchange(socket, method, params)).await {
        Ok(response) => response,
        Err(_) => bail!(
            "no reply from the world at {} after {} seconds",
            socket.display(),
            deadline.as_secs_f64()
        ),
    }
}

/// Connect, write one request and read one response. No deadline of its own:
/// `call_with_deadline` bounds the three steps together.
async fn exchange(socket: &Path, method: &str, params: Value) -> Result<Response> {
    // `fac-agent` has no `daemon` subcommand, so this must not tell the agent
    // to run one. The world is down, or FACTOBOT_SOCKET points at the wrong place.
    let stream = UnixStream::connect(socket).await.with_context(|| {
        format!(
            "no world is answering at {}; check FACTOBOT_SOCKET",
            socket.display()
        )
    })?;
    let (read, mut write) = stream.into_split();
    let request = Request {
        v: PROTOCOL_VERSION,
        id: 1,
        method: method.to_owned(),
        params,
    };
    let mut line = serde_json::to_vec(&request)?;
    line.push(b'\n');
    write.write_all(&line).await?;

    let mut reply = String::new();
    if BufReader::new(read).read_line(&mut reply).await? == 0 {
        bail!("daemon closed the connection without replying");
    }
    serde_json::from_str(&reply).context("daemon sent an invalid response")
}

#[cfg(test)]
mod tests {
    use std::time::{Duration, Instant};

    use serde_json::json;
    use tokio::net::UnixListener;

    use super::call_with_deadline;

    #[tokio::test]
    async fn silent_daemon_fails_within_the_deadline() {
        let dir = tempfile::tempdir().unwrap();
        let socket = dir.path().join("fac.sock");
        let listener = UnixListener::bind(&socket).unwrap();
        tokio::spawn(async move {
            // Accept and hold the connection. Dropping it would look like a
            // closed daemon, which fails at once instead of at the deadline.
            let (stream, _) = listener.accept().await.unwrap();
            std::future::pending::<()>().await;
            drop(stream);
        });

        let deadline = Duration::from_millis(100);
        let started = Instant::now();
        let result = tokio::time::timeout(
            Duration::from_secs(5),
            call_with_deadline(&socket, "status", json!({}), deadline),
        )
        .await;
        let elapsed = started.elapsed();
        let err = result
            .expect("call did not return within the test deadline")
            .expect_err("a silent daemon should fail");
        assert!(
            elapsed >= Duration::from_millis(75),
            "returned in {elapsed:?}, before the deadline"
        );

        let message = format!("{err:#}");
        assert!(message.contains(&socket.display().to_string()), "{message}");
        assert!(message.contains("0.1"), "{message}");
        assert!(message.contains("seconds"), "{message}");
    }
}
