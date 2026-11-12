//! The agent's `fac`: the agent commands and nothing else. The playtest
//! sandbox mounts this binary as `fac`, so an agent holds no code that runs a
//! daemon or reaches the dev socket (decision 64).

use std::process::ExitCode;

use clap::Parser;
use factobot::agent;

#[tokio::main]
async fn main() -> ExitCode {
    factobot::init_tracing();
    agent::run(agent::Cli::parse()).await
}
