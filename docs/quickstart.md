# Quickstart

Run a factobot benchmark: a real Factorio world, an agent that can only play through `fac`, and a `summary.json` when it stops. The smoke task below is the short one. It boots a fresh map, asks the agent for the game tick and the Factorio version, and writes the same summary a long run writes. Once the setup on this page has finished, that run completes in under 5 minutes. Downloading the game and compiling `fac` the first time take longer.

Red science, the scored stage, is the same runner with a different task. It takes hours. The command is [below](#red-science).

## Setup

You need Linux. The headless server build is the Linux 64-bit build pinned in `mise.toml`.

Install [mise](https://mise.jdx.dev), then the sandbox tools. The runner looks for these exact paths: `/usr/bin/bwrap`, `/usr/bin/slirp4netns`, `/usr/bin/nsenter`, and `/usr/bin/ip`. Package names on Arch and on Debian or Ubuntu:

```bash
# Arch
sudo pacman -S --needed bubblewrap slirp4netns util-linux iproute2
# Debian or Ubuntu
sudo apt-get install bubblewrap slirp4netns util-linux iproute2
```

The smoke script below is `/usr/bin/python3` on purpose. The sandbox runs a program that lives under `/usr` from the host's `/usr`. A Python from anywhere else is copied in as a single file and will not start. Any Python 3 there is enough. The runner itself uses the Python from mise and uv.

From a fresh checkout:

```bash
mise trust
mise install
mise exec -- uv sync --project python --locked
mise run fetch-factorio
```

`mise install` puts the pinned Rust, uv, and the other tools in place. `mise run fetch-factorio` downloads the free headless server into `~/.cache/factobot/factorio/<version>` and checks the checksum in `mise.toml`. No Factorio account is required for this. Re-running it does nothing if that directory is already there.

Compile `fac` once. `mise run playtest` compiles again, and a second build is incremental:

```bash
mise exec -- cargo build --locked
```

## Smoke benchmark

This command is the whole run. `playtests/smoke.md` is the task. Everything after the second `--` is the agent. `{prompt}` is required: the runner replaces that argument with the task text. This script ignores the text, calls `fac status`, and prints the one line the task asks for.

```bash
mise run playtest -- playtests/smoke.md --timeout 180 -- \
  /usr/bin/python3 -c 'import json,subprocess; s=json.loads(subprocess.check_output(["fac","status"])); g=s["result"]["game"]; print(json.dumps({"tick":g["tick"],"version":g["game_version"]}))' \
  {prompt}
```

`--timeout` is seconds of the agent's own run, counted after the world has booted. The default is 1800. `0` stops the agent as soon as it starts. There is no unlimited value. A long run uses a large count such as `999999999`.

The runner prints the summary on stdout and writes it to `target/playtests/smoke-<YYYYMMDD-HHMMSS>-<random>/summary.json`. The process exits 0 when the agent process exits 0. This task has no milestone, so a successful script is a successful run.

What the agent can call is `fac --help`. Positions are map tiles as `X,Y` (x east, y south). A few that the help itself uses:

```bash
fac status
fac observe
fac walk 12,-30 --wait
fac craft iron-gear-wheel --count 4
fac place stone-furnace 3,4
```

A refusal is still one JSON object, with `ok` false and `error.code` of `rejected`. The message says which rule failed. For a hand craft that asks for more than the inventory can cover, it names how many you can craft and what one craft needs. `fac` exits non-zero in that case.

## Results

The run directory:

| Path | Contents |
|---|---|
| `summary.json` | The result. Same object the runner printed |
| `transcript.jsonl` | The agent's stdout. For the smoke script, the `{"tick", "version"}` line |
| `started` | Touched when the run begins |
| `world/calls.jsonl` | One JSON line per daemon call |
| `world/server.log` | Factorio's log |
| `world/daemon.log` | The daemon's log |
| `world/save.zip` | Written when the server quits |

`calls.jsonl` fields are `unix_ms`, `duration_ms`, `surface` (`agent` or `dev`), `tick`, `method`, `params`, and `response`. A screenshot response logs the PNG length instead of the image.

`docs/run-record.md` lists every `summary.json` field, its type and when it is null.

A smoke summary from the script above has `until` and `milestone_tick` null, `turns` and `cost_usd` null, and `methods` of `["status"]`.

### Score

For red science, take the ticks from the summary:

```text
stage_ticks = milestone_tick - start_tick
```

The reference is 5 hours. At 60 ticks a second that is 1,080,000 ticks. If `stage_ticks` is within twice that (2,160,000 ticks, 10 hours), the score is `1080000 / stage_ticks`. Above 1.00 is faster than the reference. If the milestone is missing, or later than that cap, the score is 0.25. The runner records the ticks, and `mise run report` applies the ratio to every run under `target/playtests` (`docs/development.md`, Leaderboard). `--timeout` is a wall-clock limit on the agent. At game speed 1, 36000 seconds is the same 10 hour budget. The score still uses ticks.

`packs` is how you see why a milestone did or did not fire. `made_by_machine` for `automation-science-pack` counts only after you subtract what the agent crafted by hand. `milestone_tick` is the tick labs had used more packs than were ever hand-crafted.

## A model instead of the script

The default harness is Claude Code. It needs a login already on the machine (`~/.claude/.credentials.json`, the `claudeAiOauth` entry). `--model` is the name Claude Code uses:

```bash
mise run playtest -- playtests/smoke.md --model sonnet
```

`sonnet` is the default when `--model` is omitted. The summary's `final_answer` is Claude Code's result text, and `turns` and `cost_usd` come from its report.

Any other program goes after `--`. `{prompt}` must appear in one of its arguments. `--env NAME` passes a host environment variable into the sandbox (an API key). `--expose PATH` mounts a host path read-only at the same path. Both apply only to a custom command:

```bash
mise run playtest -- playtests/smoke.md --env MY_API_KEY -- \
  my-agent --print {prompt}
```

omp is the other built-in preset (`--agent omp`). It needs `OMP_AUTH_BROKER_URL` in the environment, a token file at `~/.omp/auth-broker.token`, and `/usr/bin/nft` (nftables). Name the model in full (`claude-opus-5-5`). A short name is matched fuzzily and can pick a different model. Its `turns` and `cost_usd` stay null. `final_answer` is its last assistant message.

Other tasks in `playtests/` use the same command with a different file: `gather-and-craft.md`, `build-a-smelter.md`, `power-and-research.md`. A `.lua` file next to a task, if one exists, runs in the world before the agent starts.

## Red science

Scored stage, one seed, fresh map, game speed 1. The agent plays until labs research with a machine-made automation science pack, or until 36000 seconds (10 hours) after the world has booted. The exit status is 0 only when `milestone_tick` is set.

```bash
mise run playtest -- playtests/red-science.md --model opus \
  --seed 1 --until automation-science-pack --timeout 36000
```

`--seed` defaults to 1. One invocation is one seed. Repeat the command with another seed for a second sample. With `--until`, an agent that quits early is resumed in the same conversation, up to 10 times (`--max-resumes`).

The stage time and the score are the formula in [Score](#score). Five seeds and the median are the benchmark's intended report. This command runs one of them.

An Inspect AI task for the same stage is also in the Python package. It runs seeds 1 to 5, and its scorer writes the ratio. It is optional. The playtest command above is the benchmark run.

```bash
mise exec -- uv run --project python --extra anthropic \
  inspect eval factobot/red_science \
  --model anthropic/<model> \
  -M max_retries=0 \
  -T 'seeds=[1]'
```

`--extra anthropic` and `--extra openai` install the provider SDK for `anthropic/...` and `openai/...` models. `-M max_retries=0` turns off that SDK's own retries for those two providers. `-T 'seeds=[1]'` runs one seed instead of five. The score metadata includes `start_tick`, `end_tick`, `stage_ticks`, `paused_seconds`, and `outages`.

## Assisted rocket run

`playtests/rocket.md` with `--skill skills/factorio-rocket` gives the agent a written skill and, with `--camera`, screenshots. Report that time apart from benchmark scores. The summary lists the skill under `skills`.

The camera needs the graphical client (`mise run fetch-factorio -- --client`, which needs `FACTORIO_USERNAME` and `FACTORIO_TOKEN`) and Xvfb with Mesa. Without a camera, `fac screenshot` fails as `unavailable`.

```bash
mise run playtest -- playtests/rocket.md --model opus \
  --skill skills/factorio-rocket --camera --until rocket \
  --timeout 172800 --max-resumes 100 --autosave-minutes 10
```

`--agent omp --model claude-opus-5-5` runs the same task with omp. Use the full model name there.

`--timeout` here is 48 hours. A huge value such as `999999999` leaves the cap unreachable. The run still ends at the rocket, after 100 resumes, or when you stop it. `0` ends it immediately.

Ctrl-C once stops the agent, saves the world, and writes `summary.json` with `"stopped": true`. A second Ctrl-C interrupts the runner. Do not signal the Factorio process yourself: a second signal during its save leaves a partial zip.

To continue from a save this run left behind:

```bash
mise run playtest -- playtests/rocket.md --model opus \
  --skill skills/factorio-rocket --camera --until rocket \
  --save target/playtests/<run>/world/save.zip \
  --notes target/playtests/<run>/notes.md \
  --timeout 172800 --max-resumes 100 --autosave-minutes 10
```

`--notes` is the `notes.md` the earlier run copied into its run directory, when the agent wrote one.

`--save` copies that zip. `seed` in the new summary is null. `start_tick` and `packs_at_start` are the world as the new agent found it.

## Watch a world

The game port listens on localhost unless you pass `--listen ADDRESS` on the playtest command. The runner then prints `watch with: fac watch ADDRESS:PORT` on stderr. Anyone who can reach that address can watch the map, so use a private network.

On a machine with a display:

```bash
HOST=ADDRESS:PORT mise run watch
```

Set `HOST` to the full `address:port` from that line. A playtest chooses its own port. `DISPLAY` must name a display the X server accepts, or `fac watch` exits before Factorio starts. `mod/factobot` in this checkout has to match the running daemon, file for file. Watching does not change the world.
