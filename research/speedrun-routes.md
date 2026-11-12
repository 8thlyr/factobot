# Speedrun routes: how top Factorio runners reach the rocket, and a route for the factobot agent

Research date 2026-11-02. Game data comes from wube/factorio-data at commit `acf5a342afcb66c066b9d88d202e8622112da117` ("added version 2.1.24", 2026-10-27; `base/info.json` version 2.1.24). Short form below: `fd:<file>`, meaning `https://github.com/wube/factorio-data/blob/acf5a342afcb66c066b9d88d202e8622112da117/base/prototypes/<file>`. The freeplay start inventory comes from the 2.1.24 install (`data/base/script/freeplay/freeplay.lua`), because that script is not in the factorio-data repo. Run timings come from LiveSplit overlays I read off VOD frames (`yt-dlp --download-sections` plus ffmpeg), from speedrun.com API data and from runners' slide decks. Tags: `[INFERENCE]` is my own derivation, `UNVERIFIED` is a claim I could not check, `UNVERIFIED-2.x` is a 1.1-era claim not confirmed for 2.x.

Throughout, "action" means one `fac` command. The task brief puts each action at 5 to 30 s of game time. Where a number needs one value, I use 15 s per action, labelled `t_a`.

---

## Summary: ranked takeaways (largest time saved first)

