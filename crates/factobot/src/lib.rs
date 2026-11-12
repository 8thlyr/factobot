//! What the harness's `fac` and the agent's `fac-agent` share: the agent
//! commands, the client that sends them and the protocol they speak.

pub mod agent;
pub mod client;
pub mod protocol;

/// Log to stderr, filtered by `FACTOBOT_LOG`. Both binaries call this first.
pub fn init_tracing() {
    tracing_subscriber::fmt()
        .with_env_filter(tracing_subscriber::EnvFilter::from_env("FACTOBOT_LOG"))
        .with_writer(std::io::stderr)
        .init();
}
