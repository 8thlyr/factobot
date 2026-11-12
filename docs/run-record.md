# Playtest run record

`python -m factobot.playtest` writes one directory, named with `--out` (by default `target/playtests/<task>-<timestamp>-<random>`, where `<random>` is 8 hex digits so two runs started in the same second get different directories). A directory that already holds a world (`world/save.zip` or `world/calls.jsonl`) is refused. `summary.json` in that directory is the record of what ran. The runner writes it to a temporary file in the directory and moves it into place, so a signal during the write does not leave a truncated file.

`schema` is `1`. This document describes that shape.

## `summary.json`

Times are UTC, `YYYY-MM-DDTHH:MM:SS.ffffffZ`. `started_at` is taken when the run begins, before the world boots. `ended_at` is taken when the summary is built, after the agent and the world have stopped.

`git` is the checkout that contains the working directory the run was started from: `commit` is `git rev-parse HEAD`, and `dirty` is true when `git status --porcelain` prints anything (staged, unstaged or untracked). `git` is null outside a checkout, and when git cannot name `HEAD`.

`versions.factobot` is the installed Python package version. `versions.game` and `versions.mod` are `script.active_mods` for `base` and `factobot`, and `game_speed` is `game.speed`, read from the world once it is up. `versions.protocol` is the protocol version this package speaks. `versions.game`, `versions.mod` and `game_speed` are null when that read did not happen or the world did not report a string or a number.

`task_sha256` is the SHA-256 of the task text (the task file's contents, not the preamble the harness adds in front of it). `setup_sha256` is the SHA-256 of the setup Lua, and null when the run had no setup file. Both are lowercase hex of the UTF-8 text.

`skill_sha256` maps each installed skill's directory name (the same names as `skills`) to the SHA-256 of that directory. The digest covers every file under it, in sorted order of the relative path with `/` as the separator. A symbolic link to a file counts as that file. A symbolic link to a directory is not walked. For each file the digest takes the relative path as UTF-8, a NUL byte, the file's bytes, and a NUL byte. The object is empty when the run installed no skill.

`config` is the limits the run was given.

| Key | Type | Null when |
|---|---|---|
| `schema` | integer | never. `1` for this shape |
| `started_at` | string | never |
| `ended_at` | string | never |
| `git` | object | outside a git checkout, or when git cannot name `HEAD` |
| `git.commit` | string | not present when `git` is null |
| `git.dirty` | boolean | not present when `git` is null |
| `versions` | object | never |
| `versions.factobot` | string | the installed package has no version metadata |
| `versions.game` | string | the world was not read, or did not report `base` |
| `versions.mod` | string | the world was not read, or did not report `factobot` |
| `versions.protocol` | integer | never |
| `game_speed` | number | the world was not read, or did not report a speed |
| `task_sha256` | string | never |
| `setup_sha256` | string | the run had no setup file |
| `skill_sha256` | object | never. Empty when no skill was installed. Each value is a string |
| `config` | object | never |
| `config.timeout` | number | never. Seconds the agent may run, not counting world boot |
| `config.max_resumes` | integer | never |
| `config.autosave_minutes` | number | autosave is off |
| `config.camera` | boolean | never |
| `config.listen` | string | `--listen` was not given |
| `task` | string | never. The task's first line, or `""` when the task text is blank |
| `agent` | string | never. The harness name |
| `model` | string | a custom command was given no `--model` |
| `seed` | integer | the run started from `--save`, which brings its own map |
| `save` | string | the run did not use `--save`. A path is absolute |
| `exit_code` | integer | the runner stopped the agent, or the agent never started. A negative code means the process died from a signal |
| `stopped` | boolean | never. True when a signal ended the run |
| `timed_out` | boolean | never. True when the timeout stopped the agent before the goal, and no signal did |
| `wall_seconds` | number | never. Seconds from the start of the run to the summary, to one decimal |
| `turns` | integer | the harness did not report them |
| `cost_usd` | number | the harness did not report a cost |
| `fac_calls` | integer | never |
| `fac_errors` | integer | never. Calls whose response was not ok |
| `methods` | array of strings | never. Empty when the agent made no call. Sorted, with no repeats |
| `response_bytes` | object | never |
| `response_bytes.total` | integer | never. Bytes of the daemon's responses to the agent's calls |
| `response_bytes.by_method` | object | never. Method name to byte count, largest first. Empty when there were no calls |
| `final_answer` | string | the harness reported no answer |
| `until` | string | `--until` was not given |
| `milestone_tick` | integer | there was no goal, the goal was not reached, or the world was not read |
| `resumes` | array | never. Empty when the agent was not resumed. Each entry has `exit_code` (integer), `tick` (integer) and `wall_seconds` (number) |
| `agent_failed` | string | the agent did not fail to start several times in a row. Otherwise the last line it wrote |
| `error` | string | the world did not fail under a running agent. Otherwise the exception's type and message, from a world that failed after it first answered and with no stop signal. The ticks and packs are then from the last poll that worked |
| `research` | array | never. Empty when none was recorded. Each entry has `name` (string) and `tick` (integer) |
| `lab_use_by_minute` | array | never. Empty when none was recorded. Each entry has `tick` (integer) and `used_by_labs` (object of pack name to count) |
| `autosaves` | array | never. Empty when autosave is off or none are still on disk. Each entry has `path` (string) and `tick` (integer). Oldest first |
| `start_tick` | integer | a stop during boot left the world unread |
| `end_tick` | integer | the world was not read |
| `packs_at_start` | array | the world was not read. Otherwise the packs already made or used when the agent started. Each entry has `name`, `made_by_hand`, `made_by_machine` and `used_by_labs` |
| `packs` | array | the world was not read. Otherwise the packs made or used by the end of the run, in the same shape as `packs_at_start` |
| `out_dir` | string | never. The run directory |
| `skills` | array of strings | never. Empty when no skill was installed. Directory names, in the order given |

## Other files

| Path | What it holds |
|---|---|
| `started` | Empty file, created when the run directory is made. `agent-view` orders runs by its modification time. |
| `transcript.jsonl` | The harness's stdout. Absent when the agent never started. |
| `world/save.zip` | The save the server writes when it quits. Absent when the world never booted. |
| `world/calls.jsonl` | The daemon's call log, appended while the world runs. |
| `world/daemon.log` | The daemon's log. |
| `world/server.log` | The Factorio server's log. |
| `world/write-data/saves/autosave-1.zip` | Autosaves when `--autosave-minutes` is set, with `autosave-2.zip` and `autosave-3.zip`, rotated in turn. `autosaves` in the summary lists the ones still on disk. |
