# Tech tree for a rocket speedrun (Factorio 2.1.24, base game, peaceful)

Research date: 2026-11-02. Audience: the factobot agent and whoever writes its player profile. Tags: `[INFERENCE]` = my own derivation; `UNVERIFIED` = claim I could not confirm; `UNVERIFIED-2.x` = a 1.1 source that I could not confirm for 2.x.

## Summary: most valuable takeaways, ranked by time saved

1. **Size labs to the pack supply, then buy lab speed instead of more labs.** A lab finishes a unit in `T / S` seconds (T = unit time, S = lab speed), so the labs needed to keep up with a supply of R units/s is `L = R × T / S` ([wiki Research](https://wiki.factorio.com/Research)). Research speed 1 + 2 cost 2 `fac research` calls and 300 red + 300 green packs, and they give S = 1.5. That does the work of 50% more labs. For an agent that pays one `place` call per lab plus one per feeding inserter, that is the cheapest throughput in the game [INFERENCE].
2. **Build purple before yellow.** `productivity-module-3` and `speed-module-3` together cost 36,000 lab-s and need only R+G+B+P packs. Research them while yellow is being built, and only `rocket-silo` (60,000 lab-s) is left once yellow flows. At 32 labs × 1.5 speed that keeps 12.5 minutes of research off the end of the run [INFERENCE from the computed costs below].
3. **The blue path is gated by a trigger, not by labs.** `oil-processing` (refinery, chemical plant) has no lab cost. It completes the first time a pumpjack extracts crude oil, after `oil-gathering` is researched. Plastics, advanced circuits, sulfur and blue science cannot even be queued before that (`fac research` rejects them). Research `oil-gathering` early, get a powered pumpjack on oil as soon as possible, and fill the lab time in between with required R+G techs that have no oil dependency (logistics-2, railway, concrete, solar-energy, electric-energy-distribution-1).
4. **`electric-energy-distribution-1` is mandatory in 2.x, so research it early.** Big poles reach 32 tiles and small poles 7.5, so a 500-tile line to an oil field takes about 16 big poles instead of 67 small ones. Medium poles cover a 7×7 area against 5×5 for small poles, about half as many poles inside the base. Each pole is one `place` call.
5. **`advanced-material-processing` and `automation-2` are mandatory. Get them right after green.** Steel furnaces run at crafting speed 2 on the same 90 kW as a speed-1 stone furnace, which halves furnace count and fuel inserts. Assembler 2 runs at 0.75 against 0.5, so 33% fewer assemblers. Both mean fewer `place` and `insert` calls.
6. **The steel axe is free in 2.x.** It is a trigger tech: craft 50 steel plates, and furnace output counts. Its effect is +100% character mining speed, so hand-mining ore drops from 2 s to 1 s per ore and trees from 1.1 s to 0.55 s. Research `steel-processing` early and the axe arrives with the first 50 steel.
7. **Skip what needs blueprints or ghosts, and skip defense.** Construction robots, worker-robot speed, beacons, car, circuit network and all military are things runners research that do not pay for this agent. Runners use bots to build blueprints and the car to reach oil, and `fac` has neither ghosts nor a drive command.
8. **Plan for `fac` queue mechanics.** `fac research TECH` queues TECH and, before it, every prerequisite that is neither researched nor queued; trigger techs cannot be queued; cancelling a tech drops the techs queued behind it that depend on it. The queue holds at most 7 techs, checked in a factobot test world (§5). The whole plan below is 45 `research` calls in 9 batches, plus `fast-inserter` whenever a slot is free (§8).
9. **Keep red and green running to the end.** Every tech after the blue gate still consumes red and green. The final `rocket-silo` alone needs 1000 of each of the five packs.

Required research in total: **44 technologies (4 triggers + 40 lab techs), 17,695 packs, 224,425 lab-seconds (62.3 lab-hours at speed 1)**. With the optional techs in the §8 batches it is 19,020 packs and 251,675 lab-s.

---

## 1. Sources and pinning

| What | Source | Pin |
|---|---|---|
| Technology data (2.1.24) | https://github.com/wube/factorio-data/blob/acf5a342afcb66c066b9d88d202e8622112da117/base/prototypes/technology.lua | commit `acf5a342afcb66c066b9d88d202e8622112da117` (tag `2.1.24`, "added version 2.1.24", 2026-10-27); `base/info.json` says `"version": "2.1.24"` |
| Recipes, entities, items (2.1.24) | same commit: `base/prototypes/recipe.lua`, `item.lua`, `entity/entities.lua`, `entity/mining-drill.lua`, `entity/resources.lua`, `entity/trees.lua` | same |
| 2.0 comparison | https://raw.githubusercontent.com/wube/factorio-data/2.0.72/base/prototypes/technology.lua | tag `2.0.72` |
| 1.1 comparison | https://raw.githubusercontent.com/wube/factorio-data/1.1.110/base/prototypes/technology.lua | tag `1.1.110` |
| Trigger techs, steel axe change, research queue always on | [FFF #376](https://factorio.com/blog/post/fff-376) | fetched 2026-11-02 |
| Lab speed formula, lab chains, saved progress | [wiki Research](https://wiki.factorio.com/Research) | fetched 2026-11-02 |
| Mining productivity applies to pumpjacks | [wiki Mining productivity (research)](https://wiki.factorio.com/Mining_productivity_(research)) | page modified 2026-10-30 |
| Inserter throughput (2.0.26 measurements) | [wiki Inserters](https://wiki.factorio.com/Inserters) | fetched 2026-11-02 |
| Zaspar's 2.x speedrun guide (current 2.x Default Settings WR holder, 1:59:01) | https://docs.google.com/presentation/d/12dO2YmmOUK_R528-jCKo2nSdJUKNkp-vvXWqDHS3PKo/export/txt | fetched 2026-11-02; has 2.0 and 2.1 example seeds |
| 1.1-era beginner speedrun guide (Nefrums seed; the predecessor of Zaspar's guide) | mirror https://factorio.okcomp.ir/docs/speedrun.pdf | 1.1 tech names (Advanced Electronics, RCU) |
| Mazmot's Any% cheatsheet | https://hackmd.io/@Mazmot/HyMO_CBQp | 1.1 era (research queue lists `advanced-electronics`, `rocket-control-unit`) |
| `fac research` behavior | `mod/factobot/agent.lua` (`research`), `docs/protocol.md` (`research`), `docs/decisions.md` decisions 40 and 63 | local repo |

Method: I loaded `technology.lua` in Lua 5.4 with a stub `data:extend`, dumped every technology to JSON, took the prerequisite closure of `rocket-silo` in Python, and topologically sorted it (Kahn's algorithm, ties broken by trigger first, then fewest pack types, then cheapest). The totals match the independent computation in `docs/human-baselines.md` §3c (44 techs, 17,695 pack-units, 62.34 lab-h).

**Version check.** The tech tree is identical between 2.0.72 and 2.1.24. The only diff in `technology.lua` is the format of the mine-entity trigger (`entity = "crude-oil"` became `entities = {"crude-oil"}`; changelog: "Changed MineEntityTechnologyTrigger::entity into MineEntityTechnologyTrigger::entities"). 2.0 runner sources therefore apply to 2.1 unchanged.

---

## 2. The required set (prerequisite closure of `rocket-silo`), in a valid order

Lab-s = units × seconds per unit, at one lab of speed 1. R/G/B/P/Y = automation / logistic / chemical / production / utility science pack. Every unit consumes one of each listed pack.

| # | Technology (internal name) | Units | Packs per unit | s/unit | Lab-s | Prerequisites | Unlocks |
|---|---|---|---|---|---|---|---|
| 1 | `electronics` | TRIGGER: craft 10 copper-plate | - | - | 0 | (none) | copper-cable, electronic-circuit, lab, inserter, small-electric-pole |
| 2 | `steam-power` | TRIGGER: craft 50 iron-plate | - | - | 0 | (none) | pipe, pipe-to-ground, offshore-pump, boiler, steam-engine |
| 3 | `automation-science-pack` | TRIGGER: craft 1 lab | - | - | 0 | steam-power, electronics | automation-science-pack |
| 4 | `automation` | 10 | R | 10 | 100 | automation-science-pack | assembling-machine-1, long-handed-inserter |
| 5 | `radar` | 20 | R | 10 | 200 | automation-science-pack | radar |
| 6 | `steel-processing` | 50 | R | 5 | 250 | automation-science-pack | steel-plate, steel-chest |
| 7 | `logistics` | 20 | R | 15 | 300 | automation-science-pack | underground-belt, splitter |
| 8 | `logistic-science-pack` | 75 | R | 5 | 375 | automation-science-pack | logistic-science-pack |
| 9 | `automation-2` | 40 | R+G | 15 | 600 | automation, steel-processing, logistic-science-pack | assembling-machine-2 |
| 10 | `engine` | 100 | R+G | 15 | 1,500 | steel-processing, logistic-science-pack | engine-unit |
| 11 | `fluid-handling` | 50 | R+G | 15 | 750 | automation-2, engine | storage-tank, pump, barrel |
| 12 | `advanced-material-processing` | 75 | R+G | 30 | 2,250 | steel-processing, logistic-science-pack | steel-furnace |
| 13 | `oil-gathering` | 100 | R+G | 30 | 3,000 | fluid-handling | pumpjack |
| 14 | `oil-processing` | TRIGGER: mine crude-oil (a pumpjack extracting) | - | - | 0 | oil-gathering | oil-refinery, chemical-plant, basic-oil-processing, solid-fuel-from-petroleum-gas |
| 15 | `flammables` | 50 | R+G | 30 | 1,500 | oil-processing | (prerequisite only) |
| 16 | `electric-energy-distribution-1` | 120 | R+G | 30 | 3,600 | steel-processing, logistic-science-pack | medium-electric-pole, big-electric-pole, iron-stick |
| 17 | `sulfur-processing` | 150 | R+G | 30 | 4,500 | oil-processing | sulfuric-acid, sulfur |
| 18 | `battery` | 150 | R+G | 30 | 4,500 | sulfur-processing | battery |
| 19 | `electric-energy-accumulators` | 150 | R+G | 30 | 4,500 | electric-energy-distribution-1, battery | accumulator |
| 20 | `logistics-2` | 200 | R+G | 30 | 6,000 | logistics, logistic-science-pack | fast-transport-belt, fast-underground-belt, fast-splitter |
| 21 | `railway` | 75 | R+G | 30 | 2,250 | logistics-2, engine | rail, locomotive, cargo-wagon, iron-stick |
| 22 | `plastics` | 200 | R+G | 30 | 6,000 | oil-processing | plastic-bar |
| 23 | `advanced-circuit` | 200 | R+G | 15 | 3,000 | plastics | advanced-circuit |
| 24 | `chemical-science-pack` | 75 | R+G | 10 | 750 | advanced-circuit, sulfur-processing | chemical-science-pack |
| 25 | `modules` | 100 | R+G | 30 | 3,000 | advanced-circuit | (prerequisite only) |
| 26 | `productivity-module` | 50 | R+G | 30 | 1,500 | modules | productivity-module |
| 27 | `speed-module` | 50 | R+G | 30 | 1,500 | modules | speed-module |
| 28 | `concrete` | 250 | R+G | 30 | 7,500 | advanced-material-processing, automation-2 | concrete, hazard-concrete, refined-concrete, refined-hazard-concrete, iron-stick |
| 29 | `solar-energy` | 250 | R+G | 30 | 7,500 | steel-processing, logistic-science-pack | solar-panel |
| 30 | `advanced-oil-processing` | 75 | R+G+B | 30 | 2,250 | chemical-science-pack | advanced-oil-processing, heavy-oil-cracking, light-oil-cracking, solid-fuel-from-heavy-oil, solid-fuel-from-light-oil |
| 31 | `lubricant` | 50 | R+G+B | 30 | 1,500 | advanced-oil-processing | lubricant |
| 32 | `electric-engine` | 50 | R+G+B | 30 | 1,500 | lubricant | electric-engine-unit |
| 33 | `robotics` | 75 | R+G+B | 30 | 2,250 | electric-engine, battery | flying-robot-frame |
| 34 | `advanced-material-processing-2` | 250 | R+G+B | 30 | 7,500 | advanced-material-processing, chemical-science-pack | electric-furnace |
| 35 | `production-science-pack` | 100 | R+G+B | 30 | 3,000 | productivity-module, advanced-material-processing-2, railway | production-science-pack |
| 36 | `processing-unit` | 300 | R+G+B | 30 | 9,000 | chemical-science-pack | processing-unit |
| 37 | `productivity-module-2` | 75 | R+G+B | 30 | 2,250 | productivity-module, processing-unit | productivity-module-2 |
| 38 | `speed-module-2` | 75 | R+G+B | 30 | 2,250 | speed-module, processing-unit | speed-module-2 |
| 39 | `low-density-structure` | 300 | R+G+B | 45 | 13,500 | advanced-material-processing, chemical-science-pack | low-density-structure |
| 40 | `utility-science-pack` | 100 | R+G+B | 30 | 3,000 | robotics, processing-unit, low-density-structure | utility-science-pack |
| 41 | `rocket-fuel` | 300 | R+G+B | 45 | 13,500 | flammables, advanced-oil-processing | rocket-fuel |
| 42 | `productivity-module-3` | 300 | R+G+B+P | 60 | 18,000 | productivity-module-2, production-science-pack | productivity-module-3 |
| 43 | `speed-module-3` | 300 | R+G+B+P | 60 | 18,000 | speed-module-2, production-science-pack | speed-module-3 |
| 44 | `rocket-silo` | 1000 | R+G+B+P+Y | 60 | 60,000 | concrete, rocket-fuel, electric-energy-accumulators, solar-energy, utility-science-pack, speed-module-3, productivity-module-3, radar | rocket-silo, rocket-part, cargo-landing-pad, satellite |

### Totals by pack tier (required set only)

| Tier (techs that cost) | Techs | Lab-s | Share of lab-s |
|---|---|---|---|
| R only | 5 | 1,225 | 0.5% |
| R+G | 20 | 65,700 | 29.3% |
| R+G+B | 12 | 61,500 | 27.4% |
| R+G+B+P | 2 | 36,000 | 16.0% |
| R+G+B+P+Y (`rocket-silo`) | 1 | 60,000 | 26.7% |
| **Total** | **40 lab techs + 4 triggers** | **224,425** | 100% |

Packs consumed by required research: **R 5,960, G 5,785, B 3,350, P 1,600, Y 1,000 (17,695 total)**.

### Things in this list that surprise people coming from 1.1

- `radar`, `solar-energy`, `electric-energy-distribution-1` and `electric-energy-accumulators` are prerequisites of `rocket-silo` in 2.x. In 1.1 they were not; 1.1 needed `rocket-control-unit` instead, a tech and intermediate that no longer exist (1.1.110 closure diff: only-1.1 = `advanced-electronics`, `advanced-electronics-2`, `rocket-control-unit`). You research these techs but never have to build panels, accumulators or radars.
- `logistics-2` is mandatory in 2.x because `railway` needs it, and the production science pack needs rails (`production-science-pack` recipe: 1 electric furnace + 1 productivity module + 30 rail → 3 packs, 21 s).
- `electric-mining-drill` is **not** in the closure. In 2.x electric drills sit behind a 25 × R × 10 s tech ([FFF #376](https://factorio.com/blog/post/fff-376): "electric mining drill, radar or repairs packs ... into their own new 'red science' technologies"). In practice it is mandatory (see §4).
- The silo recipe is unchanged from 1.1: 1000 steel, 1000 concrete, 100 pipe, 200 processing units, 200 electric engines, 30 s. 100 rocket parts per rocket (`rocket_parts_required = 100`); a part is 10 processing units + 10 LDS + 10 rocket fuel, 3 s, crafted in the silo (crafting speed 1, 4 module slots).

---

## 3. Trigger technologies

All base-game triggers at the pinned commit (`research_trigger` in `technology.lua`):

| Tech | Trigger | On the rocket path? | Agent note |
|---|---|---|---|
| `electronics` | craft 10 copper plates | yes | Smelt copper before anything else; the lab, inserter, small pole and green circuit recipes all come from here. |
| `steam-power` | craft 50 iron plates | yes | Comes naturally from the first iron smelting. |
| `automation-science-pack` | craft 1 lab | yes | Hand-craft the lab (2 s; 10 green circuits, 10 gears, 4 belts) as soon as `electronics` fires. |
| `steel-axe` | craft 50 steel plates | no (optional) | Free: fires on the first 50 steel. Effect `character-mining-speed +1` (+100%). |
| `oil-processing` | mine crude-oil (any amount) | yes | Needs `oil-gathering` researched, then a pumpjack placed on an oil well and powered. Until then the whole blue path is locked. |
| `uranium-processing` | mine uranium ore | no | Ignore. |
| `space-science-pack` | send a satellite to orbit | no | Post-victory. |

**Machine output counts for craft triggers.** Iron plates can only come out of a furnace, so the `steam-power` trigger (50 iron plates) proves furnace output counts. The same goes for steel and the axe [INFERENCE from the data].

**`fac` handles triggers explicitly.** `fac research <trigger-tech>` is rejected with "... is not researched in labs; it unlocks when you ...". A tech that needs an unfinished trigger tech queues nothing and is rejected with "X needs Y, which is not researched in labs; it unlocks when you ...", because a trigger tech can never be queued (`research` in `agent.lua`, decision 63). Consequence: plastics, sulfur, battery, flammables and everything after them can only be queued once a pumpjack has actually pumped oil.

**Pumpjack detail.** The pumpjack is a mining drill (mining speed 1, 90 kW). Mining productivity applies to it ([wiki](https://wiki.factorio.com/Mining_productivity_(research))). Whether the trigger fires before the pumpjack's output pipe is connected is UNVERIFIED. The pumpjack should mine until its internal fluid box is full, which should be enough to fire it [INFERENCE]. To be safe, connect a pipe or storage tank.

---

## 4. Optional technologies: verdicts

Costs are from the pinned `technology.lua`. "Runner use" lists who researches it: Z = Zaspar 2.x guide, N = 1.1 beginner guide (Nefrums seed), M = Mazmot 1.1 cheatsheet.

| Tech | Cost (units × packs × s) | Lab-s | Effect (2.1.24 data) | Runner use | Verdict | Why, and how it applies to this agent |
|---|---|---|---|---|---|---|
| `electric-mining-drill` | 25 × R × 10 | 250 | unlocks electric drill: mining speed 0.5, no fuel (burner drill: 0.25, 150 kW of fuel) | Z (2nd tech) | **Yes, mandatory in practice** | Doubles ore per drill and removes all fuel inserts for drills. Every burner drill needs repeated `insert coal` calls; electric drills need none. |
| `steel-axe` (trigger) | craft 50 steel | 0 | +100% character mining speed: ore 2 s → 1 s, trees 1.1 s → 0.55 s (ore `mining_time` 1, tree 0.55, character `mining_speed` 0.5) | Z (optional: "place 5 furnaces and half stack them with iron to unlock steel axe"), N, M | **Yes, free** | Halves the game time of every `mine` call (rocks, trees for wood, early ore, picking up your own buildings). Do not build extra furnaces for it: the first 50 steel for assembler 2s and steel furnaces fire it. In 1.1 it was a 50 × R × 30 s lab tech; 2.x replaced that with the trigger ([FFF #376](https://factorio.com/blog/post/fff-376): "Steel axe technology now requires you to craft actual steel plates"). |
| `fast-inserter` | 30 × R × 15 | 450 | fast inserter: 2.50 items/s chest-to-chest vs 0.86 for the basic inserter (wiki, measured 2.0.26) | Z, N, M (all early) | **Yes, cheap, low priority** | Needed only where one inserter must move more than 0.86/s: direct-insertion gear → red science, wire → green circuit with assembler 2s, steel furnace input at speed 2. One extra call; queue it whenever a slot is free, outside the §8 batches. |
| `toolbelt` | 100 × R+G × 30 | 3,000 | +10 inventory slots (80 → 90) | Z (Mall 4), N (optional order, first) | **Yes** | Inventory limits are enforced. Each extra stack carried saves walk-and-`take` round trips when building far from the mall. 200 packs total; queue it in the green stage before the long oil and outpost builds. |
| `research-speed-1` | 100 × R+G × 30 | 3,000 | lab speed +20% | Z, N, M | **Yes, high** | See §6. Does the work of 20% more labs. |
| `research-speed-2` | 200 × R+G × 30 | 6,000 | lab speed +30% (cumulative +50%) | Z, N, M | **Yes, high** | Payback: about 220,000 lab-s of required research follows it, so S = 1.5 saves about 73,000 lab-s of lab occupancy for a 9,000 lab-s cost when labs are the bottleneck [INFERENCE]. When packs are the bottleneck it lets 2/3 as many labs keep up, which saves `place` calls. |
| `research-speed-3` | 250 × R+G+B × 30 | 7,500 | +40% (S 1.5 → 1.9) | N (optional, last); not in Z | **No (unless blue packs pile up in front of labs)** | Costs 250 blue packs (7.5% of all required blue) to cut labs by 21%. Zaspar's 2.x route stops at lab speed 2. |
| `research-speed-4+` | 500 × R+G+B × 30 and up | 15,000+ | +50% each | none | **No** | Blue and purple packs are the scarcest resource late. |
| `mining-productivity-1` | 250 × R+G × 60 | 15,000 | +10% output of all mining drills **and pumpjacks**; bonus ore does not deplete the patch ([wiki](https://wiki.factorio.com/Mining_productivity_(research))) | Z (late, after bots) | **Yes, as an R+G filler** | Same as placing 10% more drills and pumpjacks without the `place` calls. Rough payback: 500 packs ≈ 2,500 ore-equivalents [INFERENCE: red ≈ 1 copper + 2 iron; green ≈ 5.5 iron + 1.5 copper]. At 15 ore/s of drilling, +1.5 ore/s repays that in about 28 min [INFERENCE]. Queue it while blue is being built, when the labs have nothing else R+G to do. Needs 15,000 lab-s, so not before research speed. |
| `mining-productivity-2` | 500 × R+G+B × 60 | 30,000 | +10% | none | **No** | 500 blue packs; too late to pay back. |
| `logistics-2` | 200 × R+G × 30 | 6,000 | fast belts (30/s) | Z, N, M | **Required anyway** (railway prerequisite) | Research it as filler before the oil trigger. Building fast belts is rarely needed: an agent-scale factory seldom pushes more than 15 items/s down one belt [INFERENCE]. |
| `advanced-material-processing` | 75 × R+G × 30 | 2,250 | steel furnace: speed 2, 90 kW, recipe 6 steel + 10 brick | Z, N, M | **Required; research early** | Half the furnaces per plate/s of stone furnaces. Fewer `place` calls and half the fuel per plate. |
| `automation-2` | 40 × R+G × 15 | 600 | assembler 2: speed 0.75, can craft fluid recipes | Z, N, M | **Required; first R+G tech** | 1.5× per machine; needed for fluid recipes (electric engines need lubricant). |
| `electric-energy-distribution-1` | 120 × R+G × 30 | 3,600 | medium pole (wire 9, supply 7×7), big pole (wire 32, supply 4×4) | Z (late, before silo); N, M: not a silo prerequisite in 1.1 | **Required; research early for the agent** | Runners leave it late because bots and blueprints place their poles. The agent places every pole by hand: the oil and outpost lines are 2-4× fewer `place` calls with big poles [INFERENCE: 32/7.5 wire-reach ratio]. Recipe: medium = 2 steel + 4 sticks + 2 cable; big = 5 steel + 8 sticks + 4 cable. |
| `automobilism` (car) | 100 × R+G × 30 | 3,000 | car | Z (drives to oil) | **No** | `fac` has no drive command; `walk` handles 500-tile trips. |
| `construction-robotics` | 100 × R+G+B × 30 | 3,000 | roboport, construction robot | Z, N, M | **No** | Construction robots only build ghosts, repair, and act on deconstruction orders. The agent has no ghosts, no blueprints and no deconstruction planner. Runners use it for their whole second half (Mazmot's "2nd factory (build by bots)", Zaspar's "Print a new power plant for bots to build"). That speed source is not available here. |
| `logistic-robotics` | 250 × R+G+B × 30 | 7,500 | logistic robot, roboport, passive provider + storage chest, personal logistic requests | none of the three before yellow | **No (re-evaluate only if `fac` gains a logistic-request command)** | Its value would be personal requests (robots bring items to the character), but `fac` cannot set requests. Requester chests need `logistic-system`, which costs yellow packs. |
| `worker-robots-speed-1/2` | 50 and 100 × R+G+B × 30 | 1,500 / 3,000 | robot speed | Z, N, M | **No** | Only matters with bots. |
| `effect-transmission` (beacons) | 75 × R+G+B+P × 30 | 2,250 | beacon (2 module slots, effectivity 1.5, diminishing profile 1/√n) | Z (20 beacons around the silo), N, M | **No** | See §7. 20 beacons cost about 40 `place`/`insert` calls (≈10 min of wall time at 15 s/call) to speed up a silo that is usually limited by its ingredients, not its crafting speed [INFERENCE]. |
| `productivity-module-3` / `speed-module-3` | required | | | | required techs | Whether to *build* prod 3s for the silo is a production decision. Both runners put 4 prod 3s in the silo (+40% parts per craft) (§7). |
| `circuit-network` | 100 × R+G × 15 | 1,500 | combinators, speaker | Z (alarm for purple inputs) | **No** | No value without wiring by hand. |
| `landfill` | 50 × R+G × 30 | 1,500 | landfill | none | **Only if water blocks a required build** | Map-dependent. |
| `automation-3`, `logistics-3`, `bulk-inserter`, `efficiency-module*`, `coal-liquefaction`, nuclear | various | | | none | **No** | They cost purple packs or do nothing for the rocket. (`advanced-material-processing-2` is a required tech, but electric furnaces need to be built only as purple-pack ingredients.) |
| All military (`military-*`, `gun-turret`, `stone-wall`, `heavy-armor`, `land-mine`, `military-science-pack`, `cliff-explosives` needs `military-2`) | | | | Z, N, M (they play with biters) | **No** | Peaceful, no enemy bases. Strip these from any runner queue you copy. Cliff explosives need `military-2`; route around cliffs instead. |

---

## 5. How research works through `fac`, and what that means for queuing

From `research` in `mod/factobot/agent.lua`, `docs/protocol.md` (`research`) and decisions 40 and 63 in `docs/decisions.md`:

- `fac research` with no tech returns the current research, the queue, and what is available.
- `fac research <tech>` queues the tech and, before it, every prerequisite that is neither researched nor queued, in dependency order, as clicking a locked tech on the tech screen does. It is rejected if the tech is already researched or queued or is a trigger tech. If a missing prerequisite is an unfinished trigger tech, or the tech and its missing prerequisites don't all fit in the queue, nothing is queued. Issuing a batch in the order of §8 queues one tech per call.
- Cancelling a queued tech also drops every queued tech behind it that depends on it ("the engine drops with it the technologies queued behind it (probed)").
- The research queue is always on in 2.x: "So now it is always on and you cannot turn it off" ([FFF #376](https://factorio.com/blog/post/fff-376)). It had already become default-on for new games in 1.1.92 (changelog: "The research queue is enabled by default for new games.").
- **Queue length: 7.** A 2.x-era mod-portal post says "The vanilla research queue is limited to only 7 technologies" ([Parallel Research discussion](https://mods.factorio.com/mod/simultaneous-research/discussion/6a724a2d97a494eac1164685)). Confirmed in a factobot test world on 2026-11-02 (2.1.24, seed 1): the engine refused an eighth tech. `fac research` now checks the cap first and rejects with "queueing X takes N slots (...) but the research queue holds at most 7 technologies and has K free; nothing was queued". The plan below is therefore cut into batches of at most 7. Re-check the queue at natural checkpoints (after a big build) and top it up.
- Lab speed formula ([wiki Research](https://wiki.factorio.com/Research)): a tech takes `T0 × P / (L × S)` seconds, with T0 = seconds per unit, P = units, L = labs, and `S = (1 + Br) × (1 + Mr)`. Br is the research-speed bonus; Mr is the sum of module effects in the lab (speed positive, productivity negative). Productivity modules also add bonus units.

Each research call is one action (5-30 s of wall time, during which the game runs). The full plan is 45 calls (40 required lab techs + 5 optional), plus `fast-inserter`. That is roughly 4-23 minutes of agent time, so do not issue research calls one at a time between other actions. Batch them: each batch below is 4-7 calls issued together at one checkpoint [INFERENCE].

---

## 6. Lab count guidance

### The rule

Labs needed so research keeps pace with pack supply:

`L = R × T / S`

- R = units per second you can supply = the production rate of the scarcest pack the current tech needs (each unit eats one of every listed pack).
- T = seconds per unit of the current tech: red techs 5-15 s, R+G techs 15-30 s (60 s for mining productivity), blue techs 30-45 s (LDS and rocket fuel are 45 s), purple and silo techs 60 s.
- S = lab speed: 1.0 base, 1.2 after research-speed-1, 1.5 after research-speed-2.

Labs beyond `L` sit idle waiting for packs. Labs below `L` let packs pile up, which is cheap to fix later. So build toward the *largest* T you will research in the stage.

| Supply R (units/s) | Red stage (T=15, S=1) | Green, before lab speed (T=30, S=1) | Green after RS2 (T=30, S=1.5) | Blue (T=45, S=1.5) | Purple/yellow/silo (T=60, S=1.5) |
|---|---|---|---|---|---|
| 0.25 | 4 | 8 | 5 | 8 | 10 |
| 0.5 | 8 | 15 | 10 | 15 | 20 |
| 1.0 | 15 | 30 | 20 | 30 | 40 |
| 1.5 | 23 | 45 | 30 | 45 | 60 |

Reference for scale [INFERENCE: machine counts from Zaspar's guide × 2.1.24 recipe times, assuming assembler 1 for red/green as built]: Zaspar's "Mall 4 + Labs" step has 10 red assemblers (10 × 0.5 / 5 s = 1.0 R/s) and 12 green (12 × 0.5 / 6 s = 1.0 G/s) feeding **32 labs**, close to `L = 1.0 × 30 / 1 = 30`. His blue (14 assembler 2s: 14 × 0.75 × 2 / 24 s = 0.875 B/s) runs on the same 32 labs at S = 1.5. For purple (14 assembler 2s: 1.5 P/s) and yellow (12 assembler 2s: 1.29 Y/s) he doubles to **64 labs**; the formula gives 1.29 × 60 / 1.5 = 52. The 1.1 beginner guide used "30 labs" for red/green and "double the amount of labs" at yellow.

### Stage-by-stage recommendation for the agent

Lab-s and pack counts are per batch of the queue in §8 (computed from the pinned data). "Minutes at L labs" = lab-s / (L × S) / 60: the time research takes *if packs are not the limit*. S = 1 through Q2, S = 1.5 from Q3 on (research-speed-2 follows the 200 lab-s `radar` at the head of Q3).

| Batch (stage) | Lab-s | Packs consumed | S | Min. at 10 labs | Min. at 20 labs | Min. at 40 labs | Recommended labs |
|---|---|---|---|---|---|---|---|
| Q1 (red) | 1,275 | R 180 | 1 | 2.1 | 1.1 | 0.5 | **2-4, hand-fed first, then fed by one inserter chain**. Red pack crafting is the limit (5 s per pack by hand; 10 s in an assembler 1), not labs. |
| Q2 (green, blue critical path) | 14,700 | R/G 585 each | 1 | 24.5 | 12.2 | 6.1 | **10-20.** Use `L = 30 × R_green`. Stop adding labs once RS2 lands: S = 1.5 cuts L by a third. |
| Q3 (green fillers, waiting on pumpjack) | 32,450 | R 1,095, G 1,075 | 1.5 | 36.1 | 18.0 | 9.0 | same labs |
| Q4 (oil trigger → blue gate) | 23,250 | R/G 925 each | 1.5 | 25.8 | 12.9 | 6.5 | same labs |
| Q5 (green fillers while blue is built) | 22,500 | R/G 500 each | 1.5 | 25.0 | 12.5 | 6.2 | same labs |
| Q6 (blue, purple path) | 27,750 | R/G/B 925 each | 1.5 | 30.8 | 15.4 | 7.7 | **15-30** (`L = 45 × R_blue / 1.5 = 30 × R_blue`) |
| Q7 (blue, yellow path) | 33,750 | R/G/B 825 each | 1.5 | 37.5 | 18.8 | 9.4 | same |
| Q8 (purple: PM3 + SM3) | 36,000 | R/G/B/P 600 each | 1.5 | 40.0 | 20.0 | 10.0 | **20-40** (`L = 40 × R_purple`) |
| Q9 (yellow: rocket-silo) | 60,000 | 1,000 of each of 5 packs | 1.5 | 66.7 | 33.3 | 16.7 | **20-40** (`L = 40 × R_yellow`). Pack-limited floor: 1000 / R_yellow seconds (33 min at 0.5 Y/s). |

Practical rules [INFERENCE]:
- **Feed labs as a chain**: "Inserters can take science packs from labs and hand them to other labs, making a lab chain a feasible solution" ([wiki Research](https://wiki.factorio.com/Research)). One belt or chest at the head of the row feeds the whole row. A lab costs about 2 `place` calls (lab + inserter) plus a pole every 2-3 labs. Twenty extra labs cost about 50 calls, roughly 12 minutes of wall time at 15 s per call. Lab speed research is far cheaper per unit of throughput.
- **Power**: 60 kW per lab. 40 labs = 2.4 MW = about 2.7 steam engines (900 kW each).
- **Pack floors dominate.** The bare closure of `chemical-science-pack` needs 1,050 red and 915 green packs (`docs/human-baselines.md` §3c). The recommended order puts about 2,300 green packs through the labs before `chemical-science-pack` completes (Q2 + Q3 + the first four techs of Q4). At 0.5 G/s that is 76 minutes of pack production, at 1 G/s 38 minutes. Raising pack supply beats adding labs, and if green supply is low, cut Q3 back (see §8).
- **Productivity modules in labs** (prod 1: +4% productivity, −5% speed each, 2 slots): two per lab give units/s × 0.97 and save 7.4% of packs. Each lab needs an `insert` call. Only worth it if the agent is standing at the labs anyway and packs are the bottleneck; runners do it (Z: "Prod 1s in ... labs") because their bots do the inserting.

---

## 7. Late-game research-adjacent build decisions

These are production choices; I include them only because they decide which research is worth having.

- **Prod 3s in the silo**: 4 × prod 3 = +40% productivity, −60% speed. 100 parts need 72 crafts instead of 100, which saves 28 × (10 PU + 10 LDS + 10 rocket fuel) = 280 of each. Silo time goes from 100 × 3 s = 300 s to 72 × 3 / 0.4 = 540 s. A prod 3 is 4 prod 2 + 5 AC + 5 PU (60 s); a prod 2 is 4 prod 1 + 5 AC + 5 PU (30 s); a prod 1 is 5 AC + 5 GC (15 s). So 4 prod 3s = 64 prod 1s, as Zaspar notes ("Feed 80 blue and red circuits and 64 prod1s to make 16 prod 2s. Make the 4 prod3s for the silo from those"). Both runners do it. The techs are mandatory anyway, so the only cost is crafting [INFERENCE: worth it when built by assemblers; 1,680 s if all module tiers are hand-crafted].
- **Beacons around the silo** (`effect-transmission`, optional): with 8 beacons of 2 speed 3 each, the silo gains 8 × 1.5 × 2 × 0.5 × 0.3535 ≈ +4.2 speed, so the 72 crafts take about 46 s instead of 540 s [INFERENCE from beacon `distribution_effectivity = 1.5`, `profile[8] = 0.3535`, speed 3 = +0.5]. That only saves time if all 720 PU, 720 LDS and 720 rocket fuel are stockpiled before the silo exists. The agent will usually feed the silo as ingredients arrive, so beacons do not pay [INFERENCE].
- **Radar**: required as a tech only. A built radar (300 kW, 10 MJ per sector, so one chunk scanned every 33 s, out to 14 chunks or about 448 tiles) charts new map area that `fac map` can then show. It is useful if the start area has no oil in sight [INFERENCE from the radar prototype].

---

## 8. Recommended research queue for the agent

Batches hold at most 7 techs (queue cap, see §5), but a batch can be issued while the one before it still has techs queued, so issue as many as fit (7 including the running one) and the rest as the queue drains. "When" names an observable game state. Order within each batch is the issue order, and it is a valid topological order given all earlier batches. Optional techs are marked (opt).

| Batch | When to issue | Techs, in order | Calls | Lab-s | Packs |
|---|---|---|---|---|---|
| Q0 | No calls. Do these in the first minutes. | Smelt 10 copper plates → `electronics`. Smelt 50 iron plates → `steam-power`. Hand-craft 1 lab → `automation-science-pack`. | 0 | 0 | 0 |
| Q1 | First lab placed and powered, 10 red packs hand-crafted | `automation`, `electric-mining-drill` (opt, practically required), `logistic-science-pack`, `steel-processing`, `logistics` | 5 | 1,275 | R 180 |
| Q2 | Red packs come from assemblers and the first green packs are 2-3 minutes away | `automation-2`, `research-speed-1` (opt), `engine`, `fluid-handling`, `oil-gathering`, `advanced-material-processing`, `electric-energy-distribution-1` | 7 | 14,700 | R/G 585 |
| Q3 | Q2 is down to 1-2 techs; issue as many as fit (7 including the running one), the rest as it drains. Meanwhile walk to oil and place a powered pumpjack. | `radar`, `research-speed-2` (opt), `toolbelt` (opt), `logistics-2`, `railway`, `concrete`, `solar-energy` | 7 | 32,450 | R 1,095, G 1,075 |
| Q4 | Immediately after `oil-processing` fires (pumpjack has pumped); issue as many as fit (7 including the running one), the rest as it drains | `plastics`, `advanced-circuit`, `sulfur-processing`, `chemical-science-pack`, `battery`, `modules`, `productivity-module` | 7 | 23,250 | R/G 925 |
| Q5 | Q4 down to 1-2 techs, while building refinery → red circuits → blue science | `speed-module`, `flammables`, `electric-energy-accumulators`, `mining-productivity-1` (opt) | 4 | 22,500 | R/G 500 |
| Q6 | First blue packs reach the labs; issue as many as fit (7 including the running one), the rest as it drains | `advanced-material-processing-2`, `production-science-pack`, `processing-unit`, `productivity-module-2`, `speed-module-2`, `advanced-oil-processing`, `lubricant` | 7 | 27,750 | R/G/B 925 |
| Q7 | Q6 down to 1-2 techs; build purple science now. Issue as many as fit (7 including the running one), the rest as it drains | `electric-engine`, `robotics`, `low-density-structure`, `utility-science-pack`, `rocket-fuel` | 5 | 33,750 | R/G/B 825 |
| Q8 | First purple packs reach the labs (yellow still being built) | `productivity-module-3`, `speed-module-3` | 2 | 36,000 | R/G/B/P 600 |
| Q9 | Yellow packs reach the labs. Can be issued early: it is accepted once its prerequisites are queued. | `rocket-silo` | 1 | 60,000 | 1,000 of each |
| **Total** | | 40 required + 5 optional | **45** | **251,675** | R 6,635, G 6,435, B 3,350, P 1,600, Y 1,000 |

Why this order [INFERENCE unless cited]:
- **Q1**: `automation` first (10 units, 100 lab-s) because assemblers end hand-crafting of red packs. `logistic-science-pack` comes right after `electric-mining-drill`: the queue is first-in first-out, its recipe gates every green assembler, and in test runs with `logistics` and `steel-processing` ahead of it the labs sat on a starved red supply while green packs waited (`skills/factorio-speedrun/references/research.md`). `steel-processing` still comes early so steel production, and with it the free steel axe, starts soon. `radar` is needed only by `rocket-silo`, so it waits for Q3. `fast-inserter` (opt) goes in whenever a slot is free and one inserter has to move more than 0.86 items/s. Zaspar's first block is the same minus military: "Automation, Electric miners, Gun turret, Logistics, Fast inserter, Steel processing, Green science".
- **Q2**: the blue critical path is `automation-2 → engine → fluid-handling → oil-gathering` (5,850 lab-s), then the trigger, then `plastics → advanced-circuit`, `sulfur-processing`, `chemical-science-pack` (14,250 lab-s). `research-speed-1` goes second because its benefit scales with all the research still to come. `electric-energy-distribution-1` closes the batch so big poles exist before the agent runs a power line to the oil field.
- **Q3**: these are required techs with no oil dependency, the right work for the labs while the pumpjack is pending. `radar` (red only, 200 lab-s) leads, then the agent's own benefits (RS2, toolbelt). **The queue is first-in first-out**, so Q4 waits behind whatever is left of Q3. If `oil-processing` fires while the tail of Q3 (railway, concrete, solar-energy) is still queued and green supply is short, cancel those three (none has a queued dependent), queue Q4, and put them back in Q5. Partial progress is kept: "if another research is in progress, that progress will be saved" ([wiki Research](https://wiki.factorio.com/Research)). Each cancel and re-add is a call, so only do this when more than about 10 minutes of Q3 remain [INFERENCE].
- **Q4**: the blue gate, then `battery` (needed for robotics and accumulators) and `productivity-module` (needed for purple packs).
- **Q5**: R+G leftovers. `mining-productivity-1` comes last because it is the only optional tech here and takes 15,000 lab-s. Skip it if blue is almost ready and the labs would still be busy with it.
- **Q6 before Q7**: the purple pack recipe needs `advanced-material-processing-2` (electric furnace), `productivity-module` and `railway`. Getting purple first lets Q8 (36,000 lab-s) run during the yellow build. `processing-unit` is in Q6 because PM2/SM2 and yellow all need it. `advanced-oil-processing` and `lubricant` start the yellow path (electric engines need lubricant; flying robot frames need electric engines).
- **Q7**: `rocket-fuel` is last because it is needed only for rocket parts. Its 13,500 lab-s can overlap with the start of purple.
- **Q9 timing**: `rocket-silo` is 60,000 lab-s, 27% of all research, and cannot start before yellow flows. At 0.5 Y/s it takes at least 2,000 s of yellow production. Size the final lab block for it (§6) and build the silo and part supply while it runs.

Compared with the runners: Zaspar (2.x) researches lab speed 1 and 2 in "Mall part 5", right after the steel build. He takes mining productivity 1 after bots, logistics 2 at the 32-lab step, and EED1, accumulators and solar only right before the silo, because bots place his poles. The 1.1 beginner guide calls toolbelt, lab speed 1, 2 and 3, flammables and concrete "Optional Order", meaning they can be delayed. Flammables and concrete are mandatory, though; that guide just pushes them late. Mazmot's 1.1 queue puts research speed ×2 right after automation 2, as here.

---

## 9. 1.1 vs 2.x checks

| Item | 1.1.110 | 2.1.24 | Effect on old guides |
|---|---|---|---|
| Steel axe | 50 × R × 30 s research | trigger: craft 50 steel | 1.1 queues that list "Steel Axe" as a lab tech are wrong for 2.x; it is free. |
| Electric mining drill | available from start | 25 × R × 10 s tech | 1.1 openings must add it. |
| Early recipes (pipes, boiler, lab, inserter, red pack) | available from start | triggers `steam-power`, `electronics`, `automation-science-pack` | Smelt 10 copper and 50 iron, craft a lab. |
| Oil processing | lab tech | trigger: mine crude oil, after `oil-gathering` (100 × R+G × 30) | Blue path now needs a pumpjack running before plastics can be queued. |
| Advanced electronics 1/2 | techs | renamed `advanced-circuit` / `processing-unit` | Name mapping only. |
| Rocket control unit | tech + intermediate | removed; silo now needs radar, solar, EED1, accumulators | Mandatory set changed; total cost almost equal (17,865 vs 17,695 pack-units, per `docs/human-baselines.md`). |
| Rocket part | 10 RCU + 10 LDS + 10 rocket fuel | 10 PU + 10 LDS + 10 rocket fuel | |
| Toolbelt, research speed 1/2, mining prod 1, logistics 2, AMP, fast inserter | same cost and effect in both | | 1.1 advice on these carries over. |
| Research queue | map setting (default on since 1.1.92) | always on | |
| 2.0.72 vs 2.1.24 | | identical tree | 2.0 sources are valid for 2.1. |

---

## 10. Open questions and fetch log

- UNVERIFIED: whether `oil-processing` fires from a pumpjack with no output pipe.
- UNVERIFIED: the speedrun.com "Research Queue Any% / DS" resource (https://www.speedrun.com/factorio/resources/br40b) returned HTTP 403 to the reader and to curl, so I could not read the runners' published queue file. Zaspar's guide has "Full research queue: todo".
- Zaspar's slide text lists research per stage but no counts per tech. The numbers next to the tech names in the export are item counts from the slides, not research data.
- Reddit was not used.