1. **Size the factory to the action budget, not to a human's.** Runners place 2,000+ entities, and bots print most of them. At `t_a` = 15 s, 1,000 placements cost about 4 game hours. The whole run needs roughly 240k iron plates, 180k copper plates and 20k+ steel (§10). How fast those must arrive depends on how long the run is. The best build is therefore much smaller than a runner base. A lean base of about 60 drills, 50 furnaces, 50 assemblers and 20 labs puts the rocket around 6 to 8 h, against a 50 h average human reference `[INFERENCE]` (§10c, §11).
2. **Direct insertion inside a cell, one belt run between cells.** `place --to` lays a straight belt run in one action plus its walking time (decision 52). Inside a cell the chain costs one action per machine: drill→furnace, furnace→inserter→assembler, assembler→inserter→lab, lab→inserter→lab. Zaspar's 2.x opening already places assemblers beside burner-furnace columns and pulls plates straight out of the furnaces (Zaspar WR VOD frames 9:02 to 10:32, §4). Where a line has to cross something, underground belt pairs cover 6 tiles in 2 actions (`max_distance = 5`, `fd:entity/transport-belts.lua`). Pipe-to-ground pairs cover 11 tiles in 2 actions (`max_underground_distance = 10`). Big poles cover 32 tiles per action (`fd:entity/entities.lua`).
3. **Keep the hand-craft queue full and batch it.** In the early game, the only way to save time is to reach a permanently busy craft queue sooner ([lhaxq's Steelaxe% guide](https://www.speedrun.com/factorio/guides/kczn3)). For the agent, one `craft --count N` is one action for minutes of crafting, and it runs during walking and mining. So the agent should hand-craft nearly every building and skip the runner "mall" (§8).
4. **Four productivity-3 modules in the silo.** Productivity 3 is +10% each (`fd:item.lua`), so 4 give +40%, and only 72 rocket-part crafts are needed instead of 100 (100 / 1.4 = 71.4, rounded up). That saves 280 each of processing units, low density structures and rocket fuel. In raw terms it saves about 9.5k iron, 16.8k copper, 2.5k plastic and 30.8k light oil, for an input cost of 6.6k copper and 3.6k iron `[INFERENCE: recipe.lua arithmetic, §10]`. The productivity-module-3 tech is a rocket-silo prerequisite anyway, so the bonus needs no extra research. Every runner does this (Zaspar guide "Prod3s into rocket silo"; Nefrums guide same).
5. **Research has a floor, so get enough labs.** The mandatory tech closure is 62.3 lab-hours at speed 1 ([human-baselines.md §3c](../docs/human-baselines.md)). The rocket-silo tech alone is 1000 units × 60 s. Each lab feeds the next through 1 inserter, so it costs about 2 actions. With research speed 1 and 2 (+50% total, 2.5 lab-h to research, `fd:technology.lua`), the silo tech takes 33 min on 20 labs and 67 min on 10 labs `[INFERENCE]`. Runners use 32 labs, then 64 at purple (Zaspar guide).
6. **Pre-stage the rocket inputs in chests before the silo's research finishes, and feed the silo by inserter.** Runners do not belt into the silo. Zaspar: "Pick up rocket parts and put them in the silo manually". The split data shows how short the gap is: "silo researched" to launch takes 1:48 (JeHor Any%), 2:35 (JeHor DS) and 6:17 (Krul87). Stack sizes are 100 processing units, 50 LDS and 20 rocket fuel (`fd:item.lua`). With prod3, 720 of each (72 crafts of 10, since 100 / 1.4 = 71.4 rounds up) fits in about 59 inventory slots (8 + 15 + 36) `[INFERENCE]`, but a factobot test world shows the silo's input holds at most 104 processing units, 54 LDS and 24 rocket fuel at a time, so what the agent carries goes in over about 36 rocket fuel inserts across the 9-minute build, not in a few trips; feed the silo from chests by inserter instead.
7. **Fuel in full stacks and avoid refuel loops.** At 150 kW, 50 coal lasts 22 min in a burner drill. At 90 kW it lasts 37 min in a stone or steel furnace. A boiler at full 1.8 MW burns it in 111 s (`fd:entity/entities.lua`, `fd:entity/mining-drill.lua`, coal 4 MJ in `fd:item.lua`). Two burner drills on coal that face each other refuel each other forever ([wiki Burner mining drill](https://wiki.factorio.com/Burner_mining_drill)). A chest plus inserter holds 1,600 coal, which feeds a furnace for about 20 h and a boiler at full load for about 1 h `[INFERENCE]`.
8. **Plan the fixed seed offline.** Runners pay roughly 10 minutes of map rolling per attempt and pick maps with close, non-overlapping starting patches, a big secondary iron patch and about 1600% oil (Zaspar guide). Any% runners go further and route one set seed with absolute coordinates (Mazmot, Nefrums). We play fixed seeds, so a precomputed plan saves dozens of `observe`/`map`/`walk` actions: patch coordinates, water, rocks and trees in the way `[INFERENCE]`.
9. **Skip what runners only need for biters, bots or vehicles.** Skip gun turrets, military 1 and 2, heavy armor, stone walls, military science, grenades, landmines, construction robotics, worker robot speed, cliff explosives (unless cliffs block the build), car and circuit network. All of these appear in runner queues (Zaspar, Phredward). None is in the rocket-silo closure, which I recomputed from `fd:technology.lua` (§6).
10. **Take the free steel axe early.** In 2.x, steel-axe is a trigger tech: craft 50 steel plates, effect `character-mining-speed` +1, i.e. +100% (`fd:technology.lua`). Zaspar: "place 5 furnaces and half stack them with iron to unlock steel axe." It halves the time to hand-mine rocks, trees and ore. The agent mines rocks and trees a lot and picks its own buildings back up.
11. **Mind the milestone rule.** factobot counts the first research that uses more packs than were ever hand-crafted ([decisions.md](../docs/decisions.md) #43). Every hand-crafted science pack delays the milestone for its tier by one machine-made pack. Hand-craft only the 10 red packs that Automation needs, then switch to assemblers.
12. **Launch needs a payload.** A raw fish works: mine a fish entity, `mining_time` 0.4, `count` 5 (`fd:entity/entities.lua`). Runners launch with a fish (Zaspar guide "Feed the fish as the rocket payload"; JeHor Any% has a "Fish" split). No cargo landing pad is needed: in a factobot test world (2.1.24 freeplay, seed 1, 2026-11-02) a silo with no pad anywhere launched a rocket carrying one fish, and the game recorded the victory. The wiki says a pad is needed; it is wrong for this case.

---

## 1. Sources

| Source | Version | What I used |
|---|---|---|
| Zaspar's speedrun guide (Google Slides), [export/txt](https://docs.google.com/presentation/d/12dO2YmmOUK_R528-jCKo2nSdJUKNkp-vvXWqDHS3PKo/export/txt) and [export/pdf](https://docs.google.com/presentation/d/12dO2YmmOUK_R528-jCKo2nSdJUKNkp-vvXWqDHS3PKo/export/pdf) | 2.0 and 2.1 (gives one seed per map generator) | All 51 slides. I rendered the PDF to read the per-slide crafting lists and research queues, which the txt export drops. |
| Zaspar DS WR 1:59:01, [VOD](https://www.youtube.com/watch?v=2PwyPjjoOJo), [run](https://www.speedrun.com/factorio/runs/yvk04e8m) | 2.x, 2026-08-22 | Frames every 30 s for 0:00 to 11:00, end frame, auto-captions |
| JeHor 2.0 Any% 1:42:41 (Any% WR), [VOD](https://www.youtube.com/watch?v=UYXo0P8adpE), [run](https://www.speedrun.com/factorio/runs/y8ovjjwm) | 2.0.28 | Map generator frame, LiveSplit frames at 0:25, 0:35, 0:45, 1:15, 1:35 and the end |
| seb351 DS 2:33:22, [VOD](https://www.youtube.com/watch?v=6cu7Z1MfG4o); Krul87 DS 2:41:56, [VOD](https://youtu.be/oaAw8nC3k5g); JeHor DS 2:46:36, [VOD](https://youtu.be/IUK7OLl8TDc) | 2.0 | End-frame LiveSplit panels |
| Nefrums DS 2:19:12, [VOD](https://youtu.be/RI4ocNajf_w) | 1.1 | End-frame splits, auto-captions |
| [Nefrums' any% guide](https://docs.google.com/presentation/d/1XgyTdHzQM1cQrv1YpZJuRGtMv6AE9j4h6Phdn4Fe8-c) and his [research queue sheet](https://docs.google.com/spreadsheets/d/1z5tpebyMzPEstX9IR4PCHkjlvPlrntAdPMf3r2wrHnE) | 1.x | Burner counts, research order |
| [Phredward's DS guide (AntiElitz design)](https://docs.google.com/presentation/d/1etZgz5d2yIiFXLEXcKAeLRrEmdxyWHn2_8mrzQwgCLI) | 1.1 | Map selection thresholds, research queue, burner counts |
| [Mazmot Any% cheatsheet](https://hackmd.io/@Mazmot/HyMO_CBQp), [VOD chapters](https://www.youtube.com/watch?v=C0vKdPYboCg) | 1.1 | Set-seed route structure |
| [macros42 any% cheatsheet](https://docs.google.com/spreadsheets/d/1z0ov5azLLQi48M8lHLCcJGSMF5nQZDXnaVS40kQ6Nog) | 0.17/1.x | Split goals and assembler counts |
| [lhaxq Steelaxe% guide](https://www.speedrun.com/factorio/guides/kczn3) (text via [API](https://www.speedrun.com/api/v2/GetGuideList?gameId=9d35xw1l)) | 1.1 | Craft-queue principle |
| speedrun.com [categories API](https://www.speedrun.com/api/v1/games/9d35xw1l/categories), [game rules API](https://www.speedrun.com/api/v2/GetGameData?gameId=9d35xw1l), [resources](https://www.speedrun.com/factorio/resources) | current | Rules and leaderboards |

Fetch failures: the speedrun.com guide HTML pages and forum thread "Speedrunning design tips" returned 403 (Cloudflare); the v2 API worked for guide text. forums.factorio.com returned 403 through the reader. Mazmot's mapshot page is a JavaScript map viewer with no text. Zaspar's slide "Useful Links" entries (base blueprint, full crafting and research queues, save) still read "todo" in the deck.

---

## 2. Category rules relevant to us

The game-wide rules ([API](https://www.speedrun.com/api/v2/GetGameData?gameId=9d35xw1l)): latest stable or experimental version within 48 h of the start, the Freeplay scenario, no mods, and only the approved console commands. Map exchange strings are allowed only if they can be made in the in-game UI. The map preview may be used, and so may the [Factorio Preview Toolkit](https://github.com/AntiElitz/FactorioPreviewToolkit).

| Category | Map rules | Timing | Relation to factobot |
|---|---|---|---|
| **Default Settings** (DS) | "Default" preset, random map, no imported blueprints | Real time, from pressing "Random seed" to the victory screen | Same resources as ours, but biters on and the map random. The closest match for build sizes and oil distances. |
| **Any%** | Any map generator settings, set seed allowed, no imported blueprints | Real time, first frame of the map to the victory screen | Same freedom as ours: no biters and a known seed. Runners also max out resources, which we don't. JeHor's 2.0 WR used seed 1063559207 with iron, copper, coal and oil frequency, size and richness at maximum, slightly lower stone richness, and uranium off (map generator frame at 0:05 of the [VOD](https://www.youtube.com/watch?v=UYXo0P8adpE)). His enemy settings are UNVERIFIED. |
| Steelaxe% | Any settings | Stops when steel-axe unlocks | Its opening logic transfers directly to our first 15 min. |
| Category Extensions | Wave Defense, All Peaceful Achievements, Supply Challenge, Deathworld, Any% Botless, New Game+ | | **There is no peaceful-rocket category.** "Any% Botless" is the closest to our no-bots situation `[INFERENCE]`. |

Leaderboards fetched 2026-11-02:

| Category | Top runs |
|---|---|
| DS 2.x | Zaspar 1:59:01, seb351 2:33:22, Krul87 2:41:56, JeHor 2:46:36 |
| Any% 2.x | JeHor 1:42:41, Cyclomactic 1:52:33, Phredward 2:10:16 |
| Any% 1.x | Zaspar 1:18:56, Mazmot 1:21:56 |
| DS 1.x | Nefrums 2:19:12 |

How it applies to the agent: our settings sit between DS (default resources) and Any% (no enemies, known seed). DS times include biter work: turrets, grenades, landmine perimeters and pushing nests. They are a slightly pessimistic reference for a human on our settings. Any% times are optimistic, because maxed resources put all four patches at spawn (JeHor frames at 0:12 to 0:36).

---

## 3. What 2.x changed in the speedrun route (vs 1.1)

| Topic | 2.1.24 data | 1.1 | Effect on the route |
|---|---|---|---|
| First techs are triggers | steam-power: craft 50 iron plates. electronics: craft 10 copper plates. automation-science-pack: craft 1 lab. Both are needed before Automation (`fd:technology.lua`). | Lab, boilers and engines available at start | Smelting starts research. Zaspar's WR shows "Steam power" done at about 2:33 and "Electronics" at 6:02 (frames). |
| Electric mining drill | Tech `electric-mining-drill`, 25 red × 10 s, after automation-science-pack | Available at start | New early split: Zaspar's "Miner unlock", best 10:35. The burner phase lasts longer, so runners place 44 burners (Zaspar), up from 36 (Nefrums 1.x: 10/6/16/4). |
| Steel axe | Trigger: craft 50 steel plates, +100% character mining speed | Research, 50 red × 30 s (Nefrums sheet) | Free in 2.x. Zaspar half-stacks 5 furnaces with iron. |
| Oil processing | Trigger: mine crude oil. Pumpjacks come from `oil-gathering` (100 r+g × 30 s). | One research | A powered pumpjack extracting crude unlocks refineries. Research oil-gathering before the oil trip. |
| Rocket part | 10 processing unit + 10 LDS + 10 rocket fuel, 3 s, 100 parts (`fd:recipe.lua`, `rocket_parts_required = 100`) | 10 rocket control units instead of processing units | The RCU chain is gone. Processing units carry the whole load. |
| Silo prerequisites | concrete, rocket-fuel, accumulators, solar-energy, utility pack, speed-module-3, productivity-module-3, radar | Similar, plus rocket-control-unit | Research accumulators, solar and radar, but never build them. |
| Payload | Rocket needs a payload (raw fish works). No cargo landing pad needed (factobot test world, 2026-11-02). | Empty launch allowed | Mine one fish before the end. |
| Research queue | Built in | Optional setting | `fac research` queues. Queue everything early so labs never idle. |

---

## 4. The opening, minute by minute

Main source: Zaspar's 2.1 DS WR, one frame every 30 s ([VOD](https://www.youtube.com/watch?v=2PwyPjjoOJo)). His overlay timer ran about 3 s ahead of the video time. Each burner-phase step is matched to his guide slides.

| Run time | What Zaspar does | Guide reference |
|---|---|---|
| 0:00 to 0:30 | Accepts the map preview. Starts mining the huge rock by the crash site. | "Mine rocks and build burner miners, start with iron" |
| 1:00 | Checks rocks and trees around the planned base area. | |
| 1:32 | First burner drills plus stone furnaces on the iron edge. | "Place the burners close to the edge of the patch, with the furnaces on the outside... in the orientation your base will go" |
| 2:03 | Mining more rocks. Commentary: "so many stone rocks. Not very many coal rocks." | |
| 2:33 | "Steam power" researched: the 50-plate trigger is done. | |
| 3:02 | About 14 burner drills on iron in two facing columns, furnaces between them. | "14 on iron" |
| 4:02 | Burner drills on copper. | "6 on copper" |
| 5:30 | Burner drills on coal. The coal patch is far, so he does "all the coal before anything else". | "20 on coal", "4 on stone" |
| 6:02 | "Electronics" researched (10 copper plates). | |
| 6:32 | Crafting offshore pump, boiler and engine. | Power slide craft list: 1 offshore pump, 1 boiler, 1 engine, 30 small poles, 1 lab, 10 red packs, 15 gears, 15 circuits |
| 7:03 | "Automation science pack" researched (lab crafted). Pole line strung from the lake to the iron column, lab placed. | "Build a minimal power plant, feed it 1 stack of coal... Drag poles back to the iron patch and place your lab to start researching Automation" |
| 7:32 | Automation 27%. | |
| 8:00 to 8:30 | Chopping trees while research runs. | "Chop trees while the lab researches. Pre-craft some gears and green chips for assemblers." |
| 9:02 | Automation done. Assemblers placed beside the iron furnace column. Electric-mining-drill research starts. | Mini science slide: 7 assemblers "near your iron burners, keep them fed with plates. The 2 gears and 2 wire assemblers are your personal assemblers." |
| 9:30 to 10:32 | Three labs and red-science assemblers fed by inserters straight from the furnaces. Electric-mining-drill research at 85%. | Craft list: 7 assemblers, 9 inserters, 2 labs, 2 boilers, 2 engines, about 50 belts, about 50 poles |
| 10:35 | "Miner unlock" (his best split) | Power +2 boilers and +2 engines. "Craft belt and power poles until miners unlock." |

Other 2.x openings:
- JeHor 2.0 Any% (maxed resources, patches at spawn): "Burners" 4:55, "First Lab" 6:14, "1 more boilers (2)" 12:35, "Half-iron and Automated Belt" 18:02.
- seb351 2.0 DS: "First research" 7:14, "red science" 13:51.
- Krul87 2.0 DS: "Mini science" 16:09 ([human-baselines.md](../docs/human-baselines.md) §3a).

Burner counts by guide:

| Guide | Iron | Copper | Stone | Coal | Total |
|---|---|---|---|---|---|
| Zaspar 2.x | 14 | 6 | 4 | 20 | 44 |
| Nefrums 1.x any% | 10 | 6 | 4 | 16 | 36 |
| Phredward/AntiElitz 1.1 DS | 7×2 | 7 | 4 | 6×2×2 | about 49 |

Applying the opening to the agent:
- **Rocks first.** A huge rock takes 6 s to hand-mine (3 s / speed 0.5) and yields 24 to 50 stone plus 24 to 50 coal. A big rock takes 4 s for 20 stone (`fd:decorative/decoratives.lua`, character `mining_speed = 0.5` in `fd:entity/entities.lua`). Two or three huge rocks supply the whole burner phase's stone and early coal for about 10 actions. Ore takes 2 s per unit by hand, trees 1.1 s for 4 wood.
- **Far fewer burners.** Each burner drill is 4 actions: place drill, place furnace, fuel the drill, fuel the furnace. 44 burners would be about 176 actions, 44 min at `t_a` = 15 s. Runners refuel by dragging the cursor; the agent pays one action per refuel. Use 6 to 8 burner pairs on iron, 2 on copper and 3 burner drills on coal, each into a chest (§11 step 3). Get electricity and electric drills fast instead `[INFERENCE]`.
- **Copy Zaspar's 2.x layout trick.** Put assemblers and labs right next to the furnace column. Inserters then pull plates out of furnaces and feed packs into labs, with no belts.
- **Hand-craft only 10 red packs** for Automation (10 × 10 s). Later packs should come from assemblers (milestone rule, §Summary 11).

---

## 5. Build order and split timeline to the rocket

### 5a. Zaspar's 2.x DS build order (guide slides, with counts)

| # | Step | Key counts from the slide |
|---|---|---|
| 1 | Burner phase | 44 burners (14 iron, 6 copper, 4 stone, 20 coal), about 20 stone furnaces |
| 2 | Power and lab | 1 pump, 1 boiler, 1 engine, lab. Research Automation. |
| 3 | Mini science plus extra power | 7 assemblers (2 gear, 2 wire "personal", red science), +2 boilers/+2 engines |
| 4 | First half iron lane | 15 electric drills, 24 furnaces, coal fed from a chest, at least a 10-tile gap patch→smelter; assemblers: 1 ammo, 2 gears, 1 belt; +5 boilers/+5 engines |
| 5 | Green circuits | Half copper lane (15 drills, 24 furnaces), 4 wire plus circuit assemblers, copper buffer |
| 6 | More mining | Half coal lane (15 drills) to smelting and power, +half iron lane |
| 7 | Mall part 2 | 2 gear and 2 inserter assemblers on the circuit belt, chests limited to 3 stacks; power +12 engines/+2 boilers |
| 8 | More iron | Iron to 60 drills (2 belts), 48 furnaces, ore compressor; optional 5 furnaces for the steel axe |
| 9 | Mall part 3 | Iron buffer, copper buffer with 3 splitters, 6 wire plus circuit assemblers, circuit buffer; copper +half lane |
| 10 | Mall 4 plus labs | 2 gear, 1 belt, 2 pipe and 1 drill assembler; **10 red, 12 green assemblers, 32 labs (8 by 4)** |
| 11 | Coal and power | Coal across the whole patch, power 20 → 60 engines |
| 12 | Steel and bricks | Iron patch maxed (about 75 drills), steel 24+24 furnaces, 15 stone drills, 12 brick furnaces, steel-furnace assembler |
| 13 | Mall part 5 | Long and fast inserters, undergrounds, splitters, assembler 1 and 2, engines, pipe-to-ground; gears, pipes and inserters upgraded to assembler 2 |
| 14 | Iron outpost 1 | At least 30 drills, radar |
| 15 | Steel upgrade | Steel to steel furnaces; hand-fed assemblers make 10 engines for 1 car and 2 pumps |
| 16 | Oil | About 12 pumpjacks, at least 1600% yield (2000% cap), tanks; **10 refineries, 4 chem plants** |
| 17 | Green chips upgrade | Assembler 2, fast inserters |
| 18 | Blue | **24 red-circuit, 4 module, 14 blue-science assemblers** |
| 19 | Advanced oil | Cracking, tanks; explosives, acid, batteries, landmines |
| 20 | Bots | Electric engines, 7 frame assemblers, bots; roboports over the base; prod1 modules in circuits, frames, plastic, sulfur, acid and labs |
| 21 | Power | Solid-fuel plant: 12 chem plants, 40 boilers |
| 22 | Defences, backside smelting | Landmine border; 2 steel plus 2 normal smelters printed by bots |
| 23 | Iron outpost 2, copper outpost | 120 drills each, 4 belts |
| 24 | Mixed build | 4 identical modules making green chips, red chips, blue chips and LDS, with prod modules |
| 25 | Purple | **14 purple assemblers** (direct insertion), **labs doubled to 64** |
| 26 | Rocket fuel | **14 rocket-fuel assemblers**; hand-craft 20 beacons |
| 27 | Yellow | **12 yellow assemblers**, 25 frames hand-fed into each |
| 28 | Prod3, concrete, silo | 64 prod1 → 16 prod2 → **4 prod3**; 1000 concrete from 500 bricks and 100 ore; silo with **20 beacons** |
| 29 | Launch | Craft silo, insert the 4 prod3, hand-carry ingredients, fish, launch |

### 5b. Split timelines (LiveSplit, run time h:mm:ss)

| Milestone | Zaspar 2.x DS (overlay "Best" column) | JeHor 2.0 Any% (actual) | seb351 2.0 DS | Krul87 2.0 DS | JeHor 2.0 DS | Nefrums 1.1 DS |
|---|---|---|---|---|---|---|
| First lab / research | ~7:00 (frames) | 6:14 | 7:14 | | | |
| Electric drills unlocked | 10:35 | | | | | |
| Red automated | ~10:30 (frames) | | 13:51 | 16:09 "Mini science" | | 14:12 |
| Green circuits | | 18:04 / 19:37 (2nd) | 25:19 | | | |
| Red+green to mass labs | 32:57 "Labs" | 25:07 "Labs and Pipes" | 38:24 "Lab" | 39:31 "Mall + science" | 48:18 | 32:51 |
| Steel / steel furnaces | ~25:00 steel axe (commentary) | 29:45 / 30:54 | | | | |
| Oil reached | ~48:00 (commentary) | 33:05 "3 pumpjacks" | 58:17 | | | |
| Blue | 1:01:35 | 52:36 | | | 1:26:57 | 58:13 |
| Bots | ~1:06 (commentary) | 58:54 | 1:15:31 "Robotic" | | | 1:07:56 |
| Outposts / mixed | 1:26:11 "Mixed" | 1:14:06 "Mixed Build" | 1:37:03 iron, 1:48:05 copper | 2:02:22 | | 1:24:24, 1:38:47 |
| Purple + yellow | ~1:35 / ~1:43 start (commentary) | 1:23:28 "All Science" | | 2:13:47 | 2:22:35 | 1:52:21 / 1:54:54 |
| Prod 3s / concrete / fish | | 1:29:46 / 1:30:30 | | 2:29:49 | 2:29:27 / 2:30:26 | |
| Silo researched | | 1:40:53 | | 2:35:37 | 2:44:01 | 2:15:48 |
| Launch | 2:01:17 (overlay), 1:59:01 official | 1:42:41 | ~2:33 | 2:41:54 | 2:46:36 | 2:19:12 |

As fractions of each run (from §5b): mass labs at 0.24 to 0.29, blue at 0.42 to 0.52, purple+yellow at 0.81 to 0.86, silo research done at 0.96 to 0.98 ([human-baselines.md](../docs/human-baselines.md) §3b). The 1.x split goals in macros42's sheet are red 0:15, green 0:30, blue 1:00, purple 2:05, yellow 2:15, silo 2:30.

How it applies to the agent: the shares are stable across skill levels, so they make a reasonable template for the agent's split targets (§11). The steps from 20 to 24 onwards (bots, printed smelting, 120-drill outposts, mixed build) all rely on construction robots printing blueprints. That route is closed to the agent. Its late game must be a smaller, hand-placed factory that runs longer.

---

## 6. Research order

### 6a. What runners queue

Zaspar 2.x, in the order of his slides: Automation, Electric miners, Gun turret, Logistics, Fast inserter, Steel processing, Green science → Military 1, Heavy armor, Radar, Stone wall → Military 2, Steel furnaces, Automation 2, Toolbelt, Engine, Logistics 2, Car → Fluid handling, Oil processing, Military science, Lab speed 1, Lab speed 2 → Plastics, Sulfur, Red chips, Blue science, Modules, Productivity module, Speed module → Batteries, Explosives → Advanced oil, Lubricant, Electric engines, Robotics, Construction robots, Worker speed 1, 2 → Land mines, Mining productivity 1, Cliff explosives → LDS, Blue chips, Railway, Electric furnaces → Production science, Utility science, Flammables, Rocket fuel, Speed 2, Productivity 2, Concrete → (Circuit network) → Electric energy distribution 1, Accumulators, Solar panels, Beacons, Prod 3, Speed 3, Rocket silo.

The 1.x queues (Nefrums sheet, Phredward) have the same shape. Steel axe comes right after steel. Toolbelt and lab speed 1 and 2 come before blue, and Phredward adds "consider lab speed 3". AntiElitz's run pauses research after Car "to save resources" until the outpost runs.

### 6b. Rocket-silo closure in 2.1.24 (from `fd:technology.lua`)

Trigger techs (no lab time): steam-power (craft 50 iron plates), electronics (craft 10 copper plates), automation-science-pack (craft a lab), oil-processing (mine crude oil).

Lab techs, units × seconds:
- automation 10×10 r
- electric-mining-drill 25×10 r (not in the closure, but needed in practice)
- logistic-science-pack 75×5 r
- steel-processing 50×5 r
- radar 20×10 r
- logistics 20×15 r
- automation-2 40×15 rg
- advanced-material-processing 75×30 rg
- engine 100×15 rg
- fluid-handling 50×15 rg
- oil-gathering 100×30 rg
- plastics 200×30 rg
- sulfur-processing 150×30 rg
- advanced-circuit 200×15 rg
- chemical-science-pack 75×10 rg
- battery 150×30 rg
- modules 100×30 rg
- speed-module 50×30 rg
- productivity-module 50×30 rg
- flammables 50×30 rg
- concrete 250×30 rg
- logistics-2 200×30 rg
- railway 75×30 rg
- electric-energy-distribution-1 120×30 rg
- solar-energy 250×30 rg
- electric-energy-accumulators 150×30 rg
- advanced-oil-processing 75×30 rgb
- lubricant 50×30 rgb
- electric-engine 50×30 rgb
- robotics 75×30 rgb
- processing-unit 300×30 rgb
- low-density-structure 300×45 rgb
- advanced-material-processing-2 250×30 rgb
- rocket-fuel 300×45 rgb
- speed-module-2 75×30 rgb
- productivity-module-2 75×30 rgb
- production-science-pack 100×30 rgb
- utility-science-pack 100×30 rgb
- speed-module-3 300×60 rgbp
- productivity-module-3 300×60 rgbp
- rocket-silo 1000×60 rgbpy

### 6c. Optional techs: take or skip for the agent

| Tech | Cost | Runners | Agent | Why |
|---|---|---|---|---|
| steel-axe | Trigger: craft 50 steel | All | **Take** | Free; hand mining twice as fast |
| logistics (undergrounds, splitters) | 20×15 r | All | **Take** | Undergrounds give 3 belt tiles per action; it is in the closure anyway |
| research-speed-1 and 2 | 100 + 200 rg × 30 s (2.5 lab-h) | All | **Take before blue** | +50% on the remaining ~60 lab-h |
| toolbelt | 100 rg × 30 s (0.83 lab-h) | Zaspar, Nefrums | **Take** | +10 inventory slots means fewer chest trips, including for the silo's own materials (1000 steel and 1000 concrete alone are 20 slots) |
| fast-inserter | 30×15 r | All | **Take before the silo** | The silo feed needs 1.33 items/s per ingredient (10 per 7.5 s craft with 4 prod3), more than a basic inserter's ~0.83 items/s. Elsewhere a basic inserter beats a steel furnace's output (0.625 plates/s) and most assembler inputs `[INFERENCE]` |
| mining-productivity-1 | 250 rg × 60 s (4.2 lab-h) | Zaspar, Nefrums | Optional | +10% ore saves a few drills. It costs 500 packs. |
| effect-transmission (beacons) | 75 rgbp × 30 s | Zaspar (20 at the silo) | Optional, 4 at most | §7d |
| construction-robotics, worker-robots-speed | 100 rgb, 50 rgb | All | **Skip** | No ghosts, so robots have nothing to build |
| logistic-robotics | 250 rgb × 30 s | Not used | Skip | A logistic network still costs a roboport and chest per site. Not worth it for one player `[INFERENCE]`. |
| military, gun turret, heavy armor, walls, military science, landmines, explosives, cliff explosives | | DS runners | **Skip** | Peaceful. Explosives only lead to cliff explosives, so take them only if cliffs block the plan. |
| automobilism (car) | 100 rg × 30 s | Zaspar, Phredward | **Skip** | `fac` has no driving command; walking is 9 tiles/s (`running_speed = 0.15` tiles/tick) |
| circuit-network | 100 rg × 15 s | Zaspar (purple alarm) | Skip | Speaker and logic only |

How it applies to the agent: queue the whole research plan in a few early actions. `fac research` queues a tech's missing prerequisites ahead of it, as the tech screen does, but queues nothing when they don't all fit in the 7-slot queue or one is an unfinished trigger tech (protocol.md `research`, decision 63). An idle lab is lost research floor.

---

## 7. Factory sizes and the rocket finish

### 7a. Runner targets

| Item | Zaspar 2.x DS | Nefrums 1.x any% | AntiElitz/Phredward 1.1 DS | macros42 any% (0.17) |
|---|---|---|---|---|
| Labs | 32 (8×4), 64 at purple | 30 | 42 (14×3) | |
| Red / green assemblers | 10 / 12 | 9 / 10 | 10 / 11 | 8 / 10 |
| Blue assemblers | 14 | | | 18 |
| Red circuit assemblers | 24 (26 in the WR) | | 29 | |
| Purple / yellow assemblers | 14 / 12 | | | 16 / 15 |
| Rocket fuel assemblers | 14 | | | |
| Refineries / chem plants (first oil) | 10 / 4 | | 14 / 6 | |
| Oil yield | ≥1600%, about 12 pumpjacks | | ≥1600%, 12 to 14 pumpjacks | |
| Starting iron | About 75 drills (WR: 83) | | "420K+ and at least 80 iron miners" | |
| Outposts | 30-drill iron, then 120-drill iron and copper | | 40 copper drills | |
| Power | 60 engines, then a 40-boiler solid-fuel plant | | Up to 15 boilers early | |
| Silo | 4 prod3 plus 20 beacons | Prod3 in silo | | |

### 7b. How runners finish the rocket

1. Craft the silo by hand: 1000 steel, 1000 concrete, 100 pipe, 200 processing units, 200 electric engines (`fd:recipe.lua`). Buffer 200 electric engines ahead of time (Zaspar: "place a chest to buffer 200 electric engines for rocket silo later").
2. Make 4 prod3: 64 prod1 → 16 prod2 → 4 prod3. Zaspar: "Feed 80 blue and red circuits and 64 prod1s". Insert them as soon as the silo is placed.
3. Make 1000 concrete from 500 bricks, 100 iron ore and water, in an assembler 2 with water piped in (the water ingredient rules out assembler 1).
4. Carry ingredients into the silo by hand. JeHor's splits "Collect silo materials" and "Grab rocket supplies" come just before "Rocket Research".
5. Collect a fish.

Silo researched → launch took 1:48 (JeHor Any%), 2:35 (JeHor DS), 3:24 (Nefrums 1.1) and 6:17 (Krul87). Zaspar's WR end was ingredient-starved. Captions near 1:56:00: "I need about 1620 [LDS]... I have to go again" and "I cut one power pole", costing about 4 min.

### 7c. Silo throughput (2.1.24 numbers, `[INFERENCE]` arithmetic)

- Silo `crafting_speed` 1, rocket-part 3 s, 4 module slots (`fd:entity/entities.lua`).
- With 4 prod3 (speed −15% each), speed is 0.4, so 7.5 s per craft. 72 crafts take 540 s (9 min).

### 7d. Beacons at the silo (optional; `[INFERENCE]` arithmetic)

- A beacon has `distribution_effectivity` 1.5 and a per-beacon `profile` of 1/√n. Speed 1 is +0.2 per module (`fd:entity/entities.lua`, `fd:item.lua`).
- With 4 beacons of 2 speed1 each, the silo runs at 1.6 speed (1.875 s per craft), so 135 s for 72 crafts.
- With 20 beacons it runs at about 3.1 speed, so about 70 s.

For the agent, 4 beacons plus 8 modules is about 12 actions (3 min at `t_a` = 15 s) and saves about 6.75 min. It also needs effect-transmission (75 × 30 s, rgbp) and 4 × (20 green + 20 red circuits + 10 steel) per beacon. It is worth it only if purple is plentiful. 20 beacons are not worth it.

---

## 8. Hand-crafting strategy and the mall

What runners do:
- **Early game: everything by hand.** Every slide in Zaspar's guide lists a crafting batch, e.g. 44 burners plus 20 furnaces, or 15 drills plus 24 furnaces plus 2×50 belts.
- **"Stock up on intermediates before handcrafting (gears, wire, green chips, pipes)"** (Zaspar and Nefrums "Frequent mistakes"). The personal assemblers (2 gear, 2 wire) are hand-fed and looted, so the queue skips the intermediate time.
- **A mall appears at about 20 to 45 min** to unload the queue. JeHor's "Science Mall" comes at 21:39 and "Mall" at 41:03; Krul87's "Mall + science" at 39:31. It makes belts, inserters, gears, pipes, drills, then assembler 1 and 2, fast and long inserters, undergrounds, splitters and steam engines. Output chests are limited to 3 stacks.
- **Late game: bots build from blueprints**, the player only hand-crafts specialties: 20 beacons, 25 bots from frames, the silo.
- **Hand-feed scarce inputs from buffers:** 25 frames per yellow assembler, 500 steel for landmines, copper for batteries.

Hand-craft times, recursive including intermediates, character speed 1, from `fd:recipe.lua` `[INFERENCE: sum]`:

| Item | Craft s | Raw plates |
|---|---|---|
| burner mining drill | 4.0 | 9 iron, 5 stone |
| stone furnace | 0.5 | 5 stone |
| electric mining drill | 8.25 | 23 iron, 4.5 copper |
| assembling machine 1 | 6.75 | 22 iron, 4.5 copper |
| lab | 21.5 | 36 iron, 15 copper |
| inserter | 2.25 | 4 iron, 1.5 copper |
| steam engine / boiler / offshore pump | 7.0 / 3.0 / 3.0 | 31 iron / 4 iron + 5 stone / 7 iron |
| transport belt / underground (each) / splitter | 0.5 / 1.75 / 9.25 | 1.5 / 8.75 / 16 iron + 7.5 copper |
| red pack / green pack | 5.5 / 8.75 | 2 iron + 1 copper / 5.5 iron + 1.5 copper |

How it applies to the agent:
- **The agent's bottleneck is actions, not the craft queue** `[INFERENCE]`. An electric drill takes 8.25 s to craft and 1 to 2 actions (15 to 30 s) to place. The queue therefore keeps up with placement almost always. Only labs (21.5 s), splitters and steam engines can outrun placement.
- **No mall.** A mall costs dozens of placements and saves craft time the agent does not lack.
- **Build buffers that cut trips.** Use plate chests, plus gear and circuit chests fed by assemblers. Then `take` one chest for thousands of items and run one `craft --count` for the whole batch.
- **Batch crafts by phase.** Order each batch so the first building to place finishes first.
- Automate in assemblers only what the queue can't sustain (science packs, circuits for science, steel) or can't make by hand (anything with fluids).

---

## 9. Seed and map selection

Runner criteria for DS:

| Criterion | Zaspar 2.x | Phredward/AntiElitz 1.1 |
|---|---|---|
| Biters | No nests near the start | |
| Trees | "High number of trees" (wood for poles) | |
| Starting patches | "relatively close together but non-overlapping", open space at spawn | "close but not overlapping" |
| Starting iron | Fits about 75 drills (2.5 belts) | "420K+ and support at least 80 iron miners", 40 drills on copper |
| Secondary iron | Small, about 30 drills | One close, large outpost per ore |
| Tertiary | Large iron and large copper, about 120 drills each | |
| Oil | About 1600% total yield (about 12 pumpjacks), up to 2000% | At least 1600% |
| Search time | "usually... in 10 minutes of searching" | Map selection is practised as a skill |

Signs of a bad map in Zaspar's WR commentary: few coal rocks ("Guess we're going to have to live on just stone"), a far coal patch, trees on the smelter site ("rainforest"), a badly placed stone patch, and a low first oil patch ("only 780... it's 1.4 [k]. That's enough").

How it applies to the agent: we can't reroll, so treat the seed as a route problem `[INFERENCE]`:
- **Pre-scout each seed once**, with the mod or a human, and give the agent coordinates. It needs the huge rocks with coal, iron, copper, coal and stone patch centres and edges, the nearest water to the coal, a clear base rectangle, and oil patches with yields.
- **Rank build sites by walking distance.** Running speed is 9 tiles/s, so a 100-tile detour costs 11 s, about one action. Distance matters less than action count, but repeated haul trips add up.
- **Oil yield sets refinery count.** Our lean plan needs about 300 to 600% total yield (§10b), not the runners' 1600%.
- **Clear trees only where you build.** Each tree is one `mine` action (1.1 s, 0.55 s with the steel axe) and gives 4 wood. 20 to 30 trees cover all small-pole needs, since 1 wood makes 2 poles (`fd:recipe.lua`). A site that needs 100 trees cut costs about 25 min at `t_a` = 15 s.

---

## 10. Planning numbers (2.1.24)

### 10a. Machine rates

| Entity | Rate | Source |
|---|---|---|
| Character | Mining speed 0.5 (ore 2 s each, 1 s with the steel axe); running 0.15 tiles/tick = 9 tiles/s; reach 10; resource reach 2.7; inventory 80 slots | `fd:entity/entities.lua` |
| Burner drill | 0.25 ore/s, 150 kW (one coal per 26.7 s, about 6.7 ore per coal) | `fd:entity/mining-drill.lua` |
| Electric drill | 0.5 ore/s, 90 kW, 3 module slots | same |
| Stone / steel furnace | Speed 1 / 2, 90 kW each: 0.3125 / 0.625 plates/s; steel 16 s / 8 s | `fd:entity/entities.lua`, `fd:recipe.lua` |
| Assembler 1 / 2 | Speed 0.5 / 0.75, 75 / 150 kW; asm2 has 2 module slots | same |
| Lab | Speed 1, 60 kW, 2 module slots | same |
| Boiler / steam engine | 1.8 MW, one coal per 2.22 s at full load / 0.9 MW (2 engines per boiler) | same |
| Offshore pump | 1200 water/s (enough for 20 boilers) | same |
| Pumpjack | 10 crude/s at 100% yield | `fd:entity/resources.lua` (`normal = 300000`) |
| Refinery (advanced oil) | 100 crude + 50 water → 25 heavy + 45 light + 55 petroleum per 5 s | `fd:recipe.lua` |
| Chem plant | Plastic 20 petroleum + 1 coal → 2 bars per 1 s | same |
| Silo | Speed 1, 4 module slots, 100 parts, part 3 s | `fd:entity/entities.lua` |

### 10b. Run totals `[INFERENCE: recursive expansion of fd:recipe.lua, no productivity]`

| Need | Iron plates | Copper plates | Other |
|---|---|---|---|
| Science for the silo closure (5960 r, 5785 g, 3350 b, 1600 p, 1000 y) | 200.9k | 120.3k | 28.4k plastic, 18.7k stone, 16.7k acid, 5k lubricant; ~19.4k steel inside the iron figure (rails and electric furnaces for purple, engines for blue) |
| Rocket silo building | 12.1k | 8.6k | 1000 concrete, 800 plastic, 3k lubricant |
| 100 rocket parts, no productivity | 34.0k | 60.0k | 110k light oil, 9k plastic |
| 72 crafts with 4 prod3 | 24.5k | 43.2k | 79.2k light oil, 6.5k plastic |
| The 4 prod3 modules | 3.6k | 6.6k | 1.2k plastic |

Total with prod3 is about 241k iron plates, 179k copper plates and about 21k steel.

Steel is the costliest plate per unit: 16 s per plate, 20% of all smelting time ([production-chains.md §1](production-chains.md)). It takes 310k furnace-seconds at speed 1 for science alone, i.e. 43 steel-furnace-hours. Purple is the big consumer: 30 rails per 3 packs, and each electric furnace needs 10 steel.

Oil needs about 490k crude in total. Over 5 h that is about 27 crude/s, i.e. 270% total yield and 1.4 refineries at 20 crude/s each.

How it applies to the agent: production machines are sized by the run length you can afford, not by human practice. Spreading these totals over a 6 h production window gives about 11 iron/s (22 drills, 18 steel furnaces) and 8 copper/s (16 drills) `[INFERENCE]`. Production is back-loaded (purple, yellow, rocket), so build the last third of mining during the blue phase.

### 10c. Trade-off between factory size and run time `[INFERENCE, rough model]`

Let the work be K machine-hours, so a run of D hours needs about N = K/D machines at full use. Placing them costs N × a actions, where a is about 2.5 actions per machine (machine, inserters, share of poles and pipes).

- Rough K from §10b: about 230 drill-h, 240 furnace-h (iron, copper, steel), about 150 assembler-h and 42 lab-h (speed 1.5). That is about 700 machine-hours.
- Machines are idle until their tier starts, so the effective K roughly doubles.
- D then satisfies D ≈ C + N × a × t_a, where C is the unavoidable waiting time (research floor, oil trip, silo), about 2 h.
- With K ≈ 1,400 machine-hours, a = 2.5 and C = 2 h, that is D = 2 + 14.6 / D at `t_a` = 15 s, so D ≈ 5 h, and D ≈ 6.5 h at `t_a` = 30 s. The route in §11 lands near 7 h at 15 s because its stages run one after another and each waits on its own pack supply, while the model treats the whole factory as one pool.
- The optimum has N falling with √t_a. A slower agent should build fewer, better-fed machines and wait longer, not attempt runner-sized blocks.

---

## 11. Proposed route for the factobot agent

Assumptions: `t_a` = 15 s per action; peaceful; one pre-scouted seed; no blueprints; every entity is placed by hand. Times are game time from the first tick. "Stretch" assumes about 7 s per action and "Fallback" about 30 s. Both columns are `[INFERENCE]`, scaled from the action counts. Fixed waits (the 33 min silo research in step 16, the 9 min silo craft in step 17) do not scale with action time, so those two steps add the same time in every column; earlier steps still scale whole, research floors included. Action counts are my estimates.

| # | Step | Actions (approx.) | Target (`t_a` 15 s) | Stretch | Fallback |
|---|---|---|---|---|---|
| 0 | `observe`, `map`; read the seed plan | 2 | 0:01 | 0:00:30 | 0:01 |
| 1 | **Rocks.** Walk to the nearest huge rock(s) between iron and coal; mine 2 to 3 (6 s each) for ~100 stone and ~100 coal. Mine 3 to 5 trees on the way (wood for poles). | 8 | 0:03 | 0:02 | 0:05 |
| 2 | **First iron.** Place the starting burner drill on the iron edge with the starting furnace in front; insert 10 coal into each. Hand-mine 20 to 30 iron ore (one `mine --count`) into a second furnace for the first plates. Craft furnaces. | 8 | 0:06 | 0:04 | 0:11 |
| 3 | **Burners.** Craft and place 6 to 8 iron burner/furnace pairs, 2 copper pairs and 3 burner drills on coal, each into a chest. A pair burns 3.33 coal/min and a coal drill into a chest nets about 13 coal/min, enough for 3.8 pairs, so 3 coal drills carry 11 pairs; one self-feeding coal pair (two drills facing each other) nets about 25 coal/min, 7.5 pairs, too few. Fuel with 20 to 50 coal each. Steam power (50 plates) and electronics (10 copper plates) trigger on their own. | 40 | 0:16 | 0:09 | 0:30 |
| 4 | **Power and lab.** Craft offshore pump, boiler, 1 to 2 engines, ~15 small poles, 1 lab and exactly 10 red packs. Place power at the water nearest the furnace column and run poles to a lab beside the furnaces. Fill the boiler with 50 coal (11 min at the early ~300 kW load). Queue research: automation, electric-mining-drill, logistics, logistic-science-pack, steel-processing. | 25 | 0:22 | 0:13 | 0:42 |
| 5 | **Mini red science (milestone 1).** Place, beside the furnace columns: 1 gear assembler (inserter from an iron furnace), 2 red assemblers (gears in by inserter from the gear assembler, copper in by inserter from a copper furnace), red assemblers → inserter → lab → inserter → lab 2. Hand-craft 2 more labs. | 20 | **0:35** | 0:20 | 1:05 |
| 6 | **Electric mining.** After electric-mining-drill: 10 iron drills each dropping into a stone furnace, 6 copper the same. Each furnace pair has an inserter to a shared output chest and a coal chest + inserter. Take the coal from the coal drills' chests. Pick up the burners once replaced (1 action each, back to the inventory). | 70 | 1:00 | 0:35 | 1:55 |
| 7 | **Coal and power.** 4 to 6 electric drills on coal outputting onto one short belt (undergrounds where possible) that runs past the boiler row with inserters. Grow to 4 boilers and 8 engines (7.2 MW). If coal and water are far apart, chest-fed boilers plus one 1600-coal haul per boiler-hour. | 30 | 1:10 | 0:40 | 2:10 |
| 8 | **Steel axe and steel.** Steel-processing done: put 50 iron plates into each of 5 furnaces → 50 steel → steel axe. Then 4 steel furnaces chain-fed (iron furnace → inserter → steel furnace → inserter → chest). | 15 | 1:15 | 0:45 | 2:20 |
| 9 | **Green (milestone 2).** Assemblers: cable → circuit (direct), circuit + gear → inserter assembler, gear → belt assembler, inserter + belt → 2 green assemblers → labs. Inputs come from the plate chests (agent hauls) or inserters from furnaces. Labs to 8. Queue in this order, topping up as each finishes, since the queue holds 7 including the running one: automation-2, toolbelt, research-speed-1 and 2, advanced-material-processing, engine, fluid-handling, oil-gathering, radar. | 45 | **1:45** | 1:00 | 3:20 |
| 10 | **Scale smelting to the blue target.** Iron to ~20 drills, copper to ~14, steel to ~8 steel furnaces. Replace stone furnaces with steel furnaces as steel allows (same 90 kW, twice the output per fuel insert). Labs to 12 to 16 and upgrade science to assembler 2. | 90 | 2:30 | 1:25 | 4:45 |
| 11 | **Oil.** Pumpjacks on the nearest patch, about 300 to 600% total yield. Pipe-to-ground (11 tiles per 2 actions) to 2 refineries (basic first, advanced with cracking after research, step 13), then 2 to 3 plastic chem plants (coal from a chest), 1 sulfur and 1 acid. The first powered pumpjack to extract crude triggers oil-processing. Queue in this order, topping up as each finishes, since the queue holds 7 including the running one: plastics, advanced-circuit, sulfur-processing, chemical-science-pack, battery, modules, speed-module, productivity-module. | 50 | 3:00 | 1:45 | 5:45 |
| 12 | **Blue (milestone 3).** 4 to 6 red-circuit assemblers (circuits and plastic from chests or inserters), 3 engine assemblers (steel, gears, pipes), 6 blue assemblers 2 → labs. | 40 | **3:30** | 2:00 | 6:40 |
| 13 | **Back-load mining.** Iron to ~26 drills, copper to ~18, steel furnaces to ~12, stone 2 drills + brick furnaces. Queue in this order, topping up as each finishes, since the queue holds 7 including the running one: advanced-oil-processing, lubricant, electric-engine, robotics, processing-unit, low-density-structure, advanced-material-processing-2, logistics-2, railway, production-science-pack, utility-science-pack, concrete, flammables, rocket-fuel, speed-2, productivity-2, EED1, solar, accumulators, speed-3, productivity-3, rocket-silo. When advanced-oil-processing finishes (it also unlocks both cracking recipes), switch the refineries to advanced oil only together with cracking: advanced oil makes 5 heavy, 9 light and 11 petroleum per second per refinery, and the one later heavy-oil sink, lubricant for electric engines, takes a small share of it, so without cracking heavy fills the refinery's 100-unit output box and the refinery stops with `full_output` (seen in a test world after 4 crafts, light and petroleum drained). For 2 refineries: 1 heavy-cracking chem plant (40 heavy + 30 water → 30 light in 2 s, so 20 heavy/s, enough for 4 refineries) and 2 light-cracking plants (30 light + 30 water → 20 petroleum in 2 s, 15 light/s each, for the 18 light/s plus 7.5 from cracking), water piped to each. Take lubricant's heavy off the line before the heavy cracker and rocket fuel's light before the light crackers. | 70 | 4:15 | 2:25 | 8:10 |
| 14 | **Purple and yellow (milestone 4).** Purple: 1 to 2 electric-furnace assemblers, 2 prod1, 1 rail, 4 purple asm2. Yellow: 1 lubricant chem plant, 2 electric-engine, 2 frame (batteries from a chem plant), 3 LDS, 2 processing-unit, 3 yellow asm2. Labs to 20 to 24. Hand-feed frames into yellow at first, as Zaspar does. | 90 | **5:30** | 3:10 | 10:30 |
| 15 | **Rocket inputs.** 2 to 3 rocket-fuel asm2 (solid fuel from light oil plus light oil), raise LDS and processing units to cover 720 each. Build up a 200 electric engine buffer and a 1000 steel buffer in chests for the silo craft. Make 64 prod1 → 16 prod2 → 4 prod3. Make 1000 concrete (assembler 2 with water piped in). Mine 1 fish. | 40 | 6:15 | 3:35 | 12:00 |
| 16 | **Silo.** While the rocket-silo tech runs (20 labs × 1.5 → 33 min), put the silo's materials in your inventory and the rocket inputs in chests where it will stand. The tech unlocks the silo recipe, so craft the silo the moment it finishes, place it, insert the 4 prod3, then feed 720 each of processing units, LDS and rocket fuel from chests by one fast inserter (or two basic) per ingredient (the silo holds at most 104, 54 and 24 at a time, so carried stock goes in over about 36 rocket fuel inserts), then the fish. No landing pad. | 15 | 6:50 | 4:10 | 12:35 |
| 17 | **Launch.** 72 crafts × 7.5 s = 9 min, then launch. | 2 | **7:00** | 4:20 | 12:45 |

Total about 660 actions. At 15 s that is about 2.75 h of pure action time inside a 7 h run. The rest is research floor, crafting and waiting `[INFERENCE]`.

Rules for every step:
- **One action, maximum work.** Use `mine --count` up to 1000, `craft --count` for whole batches, and `insert` with the default count, which inserts everything. Fill fuel slots to 50.
- **Place machines in chains inside a cell, and belt between cells**: one `place --to` call per straight run, instead of a haul trip by hand on every visit for the rest of the run.
- **Batch the walking.** One loop per phase: take from output chests, craft while walking, insert into input chests and refuel.
- **Never let labs idle.** The research queue is cheap to keep full; it holds 7 technologies, the running one included, so top it up each time one finishes.
- **Check the "first automated research" milestones** with `inspect` on labs rather than assuming they started.

---

## 12. Open questions and unverified items

- **JeHor Any% enemy settings.** UNVERIFIED. The resource tab is confirmed from the frame; the enemy tab was not shown.
- **1.1-only claims.** The Nefrums, Phredward, Mazmot and macros42 counts and queues are 1.x. Where I cite them for structure (burner counts, map criteria, research shape), they are UNVERIFIED-2.x. The 2.x tech costs above replace their numbers.
- **The size and time model in §10c and the route times in §11** are my estimates. They need calibrating against factobot playtest action latency.
