//! Daemon socket protocol, version 3.
//!
//! Newline-delimited JSON over a Unix socket. Every client (the `fac` CLI, the
//! Python package; an MCP server later) speaks this protocol; `docs/protocol.md`
//! is the human-readable spec and must change with this file.

use serde::{Deserialize, Serialize};
use serde_json::Value;

pub const PROTOCOL_VERSION: u32 = 3;

/// The field of a `screen` result that holds the screenshot as base64 PNG
/// data. The daemon's call log keeps its length in place of the data.
pub const PNG_FIELD: &str = "png_base64";

/// Longest `timeout`, in seconds, that the `wait` method accepts.
pub const WAIT_MAX_S: f64 = 600.0;

/// The `bad_request` error for a `wait` timeout outside 0 to `WAIT_MAX_S`
/// seconds. `fac` checks it before starting a job it would wait on, so an
/// over-long `--wait` is refused before the job takes anything.
pub fn wait_timeout_error(timeout: f64) -> Option<ErrorBody> {
    (!(0.0..=WAIT_MAX_S).contains(&timeout)).then(|| ErrorBody {
        code: ErrorCode::BadRequest,
        message: format!("timeout must be 0 to {WAIT_MAX_S} seconds"),
    })
}

#[derive(Debug, Serialize, Deserialize)]
pub struct Request {
    pub v: u32,
    pub id: u64,
    pub method: String,
    #[serde(default)]
    pub params: Value,
}

/// `ok` is true with `result` set, or false with `error` set. An answer to
/// an agent method that reached the game also has `hud`, what a player's
/// screen always shows: `time` (the game clock, h:mm:ss), `free_slots` in
/// the inventory, `research` (`"logistics 43%"` or `"none"`) and, when there
/// are any, `warnings`.
#[derive(Debug, Serialize, Deserialize)]
pub struct Response {
    pub v: u32,
    pub id: u64,
    pub ok: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub result: Option<Value>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub error: Option<ErrorBody>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub hud: Option<Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ErrorBody {
    pub code: ErrorCode,
    pub message: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ErrorCode {
    /// The request was not valid protocol JSON or used another version.
    BadRequest,
    UnknownMethod,
    /// The game or the factobot mod failed to run the call.
    GameError,
    /// The game's rules forbid the action: out of reach, recipe locked,
    /// missing ingredients, nothing to mine. The message says why.
    Rejected,
    /// The daemon could not reach the game.
    Unavailable,
}

impl Response {
    pub fn ok(id: u64, result: Value) -> Self {
        Self {
            v: PROTOCOL_VERSION,
            id,
            ok: true,
            result: Some(result),
            error: None,
            hud: None,
        }
    }

    pub fn err(id: u64, code: ErrorCode, message: impl Into<String>) -> Self {
        Self {
            v: PROTOCOL_VERSION,
            id,
            ok: false,
            result: None,
            error: Some(ErrorBody {
                code,
                message: message.into(),
            }),
            hud: None,
        }
    }

    #[must_use]
    pub fn with_hud(mut self, hud: Option<Value>) -> Self {
        self.hud = hud;
        self
    }
}
