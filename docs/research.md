# Factobot research notes

Goal: a benchmark where agents play Factorio through a CLI: see the screen, menus, inventory and game state, and move, place, build, plan (blueprints) and delete.

Sources: a code read of FLE (`reference/fle/`, gitignored), live web and GitHub reads, and JC's research pass dated 2026-11-01. Items marked UNVERIFIED were not checked against a primary source.

## Verdict

It's feasible. Text state plus API-level actions over RCON is prior art (FLE, autorio, about a dozen 2026 MCP servers). Real screenshots are a moderate infrastructure job. Real menus are the novel part and the hardest. czp3009/factorio-mcp already reads and clicks the real game UI by injecting code into the client.

Newest proof point: on 2026-10-31, Ryan Madden had GPT-5.6 Sol (Codex, low thinking) launch a rocket on peaceful mode in 13.5 hours of game time. It played through a Python library that enforces player limits (reach, fog of war). The late game leaned on hand-ferrying items instead of connected logistics. GPT-5.5 had failed to use belts at all. https://ryanmadden.net/gpt-56-beats-factorio/

## Versions and licensing

- Lua API docs show 2.1.24: https://lua-api.factorio.com/latest/. Direct downloads show 2.1.23 as stable (per JC's research). FLE pins `factoriotools/factorio:2.0.73`. autorio was tested on Steam 2.0.77. czp3009/factorio-mcp was tested on 2.1.24.
- The headless server is free. A graphical client needs an owned copy. The terms of service (https://www.factorio.com/terms-of-service) allow personal, non-commercial use and forbid distributing game files. So don't ship Docker images with the game baked in; download at runtime. Ask Wube before any commercial use. Whether each concurrent graphical client needs its own license is UNVERIFIED.
- FLE downloads sprites from the HF dataset `Noddybear/fle_images`. Redistributing game art that way is a licensing gray area.

## Prior art

### FLE: Factorio Learning Environment

https://github.com/JackHopkins/factorio-learning-environment. MIT license. v0.4.8, commit e2a829d (2026-09-06). About 1.2k stars. NeurIPS 2025.

- **Architecture:** the agent writes Python against a tool namespace. Each tool is a `client.py` plus a `server.lua` talking over RCON (`fle/env/tools/agent/*`). Other surfaces: a Gym env, an MCP server (`render`, `execute`, plus git-like undo/commit/restore) and A2A multi-agent.
- **Time:**
  - `storage.fast = true` is the default (`instance.py:512`). `move_to` follows a path and then teleports; crafting and mining are instant.
  - Each action adds its would-be ticks to `storage.elapsed_ticks`. Slow mode uses `walking_state`, `begin_crafting` and `mining_state`.
  - `GameControl` drives `game.tick_paused` and `game.speed`.
- **Rules:** placing checks `reach_distance` and consumes inventory. Harvesting checks `resource_reach_distance`.
- **Vision:**
  - The `render` tool draws a top-down PNG in Python from entity data. It is not a game screenshot.
  - Real `take_screenshot` appears only in offline tooling (`fle/eval/analysis/run_to_mp4.py`).
  - FLE's v0.2 post says vision models didn't help scores much (as of May 2025).
- **Leaderboard:** stale (March 2025). Claude 3.7 Sonnet 29.1% on lab-play is the best listed. No 2026 frontier models.

| Want | FLE | Gap |
|---|---|---|
| Move | `move_to` (teleport by default) | Fine; slow mode walks for real |
| Place / build | `place_entity`, `place_entity_next_to`, `connect_entities` (auto-routes belts, pipes and poles), `rotate_entity`, `shift_entity`, `set_entity_recipe` | Fine |
| Delete | `pickup_entity` (one entity at a time) | No area deconstruction |
| Plan | `can_place_entity`, `nearest_buildable`, `get_resource_patch` | Blueprints are admin-only; no ghosts for agents |
| Inventory / state | `inspect_inventory`, `get_entities`, `get_entity`, `get_research_progress`, `score` | Fine |
| Menus | none | Missing |
| Screen | Python sprite render | Not the real screen |

### ryanmadden/autorio

https://github.com/ryanmadden/autorio. TypeScript. Author calls it "unreleased, buyer beware". Used for the GPT-5.6 rocket run.

- **macOS only.** The full graphical game hosts a private multiplayer session, so one process provides both the player character and RCON. No dedicated server is needed. The same trick should work on Linux under Xvfb (UNVERIFIED).
- A bundled mod, "Autorio native character control", gives real walking along game pathfinder routes and real mining using native mining state and timings. Crafting queues while the agent keeps acting.
- Benchmarks are JSON: map seed, starting items, daylight, time limit, milestones. Scoring is independent of the agent: a run only counts as finished when the harness observes the goal. It records `telemetry.jsonl` (production, research), `jobs.jsonl` (actions) and hashes of the harness and client.
- The game runs at speed 1, and wall-clock time counts agent thinking time. That makes it a real-time benchmark, not turn-based.
- Lessons from Madden's earlier post (https://ryanmadden.net/claude-plays-factorio/):
  - Claude found the harness API and sent raw RCON with curl, so sandbox the agent away from harness code.
  - Remote entity access and instant mining are cheats; enforce reach and time.
  - Models avoid belts and struggle with spatial layout.

### czp3009/factorio-mcp: real menus and real screen

https://github.com/czp3009/factorio-mcp. Kotlin with native C++. Linux x64 and Windows x64. Tested on 2.1.24 with the DLC.

- It injects code into a running graphical client. No mod, no RCON and no admin rights. The README warns this "may be considered cheating".
- Tools:
  - `screenshot`: the rendered game plus UI.
  - `ui_read`: UI structure, text and control values, including menus and mod windows.
  - `ui_action`: click a widget, set text or press a key.
  - `input`: keyboard and mouse timelines.
  - `world_query` and `world_overview`: world state.
  - `chat_read` and `chat_send`.
- **Linux requirements:**
  - The same user runs both processes, and ptrace must be allowed (`kernel.yama.ptrace_scope=0` for Steam-launched clients).
  - It needs the unstripped game executable, plus libpng and libturbojpeg.
- **Limits:**
  - UI reads are best-effort: custom-painted pixels and dynamic tooltips aren't reconstructed.
  - An action completing does not confirm the server accepted it.
- This is the only project found that gives agents the real menus as structured data. Best candidate for the menus track.

### Others (stars and last push from JC's GitHub API pull, 2026-11-01)

| Project | What | Stars | Last push |
|---|---|---|---|
| moeru-ai/airi-factorio | Mod (TS to Lua), RCON, LLM; optional YOLO vision on a real client in Docker (Xvfb, VNC, noVNC) | 104 | 2026-02-25 |
| Jimesarrice/FactorioAgent | Server scenario plus RCON, with a second real client as the bot's body; researches through the real UI; 49 MCP tools | 0 | 2026-10-27 |
| MarkMcCaskey/factorioctl | Rust kubectl-style CLI plus MCP; A* belt routing; ASCII `render_map` | 11 | 2026-01-26 |
| sbarisic/FactorioMCP | C# MCP, "no cheating": real walking, craft times, range checks | 15 | 2026-04-05 |
| thedemon117/ai-player-v3 | 2.0 mod that spawns an AI character, plus MCP; has build_ghosts and deconstruct | 10 | 2026-08-29 |
| lveillard/factorio-ai-companion | Companion characters, 51 RCON commands, MCP | 14 | 2026-09-13 |
| WidAmi/FactoMCP | Python MCP over RCON | 10 | 2026-04-20 |
| Palats/mapshot | Zoomable map renders made with the real client (`xvfb-run` works) | 135 | 2025-11-23 |
| ryanmadden/faketorio | 50x50 fake-Factorio testbed | 0 | 2026-03-14 |

## Screenshots

- `game.take_screenshot` does nothing on a headless server. Any graphical client connected to the game can take them; `by_player` picks whose client renders.
- **Linux without a GPU:** the graphical client runs under Xvfb with Mesa llvmpipe. Working recipe: https://tangled.org/une-tasse-de.cafe/Factorio-Map/blob/main/README.md. Gotcha: screenshots pile up in RAM, so batch them.
- AIRI devlog on running a client in Docker (Xvfb, x11vnc, noVNC): https://airi.moeru.ai/docs/en/blog/DevLog-2025.08.26/
- **Cheap modes:** FLE's sprite render, factorioctl's ASCII map, or a custom render built from `find_entities_filtered`.

## Engine primitives (LuaGameScript docs, 2.1.24)

- `game.tick_paused`, `game.ticks_to_run` (run N ticks, then re-pause) and `game.speed`. `ticks_to_run` is the clean primitive for turn-based stepping.
- Multiplayer is deterministic lockstep (https://wiki.factorio.com/Desynchronization). A rendering client is just another peer, which suits replays.
- **RCON speed:** a 2019 forum report found large `/c` commands slow down when a player is connected (UNVERIFIED in 2.x). Register mod commands or a remote interface that returns compact JSON instead.

## Candidate architecture

```
agent (sandboxed, CLI only)
  └─ fac CLI / MCP ──► factobot daemon (holds RCON, pause/step, logs, scoring)
                         ├─ RCON ──► game host: graphical client under Xvfb hosting MP (autorio-style),
                         │           or headless server + Xvfb spectator client
                         │           └─ factobot mod: JSON observe/act, rule enforcement
                         └─ (menus track) czp3009-style injection: screenshot, ui_read, ui_action
```

Hosting the game from a graphical client (autorio's approach) removes the separate headless server. `take_screenshot` then works in the same process. The cost is one owned copy and one llvmpipe renderer per environment.

## Open decisions

1. **Base:** fork FLE (Linux, Docker, scoring already built, but defaults to teleporting), port autorio's design to Linux (real walking, honest scoring), or build fresh borrowing from both.
2. **Timing:** turn-based (`ticks_to_run`, reproducible) or real-time at speed 1 (autorio style, so thinking time counts against the agent).
3. **Action level:** player-like actions, or high-level helpers such as `connect_entities` and recursive crafting, which do much of the agent's planning.
4. **Vision:** sprite render, real screenshots from an Xvfb client, or both as separate tracks.
5. **Menus:** structured API stand-ins, czp3009 injection (real UI, Linux ptrace, possibly against the spirit of a benchmark), or xdotool into the Xvfb client.

## Rough effort (JC's research estimate, unsourced)

About 4-7 weeks without real menus, 2-3 months with them. The MVP is about 2 weeks:

- **Setup:** headless server, a small mod and an RCON daemon.
- **CLI:** one `fac` CLI with about 12 commands: observe-player, observe-area, observe-entity, observe-research, walk, build, mine, craft, insert/extract, rotate, set-recipe, research, wait-ticks.
- **Turns:** `ticks_to_run` stepping.
- **Vision:** a synthetic PNG.
- **Tasks:** 3-5 lab tasks.
- **Agents:** Claude Code or Codex running in a sandbox that has only the CLI.
