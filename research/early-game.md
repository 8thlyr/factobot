# Early game (first 30 to 60 minutes): Factorio 2.1.24 base, for the factobot agent

Research date 2026-11-02. Game data comes from wube/factorio-data at commit `acf5a342afcb66c066b9d88d202e8622112da117` ("added version 2.1.24", 2026-10-27; `base/info.json` says version 2.1.24) unless a line says otherwise. Links below point at that commit. Freeplay start items come from the 2.1.24 game install (`data/base/script/freeplay/freeplay.lua`), because factorio-data does not ship scenario scripts. Lines marked "measured" come from my own runs of the 2.1.24 headless binary with a throwaway counting mod (method in section 12). `[INFERENCE]` marks my derivations. `UNVERIFIED` marks claims I could not check. `UNVERIFIED-2.x` marks 1.1-era claims I could not confirm for 2.x.

Unless stated otherwise, "L" below is the agent's game-time cost per command (model thinking plus round trip), assumed to be 10 s. The task brief puts it at 5 to 30 s.

## Summary: most valuable takeaways, ranked by time saved

1. **The opening is bound by action count, not by resources.** The shortest path to milestone 1 (first research with an assembler-made red pack) needs about 130 iron plates, 36 copper plates, a few dozen stone, a little coal and about 77 commands. At L = 10 s, the commands alone take about 13 minutes, while the materials could be hand-mined in under 6 minutes [INFERENCE, section 9]. Batch every command: `mine --count 200`, `insert` 50 coal at once, `take` 100 plates at once. Issue `place`, `insert`, `take` and `craft` while a `mine` job runs, because those commands do not use the body ([protocol](../docs/protocol.md)).
2. **Mine huge rocks first.** A huge rock takes 6 s by hand (measured 361 ticks) and drops 24 to 50 stone plus 24 to 50 coal, about 74 items. Coal ore takes 2.02 s per item. For coal alone the rock is 12.5 times faster, and counting all items 25 times faster. Every map I generated had a huge rock within 35 to 67 tiles of spawn (section 4).
3. **2.x gates the early recipes behind trigger techs.** Smelting 50 iron plates unlocks pipe, boiler, steam engine and offshore pump. Smelting 10 copper plates unlocks copper cable, circuits, inserter, lab and small pole. Crafting 1 lab unlocks the red pack recipe. In 1.1 all of these were available from the start, so 1.1 guides skip this step. Smelt copper early; the lab cannot be crafted without circuits.
4. **Coal limits the burner phase.** A burner drill plus its furnace burns 3.33 coal per minute. One coal drill emptying into a chest nets 12.75 coal per minute, which covers about 3.8 iron or copper pairs. Fill each fuel slot with a whole stack (50 coal, 22 minutes for a drill) so one `insert` lasts a long time.
5. **A drill-to-furnace pair stalls after 6.7 minutes** if nobody empties it, because the furnace output slot holds 100 plates. At L = 10 s, upkeep costs about 3.6% of the agent's time per pair, so 10 pairs eat about 36% [INFERENCE]. Keep the burner phase small, roughly 8 to 12 pairs, and move to electric drills early.
6. **Boilers burn coal fast.** At full load (1.8 MW) a boiler burns 27 coal per minute, so one stack lasts 111 s. At early loads (one lab plus one assembler, 135 kW) a stack lasts about 25 minutes. Before load grows, put a chest of coal and a burner inserter in front of each boiler. In 2.x one offshore pump feeds 200 boilers (1:200:400), so never build a second pump for power.
7. **Move power, not items.** A line of small poles is one `place --to` call with `--spacing 7`, and so is a straight belt run, plus the walking time (decision 52). For one-off loads carrying is cheaper still: the 80-slot inventory holds 8000 plates, and `walk` reaches 500 tiles in one command.
8. **Get electric mining drills soon after automation.** Electric mining drill research costs 25 red packs × 10 s, so it can also serve as the first research run on assembler-made red packs. An electric drill mines twice as fast as a burner drill (0.5/s), uses 3.3 times less fuel per ore, and needs no refuel commands.
9. **The steel axe doubles hand-mining speed** (character mining speed 0.5 to 1.0). It costs 50 steel plates crafted (250 iron plates, 800 furnace-seconds) after steel processing (50 red). Worth it only while the agent still hand-mines a lot.
10. **Trees are action-inefficient fuel.** Each tree needs its own `mine` command and yields 4 wood (8 MJ). A single `mine --count 50` on coal yields 200 MJ. Use trees only for pole wood: 1 tree makes 8 small poles.

---

## 1. Starting state in 2.1.24 freeplay

| Item | Count | Notes |
|---|---|---|
| iron-plate | 8 | Not enough for a burner drill (needs 9). |
| wood | 1 | 2 MJ of fuel, or enough for 2 small poles. Keep it for poles. |
| burner-mining-drill | 1 | |
| stone-furnace | 1 | |
| pistol | 1 | Useless in peaceful mode. |
| firearm-magazine | 10 | Useless in peaceful mode. |

Source: `created_items` in `data/base/script/freeplay/freeplay.lua` (2.1.24 install, lines 4 to 13). With the crash site on, freeplay moves `crashed_ship_items` (8 firearm magazines) and `crashed_debris_items` (8 iron plates) out of the player's inventory into the wreck (lines 24 to 36 and 84 to 86). The total is therefore the same with or without the wreck. The wreck parts themselves are entities with no items (`core/lualib/crash-site.lua`, `default_ship_parts`). factobot turns the wreck off and inserts `get_created_items` into the agent's body ([decisions.md row 27](../docs/decisions.md), the freeplay `get_created_items` call in `mod/factobot/agent.lua`), so the agent holds all 8 plates from tick 0.

**Agent:** the first useful action is to get coal and stone. The kit already contains one drill and one furnace, which make one pair once fuelled.

## 2. Character stats

