# Speedrun research: helping an agent reach the rocket fast

Side project, separate from the scored benchmark: how fast can an agent launch a rocket through `fac` when it is given as much Factorio knowledge as we can compile? Everything here targets Factorio 2.1.24, base game, freeplay, peaceful with no enemy bases, and the agent's real limits: one `place` per entity, no blueprints or ghosts, reach and walking enforced, and 5 to 30 s of game time lost per command while the model thinks.

This folder is briefing material for an "assisted" agent profile. Scored benchmark runs get no skill and none of this research (decisions 46 and 48); keep this out of their prompts. The agent-facing version is the skill [`skills/factorio-rocket/`](../skills/factorio-rocket/SKILL.md), which `playtests/rocket.md` uses (decision 77). The skill holds nothing about any map; the seed notes below stay here, for people.

Research date 2026-11-02. Game numbers are pinned to wube/factorio-data commit `acf5a34` (tag 2.1.24). Tags in the files: `[INFERENCE]` is a derivation, `UNVERIFIED` a claim nobody checked, `UNVERIFIED-2.x` a 1.1-era claim not confirmed for 2.x.

## Files

| File | What it answers |
|---|---|
| [speedrun-routes.md](speedrun-routes.md) | How 2.x record runners (Zaspar 1:59:01, JeHor, Krul87, seb351, Nefrums) play, their splits and build order, and a 17-step route adapted to this agent with target times |
| [early-game.md](early-game.md) | The first hour: start inventory, character stats, hand-mining and rock yields (measured in game), burner economy, trigger techs, first power, an opening sequence with the math |
| [production-chains.md](production-chains.md) | Every recipe on the rocket path, machine stats, oil and power, ratio tables per pack/s, total raw cost of the run, a staged minimal factory |
| [tech-tree.md](tech-tree.md) | The 44 required techs in order, which optional techs pay off, lab-count formula, a research queue in batches of at most 7, issued as slots free |
| [layout-and-logistics.md](layout-and-logistics.md) | Belts, inserters, drills, poles, fluids and port positions in fac's direction convention, a mistakes checklist mapped to `inspect` fields, small ASCII layouts to place entity by entity |

## Player profile: the rules that save the most time

Condensed from the five files; each links to the detail.

1. **Count commands, not just ticks.** At 10 to 15 s per command the opening is limited by how many commands it takes, not by resources ([early-game §summary](early-game.md)). Every command should do as much as possible: `mine --count` in the hundreds, `craft --count` whole batches, `insert` full stacks. Issue `place`, `insert`, `take` and `craft` while a `mine` job runs.
2. **Mine huge rocks first.** 6 s by hand for about 37 coal and 37 stone, 12.5 times faster than coal ore for coal and 25 times for all items. Big rocks give 20 stone in 4 s (4 furnaces). Rocks only show up in `observe`, not `map` ([early-game §3-4](early-game.md)). Seed coordinates are below.
3. **Unlock the 2.x trigger techs on purpose.** Smelt 10 copper plates for electronics (circuits, inserter, lab, small pole), 50 iron plates for steam power, craft 1 lab for red packs. 1.1 guides skip this step ([tech-tree](tech-tree.md)).
4. **Direct insertion inside a cell, belts between places.** Drill into furnace, furnace to inserter to assembler, assembler to lab, lab to lab. Between cells use a belt: `place --to` lays a whole straight run in one call, so a belt costs one command per straight run plus its walking time (decision 52; [the skill](../skills/factorio-rocket/SKILL.md) rule 1).
5. **Build each cell from one standing spot.** Build and interact reach are 10 tiles, so one `walk` then 10 to 30 `place` calls ([layout §1, §9](layout-and-logistics.md)).
6. **Hand-craft buildings, then add a gear and a circuit assembler.** One `craft` call queues minutes of work that runs while walking. Put a gear and a circuit assembler at the base early and take from them, so drills and assemblers craft from intermediates instead of plates ([the skill](../skills/factorio-rocket/SKILL.md), the mall). Never hand-craft science beyond the 10 red packs the first research needs: each hand-crafted pack delays its milestone by one machine pack (decision 43) ([speedrun-routes](speedrun-routes.md)).
7. **Keep the burner phase small** (8 to 12 drill-furnace pairs) and get electric mining drills right after automation. A pair stalls after 6.7 min when its furnace output fills, and each pair costs about 3.6% of the agent's time in upkeep ([early-game §5](early-game.md)).
8. **Steam, one pump, chest-fed boilers.** In 2.x one water makes 10 steam, so one offshore pump feeds 200 boilers; 1.1 guides that say 1:20:40 are wrong. A boiler at full load burns 50 coal in 111 s, so feed boilers from a coal chest or belt early ([production-chains §5](production-chains.md); `data/changelog.txt` 2.0.7 line "1 Water will now produce 10 Steam").
9. **Research speed 1 and 2 early.** Two calls for +50% lab speed, which saves about 75k of the 224k mandatory lab-seconds ([tech-tree §summary](tech-tree.md)).
10. **Oil gates blue.** `oil-processing` is a trigger: it fires when a pumpjack extracts crude, and plastics and everything after it cannot be queued before that. Research `oil-gathering` early and fill the wait with oil-free techs. Switch to advanced oil processing right after blue (2.17 times the petroleum per crude) ([tech-tree](tech-tree.md), [production-chains §1](production-chains.md)).
11. **Steel early.** Steel axe is a free trigger (craft 50 steel) that doubles hand-mining speed, and steel dominates purple-pack cost ([tech-tree](tech-tree.md), [production-chains](production-chains.md)).
12. **Build purple before yellow,** so the two module-3 techs research while yellow is being built ([tech-tree](tech-tree.md)).
13. **Four productivity-3 modules in the silo:** 72 rocket-part crafts instead of 100, and the techs are mandatory anyway ([production-chains §1](production-chains.md)).
14. **Size the factory to the action budget.** Runners place 2,000+ entities with bots; this agent cannot. A base of about 60 drills, 50 furnaces, 50 assemblers and 20 labs, roughly 660 commands, targets a rocket around 7 game hours at 15 s per command. That estimate is uncalibrated until playtests measure real command latency ([speedrun-routes §10-11](speedrun-routes.md), [production-chains §1 item 8](production-chains.md)).
15. **Launch with a fish, no landing pad.** Observed in a factobot test world below.

