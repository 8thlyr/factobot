# factobot

A Factorio benchmark for AI agents, built for public release: agents play through the `fac` CLI in real time, under the limits a human player has. `docs/decisions.md` is the source of truth for design; read it before changing behavior, and record any new decision there with its reason.

## Layout and commands

`docs/development.md` covers setup, hosts and layout. Run commands through mise so the pinned toolchain and Factorio version apply:

- `mise run check` before every push: format, lint and unit tests. CI runs the same tasks.
- There are no live tests (decision 88). A change to the daemon, the mod or the protocol is proved by its unit tests and by observing the game as Verifying game behavior below says; say in the PR what you observed.
- `mise run fmt` formats and `mise run lint` checks Rust, Python and Lua. To check a single file, run ruff and basedpyright through uv: `uv run --project python ruff check <path>`, `uv run --project python ruff format <path>`, `uv run --project python basedpyright --project python`. They live in the uv venv, not on PATH, and `mise exec -- ruff` fails too. StyLua is a mise tool, so a bare `stylua` works.
- Overnight runs are in `docs/development.md` (Playtests, Rocket run, Seeing the game). `TIMEOUT=0 mise run rocket` (like `--timeout 0`) stops the agent as soon as the world has booted, so it is not unlimited; a huge `TIMEOUT` such as `999999999` removes the time cap, and the run still ends at the rocket, after 100 resumes, or when stopped by hand. `mise run watch` and `mise run dev` on a Hyprland desktop need the Hyprland session's `DISPLAY=:0` and `WAYLAND_DISPLAY`, or the window cannot attach.

## Verifying game behavior

Observe the game; never infer its state from your own code. `docs/development.md` shows the tools:

- **Test worlds** (`factobot.harness.start_world`): set up the exact situation with Lua, step to exact ticks with `run_to_tick`, then assert on what the game reports. Check every new agent command this way, the limits it must enforce as well as the happy path.
- **`fac dev lua`** answers "what is actually in the world now" during development; `fac dev reload` loads mod edits without losing the world.
- **Screenshots** (`World.screenshot` with `start_world(camera=True)`, or `fac dev screenshot`): after any change that builds or moves things, render the area and read the PNG. Positions, directions and belt layouts are easy to get subtly wrong in code and obvious in a picture.
- **Playtests** (`mise run playtest -- playtests/<task>.md`): once a command works, check that an agent finds and uses it correctly from `--help` alone, and fix the help text or error messages it stumbles on.
- **`calls.jsonl`** in the run directory shows every call and the tick it landed on when a run misbehaves.
- **`fac dev hash`** must agree across two runs with the same seed and inputs; a command that breaks that is nondeterministic.

## Invariants

- **Fair play.** Agent-facing commands enforce what a player faces: reach, walking time, mining and crafting time, inventory cost, fog of war. A shortcut that lets an agent act at a distance or instantly is a benchmark bug, however convenient.
- **Real time.** The world never pauses for the agent. Pausing for model API outages (decision 19) exists only in the shelved Inspect path (decisions 45, 46); playtest harnesses never pause. The rocket track's autosaves briefly stall the game (decisions 48 and 77), so its times are not benchmark scores. Test worlds pause to make assertions exact.
- **One protocol.** `docs/protocol.md`, `crates/factobot/src/protocol.rs` and `python/src/factobot/client.py` change together. Breaking changes bump `PROTOCOL_VERSION`.
- **Mod calls.** The daemon reaches the game only through the mod's `/factobot` and `/factobot-dev` commands, which return one JSON line. Keep `/c` and `/sc` for manual debugging.
- **Agent sandbox.** Agents get `fac-agent`, the agent socket, their own harness binary and a shell, a throwaway home with a copy of its login, read-only system files and outbound internet, and nothing of the repo or the host: no dev socket, no RCON password, no harness source, no `fac daemon` (details in `docs/development.md`). Playtests hold every harness to this with bubblewrap (`python/src/factobot/sandbox.py`), not with the harness's own permission rules. One known gap, still open in decision 46: a Claude Code login refreshed during a run is written back to the host's file, and an agent that controls another Claude account can use that to switch the host's login, so log the host in again (`claude auth logout`, then `claude auth login`) after a playtest with an agent you do not trust.
- **Game files.** Download the game at runtime with `scripts/fetch-factorio`. Commit no game binaries, data or sprites, and bake none into images (Factorio terms of service).

## Conventions

- Rust 2024, clippy clean with `-D warnings`. Python 3.12+, ruff and basedpyright clean. Lua is formatted with StyLua and checked by lua-language-server against `.luarc.json`.
- Every `fac` subcommand prints one JSON object on stdout, exits non-zero on failure, and has `--help` with examples.
- Tests catch behavior a caller would notice. Mocks of the game prove nothing about the game: observe it in a test world instead.
- Secrets live in `.env.local` (gitignored). Name the key, never print its value.
- Docs and PR text: plain sentences, no em dashes.
- PRs target `main` and merge with merge commits. File them and turn on auto-merge (`gh pr merge N --merge --auto`): a ruleset requires the `Lint and test` check, and GitHub merges once it is green. No automated reviewer runs on this repo, so no `review-gate` status is coming. Leave `.github/review-loop.toml` and the `needs-review` label on Dependabot PRs in place; they are kept for a review loop that is switched off. To wait for the merge, run this loop. It ends when the PR merges or closes, or when a required check fails, since auto-merge never merges a PR with a red required check. A failed `gh` call (network, auth, rate limit) is retried rather than read as an end state:

  ```sh
  while :; do
    state=$(gh pr view N --json state -q .state) || { sleep 60; continue; }
    [ "$state" = OPEN ] || break
    gh pr checks N --required --json bucket -q '.[].bucket' | grep -qx -e fail -e cancel && break
    sleep 60
  done
  ```

  Then `gh pr view N --json state` says MERGED or CLOSED, or OPEN when a required check failed; `gh pr checks N --required` names it. Do not wait with `gh pr checks N --required --watch`: a required check that has not reported on the new head yet is missing rather than pending, so the watch can end, or fail with "no required checks reported", before the check reports. Do not substitute the babysit-pr skill's `pr-wait N --until merged` either: it reports a failed required check as an event and keeps waiting, so it never stops on the red check that blocks auto-merge.

## Reference code

`reference/` (gitignored) holds a clone of FLE (MIT): copying is allowed with attribution. autorio, czp3009/factorio-mcp and factorioctl are unlicensed: study them, copy nothing.