| Stat | Value | Source |
|---|---|---|
| Mining speed | 0.5, so ore (mining time 1) takes 2 s. Measured 121 ticks per ore (2.02 s, 0.495 ore/s). | [entities.lua L976][char-mine]; measured |
| Running speed | 0.15 tiles/tick in the prototype. Measured 8.906 tiles/s over the first 5 s on grass (8.86 tiles/s over 10 s with a small detour). The wiki says 8.9 tiles/s. | [entities.lua L732][char]; [wiki Player](https://wiki.factorio.com/Player) |
| Tile speed modifiers | Grass, sand and dirt 1.0. Shallow water 0.8, mud water 0.7, stone path 1.3, concrete 1.4, refined concrete 1.5. | [tiles.lua L1161, L1972, L2250](https://github.com/wube/factorio-data/blob/acf5a342afcb66c066b9d88d202e8622112da117/base/prototypes/tile/tiles.lua#L1161) |
| Build distance | 10 | [entities.lua L719][char] |
| Reach (interact: insert, take, open) | 10 | [entities.lua L721][char] |
| Resource reach (ore, trees, rocks) | 2.7 tiles to the collision box | [entities.lua L725][char]; factobot measures distance to the box (`mine` in `agent.lua`, against `resource_reach_distance`) |
| Item pickup / loot pickup | 1 / 2 | [entities.lua L722-723][char] |
| Main inventory | 80 slots | [entities.lua L718][char] |
| Hand-craft speed | 1 (recipe seconds are real seconds). No base technology changes it. | `character-crafting-speed` appears in no base technology ([technology.lua][tech]) |
| Health | 250 | Irrelevant in peaceful mode. |

What changes these stats in base 2.x (checked by grepping every `character-*` modifier in [technology.lua][tech]):

| Upgrade | Effect | Cost | Source |
|---|---|---|---|
| Steel axe (trigger tech) | `character-mining-speed` +1, so mining speed becomes 0.5 × (1 + 1) = 1.0: ore 1 s, huge rock 3 s | Craft 50 steel plates. Prerequisite: steel processing (50 red × 5 s). | [technology.lua L2007][tech-axe] |
| Toolbelt | +10 inventory slots | 100 × (red + green), 30 s each | [technology.lua L2528][tech-tb] |
| Modular / power / power MK2 armor | +10 / +20 / +30 slots | Mid-game | [item.lua L3645-3725](https://github.com/wube/factorio-data/blob/acf5a342afcb66c066b9d88d202e8622112da117/base/prototypes/item.lua#L3645) |
| Exoskeleton equipment | +30% movement, 200 kW | Needs an armor grid and power. Not early game. | [equipment.lua](https://github.com/wube/factorio-data/blob/acf5a342afcb66c066b9d88d202e8622112da117/base/prototypes/equipment.lua) |

Stack sizes that matter early: ore, coal and stone 50; wood, plates and gears 100; circuits, cable and red packs 200 ([item.lua][item]). Full inventory: 80 × 50 = 4000 ore, or 8000 plates.

**Agent:** a `mine` job fails when the inventory fills, so check free slots before `--count 1000`. A resource 2.7 tiles away needs a `walk` first. Buildings can be placed and fed from up to 10 tiles, so stand at the edge of the patch and build around yourself while a long `mine` job runs.

## 3. Hand-mining rates

Hand time = mining_time / 0.5. Measured times agree within 1 tick, with 1 extra tick per repeated ore cycle.

| Target | mining_time | Hand time | Yield | Items/s | Fuel gathered | Source |
|---|---|---|---|---|---|---|
| Iron, copper, coal, stone ore | 1 | 2.0 s (measured 2.02 s) | 1 | 0.495 | Coal: 1.98 MW | [resources.lua L79-135][res] |
| Tree (living) | 0.55 | 1.1 s (measured 66 ticks) | 4 wood | 3.64 | 7.27 MW | [trees.lua L4881][trees] |
| `dry-tree` | 0.5 | 1.0 s | 4 wood | 4.0 | 8 MW | [trees.lua L4987](https://github.com/wube/factorio-data/blob/acf5a342afcb66c066b9d88d202e8622112da117/base/prototypes/entity/trees.lua#L4987) |
| Dead trees (`dead-tree-desert`, `dead-grey-trunk`, `dead-dry-hairy-tree`, `dry-hairy-tree`) | 0.5 | 1.0 s | 2 wood | 2.0 | 4 MW | [trees.lua L5084-5412](https://github.com/wube/factorio-data/blob/acf5a342afcb66c066b9d88d202e8622112da117/base/prototypes/entity/trees.lua#L5084) |
| Big rock | 2 | 4.0 s (measured 241 ticks) | 20 stone (fixed) | 5.0 | none | [decoratives.lua L4475][bigrock] |
| Big sand rock | 2 | 4.0 s | 19 to 25 stone (mean 22) | 5.5 | none | [decoratives.lua L5092][sandrock] |
| Huge rock | 3 | 6.0 s (measured 361 ticks) | 24 to 50 stone + 24 to 50 coal (mean 37 + 37). One sample: 46 stone + 24 coal. | 12.3 (6.2 coal/s) | 24.7 MW | [decoratives.lua L4310][hugerock] |
| Fish (in water) | 0.4 | 0.8 s | 5 raw fish | | | [entities.lua L1197-1200](https://github.com/wube/factorio-data/blob/acf5a342afcb66c066b9d88d202e8622112da117/base/prototypes/entity/entities.lua#L1197) |

Medium, small and tiny rocks (and sand variants) are `optimized-decorative`, not entities. They cannot be mined and yield nothing ([decoratives.lua L4664-5410][rocks]).

Fuel values: wood 2 MJ, coal 4 MJ, solid fuel 12 MJ, rocket fuel 100 MJ ([item.lua L50, L73, L767, L784][item]).

**Is a huge rock faster per item than coal ore?** Yes. [INFERENCE, arithmetic on the table]

| | Huge rock | Coal ore |
|---|---|---|
| Time for 37 coal | 6 s | 37 × 2.02 = 74.7 s |
| Time for 74 items | 6 s | 149 s |
| Speed-up | 12.5× (coal only), 25× (all items) | 1× |
| Detour break-even (game time only, run at 8.9 tiles/s, coal only) | Worth it if the rock is within (74.7 − 6) / 2 × 8.9 ≈ 306 tiles off-route | |
| Detour break-even for the agent (walk there and back plus 1 extra command, L = 10 s) | About (74.7 − 6 − 30) / 2 × 8.9 ≈ 172 tiles | |

Big rocks give stone 10 times faster than stone ore (5 stone/s against 0.495/s). One big rock is 4 stone furnaces.

1.1 had the same rock data (`rock-huge` 3 s, 24 to 50 stone + 24 to 50 coal; `rock-big` 2 s, 20 stone; `sand-rock-big` 2 s, 19 to 25 stone; [1.1.110 decoratives.lua](https://raw.githubusercontent.com/wube/factorio-data/1.1.110/base/prototypes/decorative/decoratives.lua)). 2.x renamed them and, from 2.0.7, rocks drop nothing when destroyed by damage ([wiki Rock](https://wiki.factorio.com/Rock)). The agent has no reason to shoot rocks anyway.

**Agent:** `observe` (radius up to 32) lists rocks and trees as entities, but `map` shows only ore and water. To find rocks, observe on arrival at each new area. One `walk` plus one `mine` per huge rock buys about 10 minutes of fuel for one burner pair and 7 furnaces' worth of stone.

## 4. Rocks, trees and water near spawn (measured census)

Method: `factorio --create` with factobot's map-gen settings (peaceful, enemy bases off, everything else default), then a mod counted entities by distance from (0, 0) at map creation (section 12). Distances are in tiles.

| Seeds | Huge rocks ≤50 / 50-100 / 100-150 | Nearest huge | Big rocks ≤50 / 50-100 | Nearest big | Big sand rocks ≤100 | Trees ≤100 (nearest) | Nearest water |
|---|---|---|---|---|---|---|---|
| 1 to 10 (one terrain, see note) | 1 / 4-5 / 1-4 | 45 | 2 / 15-16 | 32 | 4-6 | 338-675 (43-54) | 55 |
| 1000 | 0 / 3 / 6 | 67 | 1 / 11 | 45 | 0 | 640 (50) | 53 |
| 123456 | 3 / 10 / 7 | 39 | 5 / 22 | 28 | 0 | 529 (47) | 52 |
| 987654321 | 5 / 3 / 10 | 39 | 11 / 16 | 21 | 0 | 641 (50) | 45 |
| 2058393139 | 2 / 3 / 9 | 36 | 3 / 7 | 37 | 0 | 251 (53) | 55 |
| 4226423258 | 7 / 5 / 13 | 35 | 14 / 7 | 32 | 0 | 1176 (51) | 46 |

Nearest ore in the same runs: iron 26 to 82 tiles, copper 26 to 102, coal 32 to 78, stone 32 to 70.

- Every map had at least 3 huge rocks and at least 10 big rocks within 100 tiles. On median maps, 2 huge rocks lie within reach of a short detour.
- No map had a tree within 43 tiles of spawn. Wood means a walk of about 50 tiles.
- Big sand rocks appear only in dry regions. Five of the six terrains had none within 150 tiles.
- **Note for the benchmark (not early-game advice):** seeds 1 to 10 produced the same water layout (1870 water tiles within 150, nearest 55) and almost the same rocks. Their ore layouts pair up exactly: 2 = 3, 4 = 5, 6 = 7, 8 = 9 (same tile counts and totals). Small consecutive seeds are therefore near-duplicate worlds. Large seeds all differed.

**Agent:** route the first minute through the nearest huge rock, plus a second one if it is within about 100 tiles, before going to the iron patch.

## 5. Burner economy: drills, furnaces, fuel

### 5a. Core numbers

| Entity | Speed | Power | Fuel life of one full fuel slot | Source |
|---|---|---|---|---|
| Burner mining drill (2×2, mines the 2×2 under it) | mining_speed 0.25, so 0.25 ore/s (15/min). Measured 0.246 plates/s through a furnace, including start-up. | 150 kW burner, efficiency 1 | 1 slot: 50 coal = 200 MJ = 1333 s (22.2 min). 100 wood = 200 MJ, the same. | [mining-drill.lua L1789-1827][bmd] |
| Stone furnace (2×2) | crafting_speed 1: iron or copper plate 3.2 s (0.3125/s), steel 16 s, brick 3.2 s per 2 stone | 90 kW | 50 coal = 2222 s at 100% busy. With one burner drill feeding it, it is 80% busy, so about 2778 s. | [entities.lua L1024][furnace]; [recipe.lua][recipe] |
| Electric mining drill (3×3, 5×5 area) | 0.5/s | 90 kW electric | none | [mining-drill.lua L1749](https://github.com/wube/factorio-data/blob/acf5a342afcb66c066b9d88d202e8622112da117/base/prototypes/entity/mining-drill.lua#L1749) |
| Burner inserter | Measured about 0.8 items/s chest to chest | Measured about 69 kJ per item (1 wood plus its 0.5 MJ starting buffer moved 36 plates). About 58 items per coal. | 50 coal ≈ 2900 items | [entities.lua L2614-2638][binserter]; wiki gives 69.4 kJ per item ([Burner inserter](https://wiki.factorio.com/Burner_inserter)) |

Derived per-pair numbers, for one burner drill on iron or copper feeding one stone furnace [INFERENCE]:

| Quantity | Value | Math |
|---|---|---|
| Plate output | 0.25/s = 15/min = 900/h | Drill-bound (furnace 0.3125 > 0.25) |
| Ore per coal in the drill | 6.67 | 0.25 × 4 MJ / 150 kW. The wiki says "about 7". |
| Coal use | 0.0555 coal/s = 3.33/min | Drill 0.0375 + furnace 0.0225 × 0.8 |
| Furnace output slot full | 400 s (6.7 min) | 100 plates / 0.25 |
| Furnace input slot by hand | 50 ore = 160 s of smelting | |
| Raw cost | 9 iron plates + 10 stone (drill 9 Fe + 5 stone, furnace 5 stone) | Drill recipe: 3 gears + 3 plates + 1 stone furnace ([recipe.lua L807][recipe-bmd]) |
| Iron payback | 36 s of output | 9 / 0.25 |
| Commands to build | 4: place drill, place furnace, insert drill fuel, insert furnace fuel | |
| Upkeep commands | 1 `take` per 400 s, 1 drill refuel per 1333 s, 1 furnace refuel per 2778 s, so about 0.0036 commands/s | At L = 10 s: 3.6% of the agent's time per pair |

Burner drill drop point: `vector_to_place_result = {-0.35, -1.3}` ([mining-drill.lua][bmd]). A north-facing drill centred at (x, y) drops into a 2×2 furnace centred at (x, y − 2). Measured: drill at (94, −36), furnace at (94, −38), plates produced. The other directions rotate the vector: east → furnace at (x + 2, y), south → (x, y + 2), west → (x − 2, y) [INFERENCE from the rotation].

**Agent:** after each `place`, check `inspect` → `drops_into` for the furnace. Insert a full stack of fuel (50 coal) into each drill. `insert` defaults to everything carried, but a fuel slot holds only one stack, so the surplus stays in the inventory.

### 5b. Coal

| Setup | Net coal | Upkeep | Notes |
|---|---|---|---|
| Hand-mining coal ore | 0.495/s while the body mines | 1 command per up to 1000 | Blocks walking. |
| Huge rock | about 37 per rock in 6 s | 1 to 2 commands per rock | Best fuel source in the first minutes. |
| Burner drill on coal → chest | 0.25/s gross, 0.2125/s net (12.75/min) | Refuel 50 coal every 22 min (take from its own chest, then insert: 2 commands) | An iron chest (8 Fe, 32 slots) holds 1600 coal. A wooden chest (2 wood, 16 slots) holds 800. |
| Coal loop: 2 drills on coal facing each other | 0.425/s while being drained; 0 when full | Zero fuel upkeep. Stores at most 100 coal (50 per fuel slot), then both stall. | Wiki: they fill each other in "slightly less than 3 minutes" ([Burner mining drill](https://wiki.factorio.com/Burner_mining_drill)); from an empty start I compute 50 / 0.2125 ≈ 235 s [INFERENCE]. |

Coal drills per burner pair: 0.2125 / 0.0555 ≈ 3.8 pairs per coal drill [INFERENCE]. Zaspar's 2.x human guide runs 20 burners on coal for 24 on iron, copper and stone, because coal also feeds boilers and human refuelling is cheap ([Zaspar's guide][zaspar], "Burner phase").

**Agent:** a coal drill emptying into a chest needs fewer commands than a coal loop. The loop needs a visit every 4 minutes; the chest needs one every 20 minutes or more. Use loops only where you pass by often anyway.

### 5c. Burner inserters

- Since 2.0, a burner inserter refuels itself from fuel it carries, even if the target does not need fuel ([wiki Burner inserter](https://wiki.factorio.com/Burner_inserter), history 2.0.7). That makes it the standard way to feed a boiler from a coal belt or chest.
- It cannot take fuel out of furnaces or other fuel-using buildings. On a furnace output it needs its own fuel (same wiki page).
- Placed burner inserters start with 25% of a wood (0.5 MJ), enough to move about 7 items (0.5 MJ / 69 kJ) ([entities.lua L2637-2638][binserter]).

**Agent:** a burner inserter from the furnace into a chest raises the time between `take`s per pair from 400 s (furnace slot) to 6400 s (wooden chest, 1600 plates). That cuts per-pair upkeep from about 0.0036 to about 0.0013 commands/s. It costs 3 Fe + 2 wood (or 8 Fe) + 3 commands [INFERENCE]. It is worth it for any pair meant to run longer than about 20 minutes. Up to 4 inserters can feed one 1×1 chest, so one `take` can collect from several furnaces (layout is left to the layout research).

## 6. Crafting times of early items

"Total" includes the intermediates the craft command makes automatically, at hand-craft speed 1. Raw is per item crafted. Source: [recipe.lua][recipe], computed by loading the file in Lua 5.4.

| Item | Own time (output) | Total per item | Raw per item | Unlocked by |
|---|---|---|---|---|
| Iron gear wheel | 0.5 s | 0.5 s | 2 Fe | start |
| Copper cable | 0.5 s (2) | 0.25 s | 0.5 Cu | electronics (trigger) |
| Pipe | 0.5 s | 0.5 s | 1 Fe | steam power (trigger) |
| Electronic circuit | 0.5 s | 1.25 s | 1 Fe, 1.5 Cu | electronics |
| Burner inserter | 0.5 s | 1.0 s | 3 Fe | start |
| Inserter | 0.5 s | 2.25 s | 4 Fe, 1.5 Cu | electronics |
| Long-handed inserter | 0.5 s | 3.25 s | 7 Fe, 1.5 Cu | automation |
| Fast inserter | 0.5 s | 5.25 s | 8 Fe, 4.5 Cu | fast-inserter (30 red) |
| Transport belt | 0.5 s (2) | 0.5 s | 1.5 Fe | start |
| Underground belt | 1 s (2) | 1.75 s | 8.75 Fe | logistics (20 red) |
| Splitter | 1 s | 9.25 s | 16 Fe, 7.5 Cu | logistics |
| Stone furnace | 0.5 s | 0.5 s | 5 stone | start |
| Burner mining drill | 2 s | 4.0 s | 9 Fe, 5 stone | start |
| Electric mining drill | 2 s | 8.25 s | 23 Fe, 4.5 Cu | electric-mining-drill (25 red) |
| Assembling machine 1 | 0.5 s | 6.75 s | 22 Fe, 4.5 Cu | automation (10 red) |
| Lab | 2 s | 21.5 s | 36 Fe, 15 Cu | electronics |
| Boiler | 0.5 s | 3.0 s | 4 Fe, 5 stone | steam power |
| Steam engine | 0.5 s | 7.0 s | 31 Fe | steam power |
| Offshore pump | 0.5 s | 3.0 s | 7 Fe | steam power |
| Small electric pole | 0.5 s (2) | 0.5 s | 0.5 wood, 0.5 Cu | electronics |
| Pipe to ground | 0.5 s (2) | 2.75 s | 7.5 Fe | steam power |
| Wooden chest | 0.5 s | 0.5 s | 2 wood | start |
| Iron chest | 0.5 s | 0.5 s | 8 Fe | start |
| Red pack (automation science) | 5 s | 5.5 s | 2 Fe, 1 Cu | automation-science-pack (trigger) |
| Green pack (logistic science) | 6 s | 8.75 s | 5.5 Fe, 1.5 Cu | logistic-science-pack (75 red) |
| Iron / copper plate | 3.2 s (furnace) | | 1 ore | start (smelting only, no hand-craft) |
| Steel plate | 16 s (furnace) | | 5 Fe | steel-processing (50 red) |

Machines: assembler 1 crafting speed 0.5 at 75 kW, assembler 2 0.75 at 150 kW, lab research speed 1 at 60 kW ([entities.lua L3163, L3257, L3880][asm]). A red pack takes 10 s in an assembler 1.

**Agent:** one `craft` command handles one recipe and crafts its intermediates, so queue the big items (lab, steam engine) as soon as the plates exist. Queue the 10 red packs in a separate `craft` after the lab craft finishes, because the lab craft unlocks their recipe and `craft` rejects a locked recipe. They run while you walk and mine. Hand-craft time is rarely the bottleneck in the first 15 minutes: the whole milestone-1 shopping list is about 120 s of crafting.

## 7. Trigger technologies and the earliest research

All values from [technology.lua][tech] (loaded in Lua). Trigger techs cost no packs and complete the moment the condition is met. They also appear in factobot's `research` output with a `trigger` in words.

| Tech | Trigger or cost | Unlocks |
|---|---|---|
| steam-power | Craft 50 iron plates | pipe, pipe-to-ground, offshore pump, boiler, steam engine |
| electronics | Craft 10 copper plates | copper cable, electronic circuit, lab, inserter, small electric pole |
| automation-science-pack | Craft 1 lab (needs steam-power and electronics) | red pack recipe |
| steel-axe | Craft 50 steel plates (needs steel-processing) | character mining speed +100% |
| oil-processing | Mine crude oil (needs oil-gathering) | refinery, chemical plant, basic oil processing, solid fuel |
| automation | 10 red × 10 s | assembler 1, long-handed inserter |
| electric-mining-drill | 25 red × 10 s | electric mining drill |
| logistics | 20 red × 15 s | underground belt, splitter |
| fast-inserter | 30 red × 15 s | fast inserter |
| steel-processing | 50 red × 5 s | steel plate, steel chest |
| logistic-science-pack | 75 red × 5 s | green pack |
| lamp, military, gun-turret, stone-wall, radar, repair-pack | 10 to 25 red | Not needed for the rocket in peaceful mode (see [human-baselines.md](../docs/human-baselines.md) §3c and §4). |

Recipes enabled at tick 0: burner inserter, burner mining drill, iron/copper plate (smelting), stone brick, iron gear, transport belt, stone furnace, wooden chest, iron chest, firearm magazine, light armor.

"Craft 50 iron plates" counts plates smelted in furnaces. Iron plates have only a smelting recipe (`categories = {"smelting"}`, [recipe.lua L1450-1458][recipe-plate]), and the character cannot smelt, so furnace output must be what the trigger counts [INFERENCE]. The wiki describes steam power the same way: "Craft 50 iron plates", introduced in 2.0.7 ([wiki Steam power (research)](https://wiki.factorio.com/Steam_power_(research)); [Technologies](https://wiki.factorio.com/Technologies)). Trigger techs were added in 2.0.7: "Added event-based technologies for unlocks related to the early game" ([changelog.txt][changelog]). Design rationale: [FFF #376](https://factorio.com/blog/post/fff-376).

**Agent:** smelt 10 copper ore as early as iron. Without electronics there are no circuits, no lab, no inserters and no poles. Research cannot be queued for trigger techs. For lab techs, queue the next research before the current one ends so the lab never idles.

## 8. First power

| Building | Numbers | Source |
|---|---|---|
| Offshore pump | 1200 water/s, **needs no power** (energy source `void`), 1×2, on the shore facing water | [entities.lua L1924-1971][pump] |
| Boiler | 1.8 MW fuel in, 165 °C steam. In 2.x 1 water makes 10 steam, so 6 water/s → 60 steam/s. Burns 0.45 coal/s (27/min) at full load. | [entities.lua L1229][boiler]; [fluid.lua L28-44][fluid]; changelog 2.0.7 "1 Water will now produce 10 Steam" |
| Steam engine | 30 steam/s (0.5 per tick), 900 kW | [entities.lua L1770][engine] |
| Ratio | 1 pump : 200 boilers : 400 engines (2.x). It was 1 : 20 : 40 in 1.1. | [wiki Power production](https://wiki.factorio.com/Power_production) |
| Small electric pole | Wire reach 7.5, supply area 5×5 (2.5 from centre) | [entities.lua L1643][pole] |
| Consumers | Lab 60 kW, assembler 1 75 kW, electric drill 90 kW, inserter up to 15.1 kW (wiki, 2.0.7) | [entities.lua][asm]; [wiki Inserter](https://wiki.factorio.com/Inserter) |

Minimum first power plant: 1 pump (7 Fe) + 1 boiler (4 Fe, 5 stone) + 1 steam engine (31 Fe) + 1 small pole (from the start wood: 1 wood + 1 Cu = 2 poles) = 42 Fe, 5 stone, 1 Cu, 1 wood, 13.5 s of crafting. One boiler with 2 engines supplies 1.8 MW, enough for 20 electric drills or 24 assemblers.

Boiler fuel life per 50-coal stack [INFERENCE]:

| Load | Coal/min | Stack lasts |
|---|---|---|
| 1 lab + 1 assembler (135 kW) | 2.0 | 24.7 min |
| 900 kW (1 engine full) | 13.5 | 3.7 min |
| 1.8 MW (2 engines full) | 27 | 1.85 min |

**Agent:** place the lab right next to the steam engine so that one pole connects both, and use `inspect` → `pipes_to` and `status` to confirm pump → boiler → engine connections. Once load passes about 300 kW, stop hand-fuelling boilers. Put an iron chest of coal plus a burner inserter in front of each boiler: 1600 coal lasts 59 min at full load, which means one `insert` per hour instead of one per two minutes. While at the shore, consider mining one fish (0.8 s, 5 raw fish). A 2.x rocket launch needs a payload ([wiki Rocket silo](https://wiki.factorio.com/Rocket_silo), 2.0.7), and fish is the cheapest. A fish taken now saves a trip near the end.

## 9. Opening sequence with math

All of this section is `[INFERENCE]`. Assumptions: L = 10 s per command. Distances are census medians: huge rocks 40 to 60 tiles, iron about 45, coal about 55, copper about 40, water about 50, all at 8.9 tiles/s, so most walks finish inside the command time. Jobs run in the background (protocol: `walk`, `mine` and `craft` return at once; crafting runs alongside walking and mining; starting a walk cancels a mine job).

### 9a. Shopping list for milestone 1 (first research with an assembler-made red pack)

| Item | Fe | Cu | Stone | Wood | Craft s |
|---|---|---|---|---|---|
| Lab | 36 | 15 | | | 21.5 |
| Offshore pump + boiler + steam engine | 42 | | 5 | | 13 |
| 2 small poles | | 1 | | 1 | 0.5 |
| 10 hand-made red packs (for automation, crafted after the lab) | 20 | 10 | | | 55 |
| Assembler 1 | 22 | 4.5 | | | 6.75 |
| Inputs for the first assembler packs (5 packs) | 10 | 5 | | | 2.5 |
| **Total** | **130** | **35.5** | **5** | **1** | **≈ 100** |

Plus research time: automation is 10 units × 10 s = 100 s on one lab. A second lab would save 50 s but costs 36 Fe, 15 Cu and 2 commands, so it is not worth it before milestone 1. The first assembler pack takes 10 s.

### 9b. Hand-mining against burner drills

- Hand-mining all 166 ore: 166 × 2.02 = 335 s of body time. Smelting at 3.2 s per plate in 3 furnaces: about 180 s, mostly overlapping the mining.
- One burner pair placed at time t has produced 0.25 × (T − t) plates by time T. The kit pair placed at 2:00 gives 45 plates by 5:00 and 150 by 12:00.
- Mining while building: `mine --count 200` on a tile at the patch edge keeps the body busy for 404 s, while `place`, `insert`, `take` and `craft` can still be issued within 10 tiles. Hand-mining is therefore nearly free next to a build site.
- **Automation beats hand-mining as soon as it is placed**, in iron terms: a pair repays its 9 Fe in 36 s. What limits drills is commands (4 to build, about 1 per 6.7 minutes to empty) and coal (15 to start, 3.33/min to run), not iron.
- Value per command: a pair placed at minute 5 and replaced by electric drills at minute 25 yields 0.25 × 1200 = 300 plates for about 4 build + 3 take + 1 refuel = 8 commands, which is about 37 plates per command. A `mine --count 200` is 1 command for 200 ore, but it ties up the body for 404 s.

### 9c. Recommended opening (growth variant)

| Phase | Commands | End (L = 10 s) | Actions | Resulting state |
|---|---|---|---|---|
| A. Scout | 2 | 0:20 | `map`; `observe` radius 32 | Patches, water and visible rocks known |
| B. Fuel and stone | 5 | 1:20 | walk + mine the nearest huge rock; walk + mine a second huge rock (or a big rock) within about 100 tiles; `craft stone-furnace` × 5 | Two huge rocks: about 74 coal and 74 stone, about 49 stone left after the 5 furnaces. Huge plus big rock: about 37 coal and 57 stone (about 32 left), so fuel fewer burners. |
| C. Iron start | 6 | 2:20 | walk to iron edge; place kit drill; place furnace at its drop point; insert 25 coal into drill and 10 into furnace; `mine iron-ore --count 200` (cancelled when phase E walks away; restart it after each walk) | Pair 1 at 0.25/s; body mining 0.495/s |
| D. Hand-smelt | 6 | 3:30 | place 2 furnaces in reach; 5 coal each; insert the ore mined so far (about 40), split between them | Iron rate ≈ 0.25 + 0.495 = 0.745/s. Steam power fires at about 4:20 (50 smelted). |
| E. Coal | 8 | 6:30 | take plates (about 100 Fe by 5:20: 8 + 49 from pair 1 + about 60 hand-smelted); `craft burner-mining-drill` × 2 + `craft iron-chest` × 2 (34 Fe); walk to coal; place 2 drills + 2 chests; 12 coal each (the rock coal left after pair 1, the hand furnaces and the copper furnace); walk back and restart `mine` | +0.5 coal/s into the chests from about 6:30 |
| F. Copper | 7 | 8:30 | walk to copper; `mine copper-ore --count 40` (81 s); place a furnace there with 5 coal; insert the ore in 2 batches; craft 1 more drill pair for copper if Fe allows | Electronics fires at about 7:30 (10 Cu smelted); about 40 Cu by 9:00 |
| G. More iron pairs | 21 | 12:00 | take plates; craft 3 drills; walk to coal (about 9:40); take both chests (about 95 coal); put 10 back into each coal drill; walk back; put 10 coal into pair 1's furnace; place each new pair (4 commands, 15 coal) | 4 iron pairs ≈ 1.0 Fe/s |
| H. Power and lab | 13 | 14:10 | `craft lab`, `craft steam-engine`, `craft boiler`, `craft offshore-pump`, `craft small-electric-pole` (queued while walking); walk to water; `craft automation-science-pack --count 10` once the lab craft has finished; place pump, boiler, engine, pole, lab; 20 coal into the boiler; insert 10 red packs; `research automation` | Automation runs 14:10 to 15:50 |
| I. Assembler red | 9 | 16:40 | `craft assembling-machine-1`; place next to the lab; `recipe automation-science-pack`; insert copper + gears; `research electric-mining-drill` (queued); after 10 s take the pack and insert it into the lab (or place an inserter) | **Milestone 1 at about 17 minutes** |

Total: about 77 commands. Checks on the balances:

- **Coal:** start 74 from two huge rocks, all spent by 6:30: pair 1 35 (25 drill, 10 furnace), hand furnaces 10, copper furnace 5, coal drills 12 each (24). The coal drills then put 0.5 coal/s into their chests (their own fuel comes from the fill), so the chests hold about 95 when phase G empties them at 9:40. G spends 20 refuelling the coal drills, 10 on pair 1's furnace and 45 on 3 new pairs, and the boiler takes the last 20. Fuel lives [INFERENCE]: pair 1's drill 25 coal = 667 s (to about 13:10); its furnace 10 coal = 556 s at 80% busy (to about 11:15, about 20:30 after the G refuel); the coal drills 12 coal = 320 s (to about 11:50, about 16:15 after the refuel); the new pairs 10 coal per drill = 267 s, so they run dry about 4.5 minutes after placement and need the next coal trip.
- **Iron by 12:00:** 8 start + pair 1 (0.25 × 600 = 150, running because G refuels its furnace) + hand ore about 140 (about 280 s of mining between the walks in phases E, F and H) + 3 pairs placed from about 10:00 to 11:30 (0.25 × 3 × 75 ≈ 55) ≈ 350. Spending: 6 drills 54 + 2 chests 16 + milestone list 130 = 200. Surplus ≈ 150 Fe for electric drills (23 Fe each) right after automation.
- **Action-bound check:** 77 commands × 10 s = 770 s ≈ 12.8 min against the 16.7 min total. The rest is research (100 s) and waiting for smelting. Milestone time scales almost linearly with L: about 10 min at L = 5 s, about 30 min at L = 20 s, about 42 min at L = 30 s.

Lean variant (milestone 1 only): skip phases E and G (about 29 commands) and hand-mine everything into 3 to 4 furnaces. Milestone 1 lands about 2 to 3 minutes earlier at L = 10 s, but the factory then has about 150 fewer plates and no coal supply, and the gap reverses within roughly the next 10 minutes. Recommended only if milestone timing is scored separately and weighted heavily.

Human reference: 2.x speedrunners split "red science" at about 14 minutes (seb351 13:51, Nefrums 1.1 14:12, Krul87 "mini science" 16:09; [human-baselines.md](../docs/human-baselines.md) §3a). By then they have far more burners: Zaspar runs 14 on iron, 6 on copper, 4 on stone and 20 on coal ([Zaspar's guide][zaspar]).

### 9d. After milestone 1 (15 to 60 minutes): what changes

- First assembler-red research: electric mining drill (25 × 10 s = 250 s on one lab) or logistic-science-pack (75 × 5 s). Zaspar's 2.x order after automation: electric miners, gun turret (skip in peaceful), logistics, fast inserter, steel processing, green science ([Zaspar's guide][zaspar], "Power and lab"). Research order belongs to the tech-tree research.
- Swap burner pairs for electric drills. An electric drill feeding a stone furnace directly is furnace-bound at 0.3125/s, needs no drill fuel and needs one furnace refuel per 37 min.
- Before power passes about 300 kW, set up boiler coal (chest + burner inserter, or coal drills → belt → burner inserter).
- Steel axe: after steel processing, 5 furnaces each given 50 iron plates make 50 steel in 160 s. This is the cheapest bonus in the game (Zaspar: "place 5 furnaces and half stack them with iron to unlock steel axe"). It costs 250 Fe and about 10 commands. Worth it if the agent still hand-mines more than about 500 items afterwards (500 × 1 s saved = 8 min of body time) [INFERENCE].

## 10. Common early mistakes that waste time

| Mistake | Cost | Fix | Agent note |
|---|---|---|---|
| Following a 1.1 guide that crafts pipes, a boiler, a lab or circuits at minute 1 | Commands rejected ("recipe locked") | Smelt 50 Fe and 10 Cu first (section 7) | Check `research` → `available` trigger text. |
| Drill or boiler runs dry | Production stops silently | Fuel with full stacks; burner inserters on boilers | `inspect` → `status: no_fuel`. |
| Furnace output full (100 plates) | Pair stalls after 6.7 min | `take` on a schedule, or inserter → chest | One `take` per pair per ≤6 min. |
| Furnace placed off the drill's drop point | Ore spills on the ground: the drill drops one item, then waits | Use the offsets in 5a | `inspect` → `drops_into` must name the furnace. |
| Stone or plates inserted into a furnace | Stone smelts to bricks (enabled at start); plates turn into steel once steel processing is researched | Insert only ore into iron/copper furnaces | `insert` puts items "where they belong", including the furnace input. |
| Mixing ores in one furnace | The furnace keeps the old recipe until its input slot is empty | One ore type per furnace | |
| Too many burner pairs | Upkeep eats the command budget (3.6% of L-time per pair) | Cap around 8 to 12, then go electric | |
| Belting long distances around obstacles | One more `place --to` per bend, plus the walk | Lay straight runs; carry one-off loads instead | `place --to` stops at a tree or rock and says where; mine it and rerun. |
| Chopping trees for fuel | 1 command per 4 wood | Huge rocks or `mine coal --count N` | Trees only for pole wood. |
| Starting a `walk` during a long `mine` | Cancels the mine job | Do in-reach work while mining; walk afterwards | Protocol: walking and mining share the body. |
| Full inventory during `mine` | The job fails | Keep slots free; deposit into chests | 80 slots. |
| Power plant not connected (water, fuel, poles) | Lab idle | Zaspar's top listed mistake: "Connect power plants properly (water, fuel, poles)" | `inspect` the engine: `fluids`, `status`. |
| Idle lab between researches | Lost research time | Queue several techs | `research` appends to the queue. |
| Second offshore pump for power | Wasted iron and commands | One pump feeds 200 boilers in 2.x | |
| Forgetting the rocket payload | A late trip to water | Mine a fish while building power | 2.x requires a payload. |

## 11. 1.1 vs 2.x differences that affect the opening

| Topic | 1.1 | 2.1.24 | Source |
|---|---|---|---|
| Steam power, lab, circuits, inserter, poles, red packs | Available from the start (no research) | Trigger techs: 50 Fe, 10 Cu, 1 lab | [technology.lua][tech]; changelog 2.0.7 |
| Steel axe | 50 red packs of research | Trigger: craft 50 steel. Same +1 mining speed. | [1.1.110 technology.lua](https://raw.githubusercontent.com/wube/factorio-data/1.1.110/base/prototypes/technology.lua); [tech-axe] |
| Water to steam | 1 water → 1 steam; pump : boiler = 1 : 20 | 1 water → 10 steam; 1 : 200 | changelog 2.0.7; [wiki Power production](https://wiki.factorio.com/Power_production) |
| Offshore pump power | None | `void` energy source (still none) | [pump] |
| Rocks destroyed by damage | Drop stone | Drop nothing (mining unchanged) | [wiki Rock](https://wiki.factorio.com/Rock) |
| Burner inserter | 94.2 kW max | 144 kW max. Refuels itself from carried fuel even if the target does not need it. Measured per-item energy (about 69 kJ) matches the old wiki figure. | [wiki Burner inserter](https://wiki.factorio.com/Burner_inserter) |
| Rocket | No payload needed for the win | Payload required (fish works) | [wiki Rocket silo](https://wiki.factorio.com/Rocket_silo) |
| Character stats, burner drill, stone furnace, ore mining times, rock yields, red pack, burner drill recipe | Same values | Same values | Compared against [1.1.110 entities.lua](https://raw.githubusercontent.com/wube/factorio-data/1.1.110/base/prototypes/entity/entities.lua), [mining-drill.lua](https://raw.githubusercontent.com/wube/factorio-data/1.1.110/base/prototypes/entity/mining-drill.lua), decoratives.lua, recipe.lua |

Tips I found only in 1.1-era or secondary sources:
- A 1.1-era TAS commentary summary says the first burners are placed so that rock mining overlaps their running, saving about 30 s. This comes from an AI-generated summary of [Zaspar's TAS developer commentary](https://www.youtube.com/watch?v=tImNejO5g48) (the summary mentions rocket control units, so it is 1.1). UNVERIFIED-2.x. The idea matches 9c phase B to C.
- Hand-feeding single coals with a drag gesture (Zaspar: "Press 'Z' while holding coal and drag over buildings") has no agent equivalent. Each building needs its own `insert`.

## 12. Method and sources

Measurements (2026-11-02): the cached factobot binary `~/.cache/factobot/factorio/2.1.24/bin/x64/factorio` with a throwaway mod in `/tmp` (not committed). Map creation used `--create --map-gen-settings` with factobot's settings (`{"peaceful_mode": true, "autoplace_controls": {"enemy-base": {"frequency": 0, "size": 0}}}`, from the `map-gen-settings.json` that `crates/factobot/src/server.rs` writes, decision 9) and `--map-gen-seed N`. The census ran in `on_init` after `request_to_generate_chunks({0,0}, 5)` and `force_generate_chunk_requests()`. Timings: characters created with `create_entity` and driven by `mining_state` / `walking_state` in `on_tick`, run with `--benchmark` (seed 123456). A burner drill + furnace and a burner inserter between two chests were run for 241 s of game time. These are single runs; random rock yields vary per rock.

Data files (all at commit acf5a34):
- Character: [entities.lua L704-734][char], [L976][char-mine]
- Burner drill: [mining-drill.lua L1789-1827][bmd]; stone furnace [entities.lua L1024][furnace]; boiler [L1229][boiler]; steam engine [L1770][engine]; offshore pump [L1924][pump]; small pole [L1643][pole]; burner inserter [L2614][binserter]; assembler 1/2 and lab [L3163, L3257, L3880][asm]
- Resources [resources.lua][res]; trees [trees.lua][trees]; rocks [decoratives.lua][rocks]
- Items and fuel [item.lua][item]; fluids [fluid.lua][fluid]; recipes [recipe.lua][recipe]; technologies [technology.lua][tech]; [changelog.txt][changelog]
- Freeplay: `data/base/script/freeplay/freeplay.lua` and `core/lualib/crash-site.lua` in the 2.1.24 install

Other sources: [Zaspar's speedrun guide (2.x, text export)][zaspar]; [wiki Player](https://wiki.factorio.com/Player); [wiki Rock](https://wiki.factorio.com/Rock); [wiki Burner mining drill](https://wiki.factorio.com/Burner_mining_drill); [wiki Burner inserter](https://wiki.factorio.com/Burner_inserter); [wiki Power production](https://wiki.factorio.com/Power_production); [wiki Mining](https://wiki.factorio.com/Mining); [wiki Steam power (research)](https://wiki.factorio.com/Steam_power_(research)); [Lua API CraftItemTechnologyTrigger](https://lua-api.factorio.com/latest/types/CraftItemTechnologyTrigger.html); factobot [protocol.md](../docs/protocol.md), [decisions.md](../docs/decisions.md), [human-baselines.md](../docs/human-baselines.md).

[char]: https://github.com/wube/factorio-data/blob/acf5a342afcb66c066b9d88d202e8622112da117/base/prototypes/entity/entities.lua#L704-L734
[char-mine]: https://github.com/wube/factorio-data/blob/acf5a342afcb66c066b9d88d202e8622112da117/base/prototypes/entity/entities.lua#L976
[furnace]: https://github.com/wube/factorio-data/blob/acf5a342afcb66c066b9d88d202e8622112da117/base/prototypes/entity/entities.lua#L1024
[boiler]: https://github.com/wube/factorio-data/blob/acf5a342afcb66c066b9d88d202e8622112da117/base/prototypes/entity/entities.lua#L1229
[pole]: https://github.com/wube/factorio-data/blob/acf5a342afcb66c066b9d88d202e8622112da117/base/prototypes/entity/entities.lua#L1643
[engine]: https://github.com/wube/factorio-data/blob/acf5a342afcb66c066b9d88d202e8622112da117/base/prototypes/entity/entities.lua#L1770
[pump]: https://github.com/wube/factorio-data/blob/acf5a342afcb66c066b9d88d202e8622112da117/base/prototypes/entity/entities.lua#L1924-L1971
[binserter]: https://github.com/wube/factorio-data/blob/acf5a342afcb66c066b9d88d202e8622112da117/base/prototypes/entity/entities.lua#L2614-L2638
[asm]: https://github.com/wube/factorio-data/blob/acf5a342afcb66c066b9d88d202e8622112da117/base/prototypes/entity/entities.lua#L3163
[bmd]: https://github.com/wube/factorio-data/blob/acf5a342afcb66c066b9d88d202e8622112da117/base/prototypes/entity/mining-drill.lua#L1789-L1827
[res]: https://github.com/wube/factorio-data/blob/acf5a342afcb66c066b9d88d202e8622112da117/base/prototypes/entity/resources.lua#L79-L135
[trees]: https://github.com/wube/factorio-data/blob/acf5a342afcb66c066b9d88d202e8622112da117/base/prototypes/entity/trees.lua#L4881
[rocks]: https://github.com/wube/factorio-data/blob/acf5a342afcb66c066b9d88d202e8622112da117/base/prototypes/decorative/decoratives.lua#L4310
[hugerock]: https://github.com/wube/factorio-data/blob/acf5a342afcb66c066b9d88d202e8622112da117/base/prototypes/decorative/decoratives.lua#L4310
[bigrock]: https://github.com/wube/factorio-data/blob/acf5a342afcb66c066b9d88d202e8622112da117/base/prototypes/decorative/decoratives.lua#L4475
[sandrock]: https://github.com/wube/factorio-data/blob/acf5a342afcb66c066b9d88d202e8622112da117/base/prototypes/decorative/decoratives.lua#L5092
[item]: https://github.com/wube/factorio-data/blob/acf5a342afcb66c066b9d88d202e8622112da117/base/prototypes/item.lua#L48-L73
[fluid]: https://github.com/wube/factorio-data/blob/acf5a342afcb66c066b9d88d202e8622112da117/base/prototypes/fluid.lua#L28-L44
[recipe]: https://github.com/wube/factorio-data/blob/acf5a342afcb66c066b9d88d202e8622112da117/base/prototypes/recipe.lua
[recipe-bmd]: https://github.com/wube/factorio-data/blob/acf5a342afcb66c066b9d88d202e8622112da117/base/prototypes/recipe.lua#L807
[recipe-plate]: https://github.com/wube/factorio-data/blob/acf5a342afcb66c066b9d88d202e8622112da117/base/prototypes/recipe.lua#L1450-L1458
[tech]: https://github.com/wube/factorio-data/blob/acf5a342afcb66c066b9d88d202e8622112da117/base/prototypes/technology.lua
[tech-axe]: https://github.com/wube/factorio-data/blob/acf5a342afcb66c066b9d88d202e8622112da117/base/prototypes/technology.lua#L2007
[tech-tb]: https://github.com/wube/factorio-data/blob/acf5a342afcb66c066b9d88d202e8622112da117/base/prototypes/technology.lua#L2528
[changelog]: https://github.com/wube/factorio-data/blob/acf5a342afcb66c066b9d88d202e8622112da117/changelog.txt
[zaspar]: https://docs.google.com/presentation/d/12dO2YmmOUK_R528-jCKo2nSdJUKNkp-vvXWqDHS3PKo/export/txt