## Seeds 1 to 5 (the Inspect task's seeds)

Scanned in factobot test worlds on 2026-11-02 with factobot's own map settings. Coordinates are map tiles from spawn (0, 0).

- **One terrain.** Water, rocks and spawn terrain (red desert, no trees within 40 tiles) are the same on all five seeds. Nearest water is at (55, 0) on every seed.
- **Huge rocks** within 150 tiles, all seeds: (-2, -45), (40, -34), (-68, -66), (57, 25), (59, 38), (-102, -2). Seeds 1 and 2 also have a cluster at (-100 to -109, -6 to 4).
- **Big rocks** nearest: (20, -24), (31, -28), (36, -34), (50, -32). Big sand rocks at (19, 39) and (18, 40).
- **Nearest ore tile per seed** (ore layouts pair up: seed 2 = 3, seed 4 = 5):

| Seed | Iron | Copper | Coal | Stone |
|---|---|---|---|---|
| 1 | (-39, -3), 38 tiles | (-20, 74), 77 | (31, 50), 59 | (-63, 11), 63 |
| 2, 3 | (-65, 16), 66 | (4, 41), 41 | (-54, 3), 53 | (-27, 29), 39 |
| 4, 5 | (34, -33), 47 | (11, -24), 26 | (34, -62), 70 | (-64, -18), 65 |

- **Crude oil.** This scan found none within 320 tiles on any of the five seeds, but a harness scan of seed 1 on 2026-11-03 (chunks generated with `request_to_generate_chunks` out to about 1,000 tiles, then read through `fac map`) found an 11-well field of 1,604% total yield centered at (278, -69), about 286 tiles from spawn (nearest well 278), and a `walk` from spawn reaches it in one call. Treat the "no oil" result as wrong for seed 1 and unchecked for seeds 2 to 5. `walk` covers 500 tiles per call at about 8.9 tiles/s.

[early-game.md §4](early-game.md) has the same census for ten more seeds.

## Checked in game during this research

| Question | Result |
|---|---|
| Does a fish launch need a cargo landing pad? | No. A silo with 100 parts, 1 raw fish and no pad anywhere launched and the game recorded victory (`finished_but_continuing`). The script call `launch_rocket()` also launched an empty rocket, so the payload rule is a GUI check. |
| How long is the research queue? | 7. The eighth `fac research` call is rejected with "the research queue would not take ...". |
| Water to steam ratio in 2.1.24 | 1 water to 10 steam (`data/changelog.txt`, 2.0.7). |

## Benchmark finding: seeds 1 to 5 are near-duplicates

Small consecutive seeds generate the same terrain and near-identical rocks, and ore layouts repeat in pairs (2 = 3, 4 = 5, and in [early-game.md](early-game.md)'s wider scan 6 = 7, 8 = 9). Decision 44's five seeds therefore give three ore maps on one terrain. Large seeds (1000, 123456, 987654321 and others) all differed. Spreading the seeds, for example to large random u32 values, would restore the variation decision 20 assumes.
