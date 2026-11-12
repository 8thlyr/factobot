# Production chains to the rocket (Factorio 2.1.24, base game)

Research date 2026-11-02. Scope: every recipe, machine and ratio on the path from a fresh freeplay start to a rocket launch, written as a briefing for the factobot agent. The agent places entities one at a time, gets no blueprints or ghosts, and spends 5 to 30 s of game time on each action.

Conventions. `[INFERENCE]` marks my own derivations; the method is shown next to each. `UNVERIFIED` marks claims I could not confirm. `UNVERIFIED-2.x` marks numbers that come from 1.1-era sources. Except where a row says otherwise, every number comes from the pinned game data (§0).

## 0. Sources and pins

| Source | Pin | Used for |
|---|---|---|
| wube/factorio-data | tag `2.1.24`, commit [`acf5a342afcb66c066b9d88d202e8622112da117`](https://github.com/wube/factorio-data/tree/acf5a342afcb66c066b9d88d202e8622112da117) (2026-10-27), `base/info.json` version 2.1.24 | Recipes ([recipe.lua](https://github.com/wube/factorio-data/blob/acf5a342afcb66c066b9d88d202e8622112da117/base/prototypes/recipe.lua)), techs ([technology.lua](https://github.com/wube/factorio-data/blob/acf5a342afcb66c066b9d88d202e8622112da117/base/prototypes/technology.lua)), machines ([entity/entities.lua](https://github.com/wube/factorio-data/blob/acf5a342afcb66c066b9d88d202e8622112da117/base/prototypes/entity/entities.lua), [entity/mining-drill.lua](https://github.com/wube/factorio-data/blob/acf5a342afcb66c066b9d88d202e8622112da117/base/prototypes/entity/mining-drill.lua), [entity/transport-belts.lua](https://github.com/wube/factorio-data/blob/acf5a342afcb66c066b9d88d202e8622112da117/base/prototypes/entity/transport-belts.lua)), items, fuel values, stack sizes and modules ([item.lua](https://github.com/wube/factorio-data/blob/acf5a342afcb66c066b9d88d202e8622112da117/base/prototypes/item.lua)), fluids ([fluid.lua](https://github.com/wube/factorio-data/blob/acf5a342afcb66c066b9d88d202e8622112da117/base/prototypes/fluid.lua)), pipeline extent ([core/prototypes/utility-constants.lua](https://github.com/wube/factorio-data/blob/acf5a342afcb66c066b9d88d202e8622112da117/core/prototypes/utility-constants.lua)). I loaded the Lua files in Lua 5.4 with a stub `data:extend` and parsed the results; I did not copy values by hand. |
| wube/factorio-data | tag [`1.1.110`](https://github.com/wube/factorio-data/tree/1.1.110) | 1.1 comparison (§10). I loaded and diffed the same files. |
| Local 2.1.24 install | `~/.cache/factobot/factorio/2.1.24/data/base/script/freeplay/freeplay.lua`, `core/locale/en/core.cfg` | Freeplay start inventory and the launch-blocker messages. These files are not in the factorio-data repo. |
| factobot live test | A factobot test world, 2.1.24 freeplay, seed 1, 2026-11-02 | No cargo landing pad is needed for a fish launch (§7). |
| Official wiki | [Rocket silo](https://wiki.factorio.com/Rocket_silo) (oldid 220498, edited 2026-10-19), [Cargo landing pad](https://wiki.factorio.com/Cargo_landing_pad), [Inserters](https://wiki.factorio.com/Inserters), [Oil processing](https://wiki.factorio.com/Oil_processing), [Power production](https://wiki.factorio.com/Power_production), [Boiler](https://wiki.factorio.com/Boiler), [Solar panel](https://wiki.factorio.com/Solar_panel), [Pumpjack](https://wiki.factorio.com/Pumpjack), [Fluid system](https://wiki.factorio.com/Fluid_system), [Transport belts/Physics](https://wiki.factorio.com/Transport_belts/Physics) | Measured inserter throughput, oil ratios, the water-to-steam change, payload rules, solar ratios. All fetched 2026-11-02. |
| Zaspar's 2.x speedrun guide | [Google Slides export](https://docs.google.com/presentation/d/12dO2YmmOUK_R528-jCKo2nSdJUKNkp-vvXWqDHS3PKo/export/txt), covers 2.0 and 2.1 map generators | Machine counts and rates a 2.x record runner targets. |
| Calculator scripts | `/tmp/calc/*.py` (scratch, not committed) | Every `[INFERENCE]` ratio and total in §4 to §6. The method is spelled out in each section. |

## 1. Summary: the most valuable takeaways, ranked by time saved

1. **The rocket needs a payload.** Since 2.0.7 "A payload is now required to win" ([wiki Rocket silo history](https://wiki.factorio.com/Rocket_silo)). One raw fish is enough. A `fish` entity in water has `minable = {mining_time = 0.4, result = "raw-fish", count = 5}` (entities.lua), and `raw-fish` has `send_to_orbit_mode = "manual"` (item.lua). The satellite, which costs 100 LDS, 100 solar panels, 100 accumulators, 100 processing units, 50 rocket fuel and 5 radars, is not needed. No cargo landing pad is needed for a fish launch. We observed this in a factobot test world on 2026-11-02: 2.1.24 freeplay, no pad, 1 fish, `launch_rocket()` returned true and victory followed. The wiki says a pad is always required. My reading is that this applies to satellites, whose launch products need somewhere to land; the 2.1.24 core.cfg message is "No cargo landing pad to collect the launch results" `[INFERENCE]`. Zaspar's 2.1 guide also ends with "Feed the fish as the rocket payload. Hit launch!" and never builds a pad. In the same test the script call `launch_rocket()` also launched an empty rocket, so the payload rule is enforced by the game GUI, not the engine; fac's `launch` enforces it itself and rejects a rocket with no payload (decision 49). *Agent:* mine one fish whenever passing water (`mine` takes fish), insert it into the silo, then `fac launch`.
2. **Mining and smelting are about two thirds of all machine-time.** Over the whole rocket path, steel-furnace time (888k s) plus electric-drill time (1.11M s) make up 67% of the 2.98M machine-seconds (§7) `[INFERENCE]`. A steel furnace smelts 0.625 plates/s and an electric drill mines 0.5 ore/s, so one drill placed to output straight into one steel furnace is a nearly balanced column with no belt and no input inserter. *Agent:* this is the cheapest plate source per action. Count placements per plate/s, not per assembler.
3. **Research advanced oil processing straight after the blue unlock.** It costs only 75 × (red, green, blue). Basic processing turns 100 crude into 45 petroleum. Advanced processing with full cracking gives 97.5 (55 + 2/3 × (45 + 0.75 × 25)), which is 2.17× as much. Advanced is also the only source of light oil (rocket fuel) and heavy oil (lubricant). *Agent:* one `recipe` action per refinery switches it, plus two cracking plants.
4. **Put 4 productivity module 3s in the silo.** That gives +40% productivity (4 × 0.1) and −60% speed, so 100 parts need 72 crafts (100/1.4 = 71.4, rounded up). This saves 28% of the rocket-part bill, about 9.6k iron ore, 17k copper ore and 50k crude `[INFERENCE: 28 × per-part raw from §7]`. The prod-3 research is already mandatory (both module-3 techs are prerequisites of `rocket-silo`). The extra cost is 64 prod-1 + 16 prod-2 + 4 prod-3 crafts: 420 advanced circuits, 100 processing units and 320 green circuits. Zaspar does exactly this ("Prod 3s into rocket silo"). *Agent:* 4 inserts. Silo crafting time grows from 300 s to 540 s, which only matters if the parts are already stockpiled.
5. **Research speed 1 and 2 pay for themselves about 8× over.** They add +0.2 and +0.3 lab speed for 300 × (red + green) packs and 9,000 lab-s (30 s per unit). In return they save about 75k of the 224k mandatory lab-seconds `[INFERENCE: 224,425 × (1 − 1/1.5)]`. Both techs are off the rocket-silo closure.
6. **Purple is the expensive pack, and steel is its cost.** Per pack it takes 52.5 iron ore, 8.33 steel and 435 speed-1 machine-seconds, against 122 for blue. Steel makes up 20% of all smelting time on the path (22,550 steel × 16 s). *Agent:* build steel smelting early and let it stockpile.
7. **Hand-craft buildings, not science.** The character crafts at speed 1, roughly one AM2 (0.75). Over a 10 h run that is 36,000 crafting-seconds, about 6% of the 622k AM2-seconds the path needs `[INFERENCE]`. Hand-crafting also cannot make engines (`advanced-crafting`) or anything with a fluid ingredient: processing units, electric engines, rocket fuel, concrete. *Agent:* the craft queue runs during walks, so fill it with machines, poles and inserters.
8. **Size the factory with the square-root rule.** If each machine costs c game-seconds of agent actions (machine, inserters, pole share, belts, recipe, fuel) and the work is W machine-seconds, total time is about W/n + c·n. That is minimised at n* = √(W/c), with T* = 2√(W·c). For the whole path W ≈ 2.98M. At c = 60 s, n* ≈ 220 machines and T* ≈ 7.4 h. At c = 120 s, n* ≈ 160 and T* ≈ 10.5 h. These are lower bounds that ignore staging (§8, §9) `[INFERENCE]`.
9. **Power: steam only, and one offshore pump is enough.** Since 2.0.7, 1 water makes 10 steam ([wiki Boiler history](https://wiki.factorio.com/Boiler)), so one offshore pump (1200 water/s, no electricity needed) feeds 200 boilers and 400 engines. Solar takes 23.8 panels plus 20.2 accumulators per average MW ([wiki](https://wiki.factorio.com/Solar_panel)), about 44 placements per MW against about 1.7 for steam. *Agent:* 1 boiler and 2 engines per 1.8 MW, belt-fed coal.
10. **Fast inserters for high-rate links.** Chest-to-chest with no capacity bonus: yellow 0.86 items/s, long-handed 1.25, fast 2.5 ([wiki Inserters](https://wiki.factorio.com/Inserters), measured on 2.0.26). Non-bulk hand size stays 1 until `inserter-capacity-bonus-2`, which is off the path. One AM2 making green circuits eats 4.5 cables/s, which is 5+ yellow inserters or 2 fast ones.

## 2. Start state and player numbers (2.1.24)

| Item | Value | Source |
|---|---|---|
| Freeplay `created_items` | 8 iron-plate, 1 wood, 1 pistol, 10 firearm-magazine, 1 burner-mining-drill, 1 stone-furnace | freeplay.lua (2.1.24 install) |
| Crash site | When enabled, freeplay moves 8 firearm-magazine and 8 iron-plate from the player into wrecks. With `set_disable_crashsite(true)` (factobot `mod/factobot/control.lua:106`) nothing is removed, so the inventory equals `created_items` above. | freeplay.lua lines 81 to 86 |
| Character | crafting speed 1, `mining_speed = 0.5` (ore with mining_time 1 takes 2 s by hand), `reach_distance = 10`, `build_distance = 10`, `reach_resource_distance = 2.7`, `inventory_size = 80`, `running_speed = 0.15` tiles/tick (9 tiles/s) | entities.lua `character` |
| Steel axe | Trigger tech: craft 50 steel plate. Gives `character-mining-speed` +1, i.e. hand mining at 1 ore/s. | technology.lua `steel-axe` |
| Hand-craftable categories | `crafting` only. `advanced-crafting` (engine unit), `crafting-with-fluid`, `smelting`, `chemistry`, `oil-processing` and `rocket-building` are machine-only. | entities.lua `character.crafting_categories = {"crafting","hand-crafting"}` |

Stack sizes that matter for an 80-slot inventory (item.lua): plates, gears, pipe, steel, bricks, plastic, rails, belts, concrete: 100. Ore, coal, stone, sulfur, solid fuel, engines, electric engines, LDS, robot frames, drills, assemblers, furnaces, inserters: 50. Circuits, advanced circuits, cables, all science packs: 200. Processing units: 100. **Rocket fuel: 20**, so 1000 rocket fuel is 50 slots. Labs, refineries, chemical plants, steam engines: 10. Pumpjacks, offshore pumps: 20.

## 3. Recipes on the rocket path (2.1.24)

`Made in` column: "assembler 1/2/3, hand" means category `crafting`. "assembler 1/2/3 (not hand)" means `advanced-crafting`, which AM1 accepts (`crafting_categories = {"crafting","advanced-crafting"}`). "assembler 2/3 only" means `crafting-with-fluid`. Recipes without an `enabled` flag are available from the start. Every value is read from recipe.lua and technology.lua at the pinned commit. Note that 2.1 writes recipe categories as `categories = {...}` lists.

#### Smelting

| Recipe | Time (s) | Ingredients | Products | Made in | Unlocked by |
|---|---|---|---|---|---|
| iron-plate | 3.2 | 1 iron-ore | 1 iron-plate | furnace | start (enabled) |
| copper-plate | 3.2 | 1 copper-ore | 1 copper-plate | furnace | start (enabled) |
| steel-plate | 16 | 5 iron-plate | 1 steel-plate | furnace | steel-processing |
| stone-brick | 3.2 | 2 stone | 1 stone-brick | furnace | start (enabled) |

#### Basic intermediates

| Recipe | Time (s) | Ingredients | Products | Made in | Unlocked by |
|---|---|---|---|---|---|
| iron-gear-wheel | 0.5 | 2 iron-plate | 1 iron-gear-wheel | assembler 1/2/3, hand | start (enabled) |
| copper-cable | 0.5 | 1 copper-plate | 2 copper-cable | assembler 1/2/3, hand | electronics |
| electronic-circuit | 0.5 | 1 iron-plate, 3 copper-cable | 1 electronic-circuit | assembler 1/2/3, hand | electronics |
| pipe | 0.5 | 1 iron-plate | 1 pipe | assembler 1/2/3, hand | steam-power |
| iron-stick | 0.5 | 1 iron-plate | 2 iron-stick | assembler 1/2/3, hand | railway |
| engine-unit | 10 | 1 steel-plate, 1 iron-gear-wheel, 2 pipe | 1 engine-unit | assembler 1/2/3 (not hand) | engine |

#### Oil chain

| Recipe | Time (s) | Ingredients | Products | Made in | Unlocked by |
|---|---|---|---|---|---|
| basic-oil-processing | 5 | 100 crude-oil | 45 petroleum-gas | oil refinery | oil-processing |
| advanced-oil-processing | 5 | 50 water, 100 crude-oil | 25 heavy-oil, 45 light-oil, 55 petroleum-gas | oil refinery | advanced-oil-processing |
| heavy-oil-cracking | 2 | 30 water, 40 heavy-oil | 30 light-oil | chemical plant | advanced-oil-processing |
| light-oil-cracking | 2 | 30 water, 30 light-oil | 20 petroleum-gas | chemical plant | advanced-oil-processing |
| plastic-bar | 1 | 20 petroleum-gas, 1 coal | 2 plastic-bar | chemical plant | plastics |
| sulfur | 1 | 30 water, 30 petroleum-gas | 2 sulfur | chemical plant | sulfur-processing |
| sulfuric-acid | 1 | 5 sulfur, 1 iron-plate, 100 water | 50 sulfuric-acid | chemical plant | sulfur-processing |
| lubricant | 1 | 10 heavy-oil | 10 lubricant | chemical plant | lubricant |
| solid-fuel-from-light-oil | 1 | 10 light-oil | 1 solid-fuel | chemical plant | advanced-oil-processing |
| solid-fuel-from-petroleum-gas | 1 | 20 petroleum-gas | 1 solid-fuel | chemical plant | oil-processing |
| solid-fuel-from-heavy-oil | 1 | 20 heavy-oil | 1 solid-fuel | chemical plant | advanced-oil-processing |

#### Advanced intermediates

| Recipe | Time (s) | Ingredients | Products | Made in | Unlocked by |
|---|---|---|---|---|---|
| advanced-circuit | 6 | 2 electronic-circuit, 2 plastic-bar, 4 copper-cable | 1 advanced-circuit | assembler 1/2/3, hand | advanced-circuit |
| processing-unit | 10 | 20 electronic-circuit, 2 advanced-circuit, 5 sulfuric-acid | 1 processing-unit | assembler 2/3 only | processing-unit |
| battery | 4 | 20 sulfuric-acid, 1 iron-plate, 1 copper-plate | 1 battery | chemical plant | battery |
| electric-engine-unit | 10 | 1 engine-unit, 15 lubricant, 2 electronic-circuit | 1 electric-engine-unit | assembler 2/3 only | electric-engine |
| flying-robot-frame | 20 | 1 electric-engine-unit, 2 battery, 1 steel-plate, 3 electronic-circuit | 1 flying-robot-frame | assembler 1/2/3, hand | robotics |
| low-density-structure | 15 | 2 steel-plate, 20 copper-plate, 5 plastic-bar | 1 low-density-structure | assembler 1/2/3, hand | low-density-structure |
| rocket-fuel | 15 | 10 solid-fuel, 10 light-oil | 1 rocket-fuel | assembler 2/3 only | rocket-fuel |
| concrete | 10 | 5 stone-brick, 1 iron-ore, 100 water | 10 concrete | assembler 2/3 only | concrete |
| productivity-module | 15 | 5 advanced-circuit, 5 electronic-circuit | 1 productivity-module | assembler 1/2/3, hand | productivity-module |
| electric-furnace | 5 | 10 steel-plate, 5 advanced-circuit, 10 stone-brick | 1 electric-furnace | assembler 1/2/3, hand | advanced-material-processing-2 |
| rail | 0.5 | 1 stone, 1 iron-stick, 1 steel-plate | 2 rail | assembler 1/2/3, hand | railway |
| inserter | 0.5 | 1 electronic-circuit, 1 iron-gear-wheel, 1 iron-plate | 1 inserter | assembler 1/2/3, hand | electronics |
| transport-belt | 0.5 | 1 iron-plate, 1 iron-gear-wheel | 2 transport-belt | assembler 1/2/3, hand | start (enabled) |

#### Science packs

| Recipe | Time (s) | Ingredients | Products | Made in | Unlocked by |
|---|---|---|---|---|---|
| automation-science-pack | 5 | 1 copper-plate, 1 iron-gear-wheel | 1 automation-science-pack | assembler 1/2/3, hand | automation-science-pack |
| logistic-science-pack | 6 | 1 inserter, 1 transport-belt | 1 logistic-science-pack | assembler 1/2/3, hand | logistic-science-pack |
| chemical-science-pack | 24 | 2 engine-unit, 3 advanced-circuit, 1 sulfur | 2 chemical-science-pack | assembler 1/2/3, hand | chemical-science-pack |
| production-science-pack | 21 | 1 electric-furnace, 1 productivity-module, 30 rail | 3 production-science-pack | assembler 1/2/3, hand | production-science-pack |
| utility-science-pack | 21 | 3 low-density-structure, 2 processing-unit, 1 flying-robot-frame | 3 utility-science-pack | assembler 1/2/3, hand | utility-science-pack |

#### Rocket

| Recipe | Time (s) | Ingredients | Products | Made in | Unlocked by |
|---|---|---|---|---|---|
| rocket-part | 3 | 10 processing-unit, 10 low-density-structure, 10 rocket-fuel | 1 rocket-part | rocket silo | rocket-silo |
| rocket-silo | 30 | 1000 steel-plate, 1000 concrete, 100 pipe, 200 processing-unit, 200 electric-engine-unit | 1 rocket-silo | assembler 1/2/3, hand | rocket-silo |
| cargo-landing-pad | 30 | 200 concrete, 25 steel-plate, 10 processing-unit | 1 cargo-landing-pad | assembler 1/2/3, hand | rocket-silo |
| satellite (not needed: fish is a valid payload) | 5 | 100 low-density-structure, 100 solar-panel, 100 accumulator, 5 radar, 100 processing-unit, 50 rocket-fuel | 1 satellite | assembler 1/2/3, hand | rocket-silo |

#### Buildings on the path

| Recipe | Time (s) | Ingredients | Products | Made in | Unlocked by |
|---|---|---|---|---|---|
| stone-furnace | 0.5 | 5 stone | 1 stone-furnace | assembler 1/2/3, hand | start (enabled) |
| burner-mining-drill | 2 | 3 iron-gear-wheel, 1 stone-furnace, 3 iron-plate | 1 burner-mining-drill | assembler 1/2/3, hand | start (enabled) |
| electric-mining-drill | 2 | 3 electronic-circuit, 5 iron-gear-wheel, 10 iron-plate | 1 electric-mining-drill | assembler 1/2/3, hand | electric-mining-drill |
| assembling-machine-1 | 0.5 | 3 electronic-circuit, 5 iron-gear-wheel, 9 iron-plate | 1 assembling-machine-1 | assembler 1/2/3, hand | automation |
| assembling-machine-2 | 0.5 | 2 steel-plate, 3 electronic-circuit, 5 iron-gear-wheel, 1 assembling-machine-1 | 1 assembling-machine-2 | assembler 1/2/3, hand | automation-2 |
| steel-furnace | 3 | 6 steel-plate, 10 stone-brick | 1 steel-furnace | assembler 1/2/3, hand | advanced-material-processing |
| lab | 2 | 10 electronic-circuit, 10 iron-gear-wheel, 4 transport-belt | 1 lab | assembler 1/2/3, hand | electronics |
| boiler | 0.5 | 1 stone-furnace, 4 pipe | 1 boiler | assembler 1/2/3, hand | steam-power |
| steam-engine | 0.5 | 8 iron-gear-wheel, 5 pipe, 10 iron-plate | 1 steam-engine | assembler 1/2/3, hand | steam-power |
| offshore-pump | 0.5 | 3 pipe, 2 iron-gear-wheel | 1 offshore-pump | assembler 1/2/3, hand | steam-power |
| small-electric-pole | 0.5 | 1 wood, 2 copper-cable | 2 small-electric-pole | assembler 1/2/3, hand | electronics |
| medium-electric-pole | 0.5 | 4 iron-stick, 2 steel-plate, 2 copper-cable | 1 medium-electric-pole | assembler 1/2/3, hand | electric-energy-distribution-1 |
| burner-inserter | 0.5 | 1 iron-plate, 1 iron-gear-wheel | 1 burner-inserter | assembler 1/2/3, hand | start (enabled) |
| long-handed-inserter | 0.5 | 1 iron-gear-wheel, 1 iron-plate, 1 inserter | 1 long-handed-inserter | assembler 1/2/3, hand | automation |
| fast-inserter | 0.5 | 2 electronic-circuit, 2 iron-plate, 1 inserter | 1 fast-inserter | assembler 1/2/3, hand | fast-inserter |
| underground-belt | 1 | 10 iron-plate, 5 transport-belt | 2 underground-belt | assembler 1/2/3, hand | logistics |
| splitter | 1 | 5 electronic-circuit, 5 iron-plate, 4 transport-belt | 1 splitter | assembler 1/2/3, hand | logistics |
| pipe-to-ground | 0.5 | 10 pipe, 5 iron-plate | 2 pipe-to-ground | assembler 1/2/3, hand | steam-power |
| pumpjack | 5 | 5 steel-plate, 10 iron-gear-wheel, 5 electronic-circuit, 10 pipe | 1 pumpjack | assembler 1/2/3, hand | oil-gathering |
| oil-refinery | 8 | 15 steel-plate, 10 iron-gear-wheel, 10 stone-brick, 10 electronic-circuit, 10 pipe | 1 oil-refinery | assembler 1/2/3, hand | oil-processing |
| chemical-plant | 5 | 5 steel-plate, 5 iron-gear-wheel, 5 electronic-circuit, 5 pipe | 1 chemical-plant | assembler 1/2/3, hand | oil-processing |
| storage-tank | 3 | 20 iron-plate, 5 steel-plate | 1 storage-tank | assembler 1/2/3, hand | fluid-handling |
| pump | 2 | 1 engine-unit, 1 steel-plate, 1 pipe | 1 pump | assembler 1/2/3, hand | fluid-handling |
| solar-panel | 10 | 5 steel-plate, 15 electronic-circuit, 5 copper-plate | 1 solar-panel | assembler 1/2/3, hand | solar-energy |
| accumulator | 10 | 2 iron-plate, 5 battery | 1 accumulator | assembler 1/2/3, hand | electric-energy-accumulators |
| speed-module | 15 | 5 advanced-circuit, 5 electronic-circuit | 1 speed-module | assembler 1/2/3, hand | speed-module |
| productivity-module-2 | 30 | 4 productivity-module, 5 advanced-circuit, 5 processing-unit | 1 productivity-module-2 | assembler 1/2/3, hand | productivity-module-2 |
| productivity-module-3 | 60 | 4 productivity-module-2, 5 advanced-circuit, 5 processing-unit | 1 productivity-module-3 | assembler 1/2/3, hand | productivity-module-3 |
| iron-chest | 0.5 | 8 iron-plate | 1 iron-chest | assembler 1/2/3, hand | start (enabled) |
| wooden-chest | 0.5 | 2 wood | 1 wooden-chest | assembler 1/2/3, hand | start (enabled) |

Trigger techs on the path, which need no science packs (technology.lua): `steam-power` (craft 50 iron plate: unlocks pipe, pipe-to-ground, offshore pump, boiler, steam engine); `electronics` (craft 10 copper plate: cable, circuit, lab, inserter, small pole); `automation-science-pack` (craft a lab); `oil-processing` (mine crude oil, i.e. a pumpjack running: refinery, chemical plant, basic oil, solid fuel from petroleum). `electric-mining-drill` is its own tech in 2.x (25 red × 10 s).

## 4. Machines (2.1.24)

| Machine | Speed | Power | Modules | Notes |
|---|---|---|---|---|
| Assembling machine 1 | 0.5 | 75 kW | 0 | crafting, advanced-crafting |
| Assembling machine 2 | 0.75 | 150 kW | 2 | adds crafting-with-fluid |
| Assembling machine 3 | 1.25 | 375 kW | 4 | Off the rocket-silo closure (`automation-3`: 150 × 60 s, needs `production-science-pack` first), and its recipe eats 4 speed modules. Skip. |
| Stone furnace | 1 | 90 kW burner | 0 | 0.3125 plates/s; coal 0.0225/s while running |
| Steel furnace | 2 | 90 kW burner | 0 | 0.625 plates/s; half the fuel per plate of a stone furnace |
| Electric furnace | 2 | 180 kW | 2 | No fuel logistics; it is also a purple-pack ingredient |
| Chemical plant | 1 | 210 kW | 3 | |
| Oil refinery | 1 | 420 kW | 3 | |
| Burner mining drill | 0.25 ore/s | 150 kW burner (0.0375 coal/s) | 0 | 2×2 area |
| Electric mining drill | 0.5 ore/s | 90 kW | 3 | 5×5 area (`resource_searching_radius = 2.49`) |
| Pumpjack | 1 cycle/s | 90 kW | 2 | 10 crude/s per 100% yield; decays to a floor of 20% of initial yield or 2/s ([wiki](https://wiki.factorio.com/Pumpjack)); crude `normal = 300000` = 100% |
| Lab | 1 | 60 kW | 2 | |
| Rocket silo | 1 | 250 kW crafting, 3.99 MW active | 4 | 100 parts per rocket (`rocket_parts_required = 100`) |
| Offshore pump | 1200 water/s | none (`energy_source = void`) | | |
| Boiler | 60 steam/s | burns 1.8 MW | | 165 °C; steam heat capacity 0.2 kJ/°C, so 30 kJ per unit |
| Steam engine | 30 steam/s | 900 kW out | | 1 boiler : 2 engines |

Ore mining time is 1 for iron, copper, coal and stone (resources.lua). Mining productivity is off the rocket-silo closure, so raw ore equals mined ore below.

Fuel values (item.lua): wood 2 MJ, coal 4 MJ, solid fuel 12 MJ, rocket fuel 100 MJ.

### Modules and beacons: mostly skip

| Module | Effect (item.lua) |
|---|---|
| Speed 1 | +20% speed, +50% energy |
| Productivity 1 | +4% productivity, −5% speed, +40% energy |
| Productivity 3 | +10% productivity, −15% speed, +80% energy |

- **Skip beacons.** `effect-transmission` is off the rocket-silo closure. A beacon costs 20 green circuits, 20 advanced circuits, 10 steel and 10 cables. Each beacon also means 1 place plus 2 module inserts, for a few percent on a few machines. Zaspar beacons only the silo; the silo crafts for 540 s with prod 3s (300 s without), so even 20 beacons save under 8 minutes.
- **Skip productivity 1 in ordinary assemblers.** AM2 has 2 slots, so +8% output for 2 actions per machine plus a module that costs 5 AC + 5 EC. Worth it only on the few long-running high-value machines.
- **Do use 4 × productivity 3 in the silo** (§1 item 4). The techs are mandatory either way.
- **Speed modules in pumpjacks** only if total oil yield is low. Zaspar: "If your total yield is less than about 1800%, you may need to come back and add speed modules to the pumpjacks later."
- **Construction robots are useless here** (no ghosts), so skip robot-frame production beyond the 334 frames that yellow packs consume.

### Belts, inserters, poles, pipes

| Entity | Throughput / reach | Source |
|---|---|---|
| Transport belt (yellow) | 15 items/s (7.5 per lane); `speed = 0.03125` | transport-belts.lua; [wiki](https://wiki.factorio.com/Transport_belts/Physics) |
| Fast belt (red) | 30 items/s | same; `logistics-2` is on the path because `railway` needs it |
| Underground belt (yellow) | `max_distance = 5` | transport-belts.lua |
| Burner inserter | 0.79 items/s chest-to-chest | [wiki](https://wiki.factorio.com/Inserters) |
| Inserter | 0.86 items/s (70 ticks per swing) | wiki; rotation 0.014 turns/tick in data |
| Long-handed inserter | 1.25 items/s | wiki |
| Fast inserter | 2.5 items/s | wiki; off the closure (`fast-inserter`: 30 red × 15 s) |
| Small electric pole | wire 7.5, supply 5×5 | entities.lua |
| Medium electric pole | wire 9, supply 7×7 | entities.lua; `electric-energy-distribution-1` is in the closure |
| Big electric pole | wire 32, supply 4×4 | entities.lua |
| Pipe-to-ground | `max_underground_distance = 10` | entities.lua |
| Pipes (2.x fluid system) | No flow falloff inside a segment. Each input or output connection is capped at 6000/s in theory, about 4200/s in practice. A segment longer than 320 tiles stops flowing unless split by a pump. | [wiki Fluid system](https://wiki.factorio.com/Fluid_system); `default_pipeline_extent = 320` in utility-constants.lua |

Planning rule of thumb `[INFERENCE]`: 30 electric drills (15/s) or 24 steel furnaces (15/s) fill one yellow belt. Zaspar's "half a lane of iron mining (15 miners) and a half lane of iron smelting (24 furnaces)" uses stone furnaces at 0.3125/s: 24 × 0.3125 = 7.5/s.

Automatic insertion limits ([wiki Inserters](https://wiki.factorio.com/Inserters)): inserters fill a crafting machine with ingredients for at least 2 crafts. Burner fuel stops at 5 items. Labs take packs for at least 2 research units.

## 5. Oil processing and power

### Oil

| Recipe (refinery speed 1) | Per refinery per second |
|---|---|
| Basic | 20 crude → 9 petroleum |
| Advanced | 20 crude + 10 water → 5 heavy + 9 light + 11 petroleum |
| Heavy cracking (chem plant) | 20 heavy + 15 water → 15 light |
| Light cracking (chem plant) | 15 light + 15 water → 10 petroleum |
| Solid fuel from light | 10 light → 1 solid fuel |
| Solid fuel from petroleum | 20 petroleum → 1 solid fuel |
| Solid fuel from heavy | 20 heavy → 1 solid fuel |

- Ratios for pure petroleum: refinery : heavy cracking : light cracking = 20:5:17, close enough at 8:2:7. One refinery with one plant of each cracking type gives 19.5 petroleum/s ([wiki Oil processing](https://wiki.factorio.com/Oil_processing)).
- **Solid fuel route.** Make solid fuel from light oil. 20 petroleum costs 30 light oil through cracking, so the petroleum route takes 3× the light oil per solid fuel. One rocket fuel = 10 solid fuel + 10 light = **110 light oil**. At 1 rocket fuel/s that is 10 chemical plants on solid fuel and 20 AM2 (15 s / 0.75) `[INFERENCE]`.
- **Path-wide oil demand** `[INFERENCE]`: 440,958 petroleum, 110,000 light and 8,000 heavy (lubricant). Covering that with advanced processing and the minimum cracking takes 5,316 refinery runs = **531,600 crude**, plus 3,122 heavy-cracking and 7,429 light-cracking runs. Averaged over the run that is about 4 refineries : 1 heavy-cracking : 2.2 light-cracking plants. During the blue-only stage use 20:5:17. During rocket-fuel production most light oil goes to solid fuel and light cracking nearly stops.
- Advanced processing stops when any of its three outputs backs up. *Agent:* every output needs a sink (cracking, solid fuel or a storage tank). Before advanced oil is researched, basic processing (one input, one output) is the simplest build. Only 75 blue packs are needed before switching.
- Scale: 531.6k crude over a 2 h oil phase is 74 crude/s, about 7.4 pumpjacks at 100% yield. Zaspar picks maps with "~1600% total oil yield (~12 pumpjacks)", i.e. 160 crude/s.

### Power

| Fact | Value | Source |
|---|---|---|
| Boiler : engine | 1 : 2 (1.8 MW : 0.9 MW) | entities.lua; [wiki](https://wiki.factorio.com/Power_production) |
| Water to steam | 1 water → 10 steam (since 2.0.7) | [wiki Boiler](https://wiki.factorio.com/Boiler) |
| Offshore pump | 1200 water/s → 200 boilers, 400 engines, 360 MW | wiki Power production; data `pumping_speed = 20`/tick |
| Coal per boiler at full load | 0.45/s (1.8 MW / 4 MJ); one 50-coal stack lasts 111 s | [INFERENCE] |
| Solid fuel per boiler at full load | 0.15/s; one 50 stack lasts 333 s | [INFERENCE] |
| Solar | 42 kW average per panel; 23.8 panels + 20.2 accumulators per MW | [wiki Solar panel](https://wiki.factorio.com/Solar_panel) |
| Inserter energy | 5 kJ per movement and per rotation, 0.4 kW drain (fast: 7 kJ, 0.5 kW) | entities.lua |

Path-wide electricity `[INFERENCE]`: about 234 GJ (drills 99.7, AM2 93.3, labs 13.5, chemical plants 11.8, refineries 11.2, pumpjacks 4.8; inserters excluded). As boiler coal that is 58.5k coal, the largest single coal use. Furnace fuel adds about 20k coal (steel furnaces) and plastic plus the silo add 19.1k coal as ingredients. Total coal is about 97.6k. *Agent:* belt coal to the boilers from dedicated drills. Hand-inserting coal at 0.45/s per boiler is impossible to keep up with.

## 6. Ratio tables

Method `[INFERENCE]`: expand each recipe tree down to ore, coal, stone, water and oil products using the pinned recipes. Solve oil with advanced processing and the minimum cracking (§5). Machine count = crafts/s × recipe time / machine speed. Assemblers are AM2 (0.75); multiply by 1.5 for AM1. Furnaces are stone furnaces (speed 1); halve the counts for steel or electric furnaces. Drills are electric (0.5/s) and include their own furnace coal. Power excludes labs and inserters. Pumpjacks assume 100% yield (10 crude/s).

### Per 1 pack/s

| Pack (1/s) | AM2 | Stone furnaces | Chem plants | Refineries | Drills | Iron ore/s | Copper ore/s | Stone/s | Coal/s (ingr. + furnace) | Crude/s | Water/s | Power MW | Steam engines |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Red | 7.3 (6.67 pack, 0.67 gear) | 9.6 | 0 | 0 | 6.4 | 2.0 | 1.0 | 0 | 0 + 0.22 | 0 | 0 | 1.7 | 1.9 |
| Green | 11.7 | 22.4 | 0 | 0 | 15.0 | 5.5 | 1.5 | 0 | 0 + 0.50 | 0 | 0 | 3.1 | 3.4 |
| Blue | 50.3 | 78.4 | 3.9 | 1.9 | 45.5 | 12.0 | 7.5 | 0 | 1.5 + 1.76 | 38.5 | 58 | 13.6 | 15.1 |
| Purple | 68.2 | 373.3 | 7.1 | 3.4 | 190.1 | 52.5 | 19.2 | 11.7 | 3.3 + 8.4 | 68.4 | 91 | 30.9 | 34.3 |
| Yellow | 98.5 | 308.8 | 13.5 | 5.3 | 187.9 | 33.3 | 49.8 | 0 | 3.8 + 6.9 | 106.8 | 192 | 37.7 | 41.9 |
| Rocket part (1 per 3 s, silo max) | 373.3 | 1110.4 | 57.2 | 29.2 | 707.3 | 113.7 | 200.0 | 0 | 15 + 25 | 584 | 466 | 149.4 | 166 |

Per-pack breakdown at 1/s (AM2 unless noted):

- **Red**: 6.67 pack, 0.67 gear; stone furnaces 6.4 iron, 3.2 copper.
- **Green**: 8 pack, 1 cable, 1 gear, 0.67 inserter, 0.67 circuit, 0.33 belt; furnaces 17.6 iron, 4.8 copper.
- **Blue**: 16 pack, 13.33 engine (AM1 ok), 12 advanced circuit, 5 cable, 2 circuit, 1.33 pipe, 0.67 gear; chem 1.5 plastic, 0.25 sulfur, 0.48 heavy crack, 1.63 light crack; 1.92 refinery; furnaces 38.4 iron, 24 copper, 16 steel.
- **Purple**: 26.7 advanced circuit, 12.8 cable, 9.33 pack, 6.67 productivity module, 5.56 circuit, 3.33 rail, 2.22 electric furnace, 1.67 iron stick; chem 3.33 plastic plus cracking; 3.42 refinery; furnaces 168 iron, 133 steel, 61.3 copper, 10.7 brick.
- **Yellow**: 20 LDS, 19.4 cable, 11.8 circuit, 10.7 advanced circuit, 9.33 pack, 8.89 processing unit, 8.89 robot frame, 4.44 electric engine, 4.44 engine, 0.44 pipe, 0.22 gear; chem 3.83 plastic, 2.67 battery, 0.83 sulfur, 0.5 lubricant, 0.33 acid plus cracking; 5.34 refinery; furnaces 159 copper, 107 iron, 42.7 steel.
- **Rocket part** at 1/3 s: 88.9 cable, 66.7 LDS, 66.7 rocket fuel, 53.3 advanced circuit, 53.3 circuit, 44.4 processing unit; chem 33.3 solid fuel, 15 plastic plus cracking; 29.2 refinery; furnaces 640 copper, 364 iron, 107 steel.

### Rates a 2.x record runner targets (Zaspar's guide)

| Build | Count in guide | Implied rate `[INFERENCE]` |
|---|---|---|
| Red science | 10 assemblers | 1.0/s with AM1, 1.5/s with AM2 |
| Green science | 12 assemblers | 1.5/s with AM2 |
| Labs | 32, later "double the number of labs to 64" | 64 labs at speed 1 use 1.07 packs/s of each type on the 60 s rocket-silo tech |
| Advanced circuits | 24 AM2 | 3.0/s |
| Blue science | 14 AM2 | 0.875/s |
| Refineries / chem plants | 10 / 4, then advanced oil | about 180 to 200 crude/s |
| Purple science | 14 AM2 | 1.5/s |
| Yellow science | 12 AM2 | 1.29/s |
| Rocket fuel | 14 AM2 | 0.7/s |

For the agent these are far too many placements. §9 gives a smaller plan.

## 7. Total raw resources for the whole rocket path

Scope: every pack in the `rocket-silo` prerequisite closure (red 5960, green 5785, blue 3350, purple 1600, yellow 1000; same counts as `docs/human-baselines.md` §3c, recomputed here from technology.lua), plus 100 rocket parts without silo productivity, plus 1 rocket silo, plus 1 raw fish. Excluded: the factory itself, optional techs (electric mining drill 25 red, research speed, fast inserter), and any cargo landing pad. Mandatory research is 224,425 lab-seconds (62.3 lab-h at speed 1).

Method `[INFERENCE]`: expand all of the above to raw materials with the same calculator as §6, then solve oil once for the combined demand.

### Per-unit raw cost

Oil products are shown as fluid amounts. "Crude eq." solves oil for that item alone with advanced processing, so for items needing only heavy or light oil it charges the co-products as waste. Machine-seconds are at speed 1 and cover crafting and smelting only (no mining).

| Item (1 unit) | Iron ore | Copper ore | Stone | Coal (ingr.) | Petroleum | Light | Heavy | Crude eq. | Machine-s |
|---|---|---|---|---|---|---|---|---|---|
| Steel plate | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 32.0 |
| Electronic circuit | 1 | 1.5 | 0 | 0 | 0 | 0 | 0 | 0 | 9.25 |
| Advanced circuit | 2 | 5 | 0 | 1 | 20 | 0 | 0 | 20.5 | 35.1 |
| Processing unit | 24.1 | 40 | 0 | 2 | 47.5 | 0 | 0 | 48.7 | 267 |
| Engine unit | 9 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 56.3 |
| Electric engine | 11 | 3 | 0 | 0 | 0 | 0 | 15 | 60 | 89.3 |
| Battery | 1.4 | 1 | 0 | 0 | 30 | 0 | 0 | 30.8 | 16.3 |
| Robot frame | 21.8 | 9.5 | 0 | 0 | 60 | 0 | 15 | 69.2 | 198 |
| LDS | 10 | 20 | 0 | 2.5 | 50 | 0 | 0 | 51.3 | 151 |
| Solid fuel (light) | 0 | 0 | 0 | 0 | 0 | 10 | 0 | 15.7 | 1.98 |
| Rocket fuel | 0 | 0 | 0 | 0 | 0 | 110 | 0 | 173 | 35.8 |
| Concrete | 0.1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 2.6 |
| Productivity module | 15 | 32.5 | 0 | 5 | 100 | 0 | 0 | 103 | 237 |
| Electric furnace | 60 | 25 | 20 | 5 | 100 | 0 | 0 | 103 | 532 |
| Red pack | 2 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 15.1 |
| Green pack | 5.5 | 1.5 | 0 | 0 | 0 | 0 | 0 | 0 | 31.2 |
| Blue pack | 12 | 7.5 | 0 | 1.5 | 37.5 | 0 | 0 | 38.5 | 122 |
| Purple pack | 52.5 | 19.17 | 11.67 | 3.33 | 66.7 | 0 | 0 | 68.4 | 435 |
| Yellow pack | 33.3 | 49.8 | 0 | 3.83 | 101.7 | 0 | 5 | 107 | 402 |
| Rocket part | 341 | 600 | 0 | 45 | 975 | 1,100 | 0 | 1,752 | 4,433 |
| Rocket silo | 12,220 | 8,600 | 1,000 | 400 | 9,500 | 0 | 3,000 | 12,000 | 105,444 |
| Cargo landing pad (not needed) | 386 | 400 | 200 | 20 | 475 | 0 | 0 | 487 | 4,016 |

### Totals for the rocket path

| Bundle | Iron ore | Copper ore | Stone | Coal (ingredient) | Crude oil | Water (chem + oil) |
|---|---|---|---|---|---|---|
| Research packs | 201,271 | 120,263 | 18,667 | 14,192 | 345,086 | 533,196 |
| 100 rocket parts | 34,100 | 60,000 | 0 | 4,500 | 175,214 | 139,658 |
| Rocket silo | 12,220 | 8,600 | 1,000 | 400 | 12,000 | 23,850 |
| **All (joint oil solve)** | **247,591** | **188,862** | **19,667** | **19,092** | **531,581** | **696,803** |
| Plus fuel `[INFERENCE]` | | | | +20k furnace coal (steel furnaces), +58.5k boiler coal | | +7.8M water as steam |

Intermediate counts for the whole path: 247,491 iron plates, 188,862 copper plates, 22,550 steel, 284,472 cables (142,236 crafts), 76,035 green circuits, 14,092 advanced circuits, 1,867 processing units, 38,184 plastic bars (19,092 crafts), 18,521 gears, 16,000 rails (8,000 crafts), 7,867 pipes, 3,883 engines, 534 electric engines, 2,000 LDS, 1,000 rocket fuel (10,000 solid fuel), 668 batteries, 334 robot frames (1000 / 3 yellow crafts, rounded up), 534 electric furnaces and 534 productivity modules (both eaten by purple packs, 1600 / 3 crafts rounded up), 5,833 bricks, 100 concrete crafts (1,000 concrete).

Machine-seconds for the whole path at real machine speeds: AM2 621,766; steel furnace 887,899; electric drill 1,107,481 (ore plus furnace and boiler coal); chemical plant 56,086; refinery 26,579; pumpjack 53,158 (at 10/s); lab 224,425; silo 300. **Total W ≈ 2.98M machine-seconds.**

With 4 × productivity 3 in the silo, the rocket-part row drops by 28% (72 crafts instead of 100).

## 8. Research stages and their workloads

Stages, computed from the prerequisite closures in technology.lua:

- **A**: closure of `chemical-science-pack`.
- **B'**: every remaining rocket-silo-closure tech that needs only red, green and blue. These can run before purple or yellow exists.
- **C'**: `speed-module-3`, `productivity-module-3` and `rocket-silo`.

| Stage | Packs (r/g/b/p/y) | Lab-s | AM2-s | Steel-furnace-s | Drill-s | Chem-s | Refinery-s | Total machine-s | n* (c=60 s) | T* h (c=60) | n* (c=120 s) | T* h (c=120) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | 1050/915/0/0/0 | 20,825 | 18,375 | 15,288 | 19,798 | 0 | 0 | 74,286 | 35 | 1.17 | 25 | 1.66 |
| B' | 3310/3270/1750/0/0 | 107,600 | 150,507 | 121,112 | 144,590 | 6,764 | 3,365 | 540,669 | 95 | 3.16 | 67 | 4.47 |
| C' | 1600/1600/1600/1600/1000 | 96,000 | 318,644 | 541,387 | 574,896 | 31,078 | 13,889 | 1,603,671 | 163 | 5.45 | 116 | 7.71 |
| Silo + 100 parts | | 0 | 134,240 | 210,112 | 251,095 | 18,244 | 9,325 | 641,965 | 103 | 3.45 | 73 | 4.88 |

Pumpjack-seconds (B' 6.7k, C' 27.8k, parts 18.7k) are in the totals but not shown as columns. The A row counts furnaces as steel furnaces; in reality stage A uses stone furnaces, which doubles that column.

The rocket-silo tech alone is 60,000 lab-s (1000 × 60 s), and the two module-3 techs are 18,000 lab-s each. C' therefore needs labs as much as factory: with 16 labs and research speed 1+2 (+50%), C' research takes 96,000 / 24 = 4,000 s (67 min) `[INFERENCE]`.

How to read n* and T* `[INFERENCE]`: c is the game time the agent spends per machine, including its inserters, pole share, belts, recipe setting and fuelling. At 15 s per action and about 4 to 8 actions per machine, c is about 60 to 120 s. Machines carry over between stages (mining and smelting especially), so the single-pool figure for the whole path (T* ≈ 7.4 h at c = 60 s, 10.5 h at c = 120 s) is a lower bound. The sum of the stage rows (13.2 h at c = 60 s) is closer to an upper bound for a plan that builds each stage from scratch.

## 9. A minimal factory for this agent `[INFERENCE]`

Goal: reach the rocket in roughly 7 to 14 h of game time with about 400 placed machines at the peak (about 450 with boilers and engines). The low end matches the route in [speedrun-routes.md §11](speedrun-routes.md) (about 7 h at 15 s per action) and the single-pool bound of §8; the high end is the §8 sum of stages built from scratch. Production rates are picked so that each stage's production time is about the same as its build time. Counts below come from the §6 calculator at the stated rates. Furnaces are steel unless noted; assemblers are AM2 (×1.5 for AM1).

| Stage | Target rates | Production machines (at this stage's peak, reused ones included) | Drills | Oil | Labs | Power | Duration at rate |
|---|---|---|---|---|---|---|---|
| A: red+green | 0.3/s each | 5.7 AM2 ≈ 9 AM1 (3 red, 4 green, 1 gear, plus cable/circuit/inserter/belt shared), 9.6 stone furnaces | 6.4 | none | 6 | 1.4 MW + 0.4 MW labs: 1 boiler, 2 engines (at the limit) | 1050/0.3 = 58 min |
| B': red/green 0.5, blue 0.25 | 0.5 / 0.5 / 0.25 | 22 AM2 (4 blue, 3.3 engine, 3 adv. circuit, 3.3 red, 4 green, 1.75 cable, ...), 18 steel furnaces (incl. 2 for steel), 2 chem plants (plastic, sulfur) | 21 | 1 refinery (half used; basic first, then advanced), 1 pumpjack at 100% | 16 (research speed 1+2 here) | 5.7 MW + 1 MW labs: 4 boilers, 8 engines | 1750 blue / 0.25 = 1.9 h; 107,600 lab-s / (16 × 1.5) = 1.25 h |
| C': all five at 0.25/s | 0.25 each | 59 AM2, 99 steel furnaces, 6 chem plants | 107 | 2.7 refineries, 5.3 pumpjacks | 16 | 21.4 MW + 1 MW labs: 13 boilers, 25 engines | 1600 / 0.25 = 1.8 h |
| Parts + silo, overlapped with C' | 100 parts in 6400 s; silo in 1 h | +17.5 AM2 (3.1 LDS, 3.1 rocket fuel, 2.1 PU, ...), +26 furnaces, +2.7 chem plants (1.6 solid fuel) for the parts; +6 AM2, +12 furnaces for the silo's steel, concrete, 200 PU and 200 electric engines | +32 for the parts, +13 for the silo | +1.4 refineries, +2.7 pumpjacks | | +7.1 MW: +4 boilers, +8 engines | 1.8 h |

These counts are maxima: lower-tier machines get reused (the B' red/green line covers C'), and C' is the peak. Several of the AM2s above are fractions, so one machine can serve two recipes over time with a `recipe` change.

Layout rules that cut actions:
- **Drill to furnace to inserter to chest columns** for plates. That is 4 entities per 0.5 ore/s, no ore belt. An iron chest holds 3,200 plates (32 slots × 100), so a single take action empties it.
- **Direct insertion chains** instead of belts where rates allow: gear → red-pack assembler, engine → blue-pack assembler, cable → circuit (fast inserters).
- **Coal**: about one electric drill on coal per boiler at full load (0.5 coal/s per drill against 0.45 coal/s per boiler): 4 for B', 13 for C'. Belt the output past the boilers, or let drills drop straight into them. Burner furnaces need 0.0225 coal/s each, so a 50-coal stack lasts 37 minutes; refilling by hand is about 1 action per furnace per 37 min.
- **Hand-craft** every building and the silo. The silo is a 30 s hand-craft once 1000 steel, 1000 concrete, 100 pipe, 200 PU and 200 EEU are in the inventory (27 slots).
- **Hand-feed the silo** from chests or with inserters. 1000 rocket fuel is 50 slots, so it takes several trips.
- **Labs**: chain lab to lab with inserters. Each lab takes all five pack types.

This plan runs well below record pace: Zaspar's 1:59 run targets 4 to 6× these rates and uses construction robots. Its game-time estimate rests on the action-cost assumption c, not on production limits.

## 10. 1.1 vs 2.x differences that change these chains

Diffed from `1.1.110` and `2.1.24` data unless noted.

| Topic | 1.1 | 2.1.24 | Effect |
|---|---|---|---|
| Rocket part | 10 LDS + 10 rocket control units + 10 rocket fuel. RCU = 1 PU + 1 speed module, 30 s. | 10 LDS + 10 processing units + 10 rocket fuel, 3 s | The 1000 speed modules of 1.1 disappear: 150 iron and 325 copper ore and about 1,030 crude saved per part `[INFERENCE]` |
| Low density structure | 20 s | 15 s | −25% machines |
| Rocket fuel | 30 s | 15 s (still 10 solid fuel + 10 light oil) | −50% machines |
| Solid fuel (all three) | 2 s | 1 s | −50% chem plants |
| Water to steam | 1 : 1 (20 boilers per pump) | 1 : 10 (200 boilers per pump), since 2.0.7 | One offshore pump for the whole run |
| Offshore pump recipe | 1 gear + 1 pipe + 2 circuits | 2 gears + 3 pipes | No circuits needed for power |
| Medium pole | 2 copper plate | 2 copper cable | trivial |
| Inserter extension speed | 0.03 / fast 0.07 / long 0.0457 | 0.035 / 0.1 / 0.05 | Rotation unchanged, so throughput is about the same |
| Starting recipes | Electric drill, lab, inserter and steam power available at start. 1.1.110 recipe.lua sets no `enabled = false` on them; checked with a line scan, not a full load. | Trigger techs (craft 50 iron plate, craft 10 copper plate, craft a lab, mine crude); electric mining drill costs 25 red | Early build order changes; see the tech-tree research |
| Payload | None needed (since 0.17) | Required: fish or satellite (2.0.7) | Mine a fish |
| Fluid system | Distance-based falloff | Segment model, 320-tile extent | Long pipes are fine without pumps up to 320 tiles |
| Rocket silo, all machine speeds, science pack recipes, oil recipes, concrete, steel, circuits | same | same | 1.1 ratio calculators remain valid for these |

`docs/human-baselines.md` §3c found mandatory research cost nearly the same: 17,865 pack-units in 1.1 vs 17,695 in 2.x.

## 11. Open items

- Main's test found that `launch_rocket()` succeeds with an empty rocket, so the game enforces the payload rule only in the GUI. fac's `launch` (decision 49) enforces it itself and rejects an empty rocket, and `mine` takes a fish in reach, so runs must bring a fish.
- How long the launch animation takes before `on_rocket_launched` fires, i.e. the extra ticks after the last part: UNVERIFIED. The wiki lists 1632 ticks (27.2 s) as the minimum interval between back-to-back base-game launches.
- The action-cost constant c is assumed, not measured. Playtest logs should give the real per-action game-time cost.
