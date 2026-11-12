# Layout and logistics for a fac agent (Factorio 2.1.24, base game)

Research date: 2026-11-02. Audience: an agent that builds one entity per `place` call, with no blueprints, ghosts or drag-building, while the game keeps running.

## Sources and conventions

- **FD** = wube/factorio-data at commit `acf5a342afcb66c066b9d88d202e8622112da117` (2026-10-27), `base/info.json` version **2.1.24**. Files used:
  - [FD entities.lua](https://github.com/wube/factorio-data/blob/acf5a342afcb66c066b9d88d202e8622112da117/base/prototypes/entity/entities.lua)
  - [FD mining-drill.lua](https://github.com/wube/factorio-data/blob/acf5a342afcb66c066b9d88d202e8622112da117/base/prototypes/entity/mining-drill.lua)
  - [FD transport-belts.lua](https://github.com/wube/factorio-data/blob/acf5a342afcb66c066b9d88d202e8622112da117/base/prototypes/entity/transport-belts.lua)
  - [FD recipe.lua](https://github.com/wube/factorio-data/blob/acf5a342afcb66c066b9d88d202e8622112da117/base/prototypes/recipe.lua)
  - [FD fluid.lua](https://github.com/wube/factorio-data/blob/acf5a342afcb66c066b9d88d202e8622112da117/base/prototypes/fluid.lua)
- **Wiki** = wiki.factorio.com, pages fetched 2026-11-02. The pages used below carry 2.0.x or 2.1.x history entries. Where a wiki number disagreed with FD, FD wins and the disagreement is noted.
- **FA** = the FactorioAccess wiki, written for blind players who also build one entity at a time ([Transport Belt Basics](https://github.com/Factorio-Access/FactorioAccess/wiki/Transport-Belt-Basics), [Ratios Cheat Sheet](https://github.com/Factorio-Access/FactorioAccess/wiki/Ratios-Cheat-Sheet), [Factory Building Guidance](https://github.com/Factorio-Access/FactorioAccess/wiki/Factory-Building-Guidance), [Inserters](https://github.com/Factorio-Access/FactorioAccess/wiki/Inserters), [Oil Logistics](https://github.com/Factorio-Access/FactorioAccess/wiki/Oil-Logistics-and-Basic-Processing)). It states it covers version 2.0.
- **Zaspar** = [Zaspar's 2.x speedrun guide](https://docs.google.com/presentation/d/12dO2YmmOUK_R528-jCKo2nSdJUKNkp-vvXWqDHS3PKo/export/txt). Zaspar holds the 2.x Default Settings record, 1:59:01 (see `docs/human-baselines.md`).
- **factobot** = this repo: `docs/protocol.md` and `mod/factobot/agent.lua`.
- Tags: `[INFERENCE]` marks my own derivation, `UNVERIFIED` a claim I could not confirm, and `UNVERIFIED-2.x` a 1.1-era claim not confirmed for 2.x.

**Coordinates.** Positions are entity centers, as `fac place` takes them, with x pointing east and y pointing south. `place` snaps the center to the grid the way the cursor does (`agent.lua` `place`). Entities with odd sizes (1x1, 3x3, 5x5) center on `.5`. Entities with even sizes (2x2 furnaces and burner drills) center on integers. The boiler (3x2) facing north centers on `(x.5, y.0)`.

**Directions in fac (checked against factobot tests):**

| Entity | What `--direction D` means |
|---|---|
| Transport belt | Items flow toward D. |
| Inserter (all kinds) | It **picks up from the D side and drops on the opposite side**. A north-facing inserter takes from the tile to its north and drops south (`test_an_inserter_picks_up_from_the_side_it_faces`). |
| Burner or electric mining drill | The output chute faces D. A burner drill facing east drops into a furnace east of it (`test_a_drill_feeds_the_furnace_it_faces`). |
| Offshore pump | D points at the water. A pump at (4.5,-3.5) with water to the east has direction east (`test_research_needs_a_powered_lab`). |
| Boiler | Steam leaves on the D side. Water connects on the two short ends. |
| Steam engine, storage tank | Only two orientations: north equals south, east equals west (`two_direction_only = true`, FD). |
| Refinery, chemical plant, pumpjack, assembler 2/3 with a fluid recipe | Fluid ports rotate with D (tables below). |
| Furnace, chest, lab, pole, pipe, assembler 1 | Direction has no effect. |

`fac rotate` turns an entity a quarter turn clockwise using `LuaEntity.rotate` and is rejected when the entity can't turn (`agent.lua` `rotate`).

---

## 1. Top takeaways, ranked by estimated time saved `[INFERENCE: ranking]`

1. **Build each cell from one standing spot.** Build reach and interact reach are both 10 tiles (`build_distance = 10`, `reach_distance = 10`, FD character). Every layout in section 9 fits inside a 20x20 square around one standing point. One `walk` followed by 10 to 30 `place` calls costs far fewer agent turns than walking between placements. Running speed is 0.15 tiles/tick (9 tiles/s, FD), so 100 tiles of walking cost about 11 s of game time.
2. **Prefer direct insertion inside a cell.** Each machine-to-machine hop is one inserter. A belt between cells costs one `place --to` call per straight run (decision 52), plus its walking time and inserters at both ends. A wooden chest holds 16 stacks, which is 1,600 plates or 800 ore or coal (FD `inventory_size = 16`; plate stack 100, ore stack 50). One `insert` call fills it, but a chest buffer costs a `take` and an `insert` on every visit, where a belt keeps carrying. Speedrunners use direct insertion for purple science and their "mixed" circuit/LDS build (Zaspar).
3. **Point drills straight into furnaces.** Burner and electric drills drop into the entity on their output tile, so no ore belt or ore inserter is needed. This is the speedrun burner phase: 14 iron, 6 copper, 4 stone and 20 coal burner drills, "with the furnaces on the outside (so inserters can grab from them)" (Zaspar).
4. **Get steam power right the first time and check it with `inspect pipes_to`.** One boiler feeds 2 engines (1.8 MW). One offshore pump feeds 200 boilers. `fac` rejects a misplaced pump and names the nearest spot that fits. Layout F gives tested coordinates.
5. **Run an `inspect` sweep straight after building.** Look at `status`, `drops_into` or `drops_at`, `pipes_to` and `fluids`. A wrong inserter direction or a pole gap costs one `rotate` or `place` when caught at build time. Caught later, it costs minutes of stalled production. Section 8 maps each mistake to the field that reveals it.
6. **Batch refuelling with the numbers in section 5.** 50 coal lasts a stone furnace 37 min, a burner drill 22 min, and a boiler 111 s at full load.
7. **Place underground belts one end at a time.** `fac place underground-belt X,Y --direction D` places the entrance, and the same with `--belt-type output` places the exit; both face the way items travel, with at most 4 tiles between them for yellow (decision 49). `place --to` rejects underground belts, so each end is its own `place`. Underground pipes work, because their ports depend only on direction (see section 6.2).

---

## 2. Belts

### 2.1 Numbers

Belt speed values are from FD transport-belts.lua and entities.lua (`speed`, in tiles per tick). Throughput and density are from the wiki pages [Transport belts/Physics](https://wiki.factorio.com/Transport_belts/Physics) and [Belt transport system](https://wiki.factorio.com/Belt_transport_system).

| Tier | `speed` (tiles/tick) | Tiles/s | Items/s, one lane | Items/s, both lanes | Underground max gap (tiles) |
|---|---|---|---|---|---|
| Transport belt (yellow) | 0.03125 | 1.875 | 7.5 | **15** | 4 (`max_distance = 5`) |
| Fast (red) | 0.0625 | 3.75 | 15 | **30** | 6 (`max_distance = 7`) |
| Express (blue) | 0.09375 | 5.625 | 22.5 | **45** | 8 |

- Density is 4 items per lane per straight tile, 8 per tile in total, for any item and any tier (wiki Physics).
- A splitter runs at the same speed as its belt tier. It splits input 1:1, keeps items on their lane, and can prioritise an input or output and filter one item to one side ([wiki Belt transport system](https://wiki.factorio.com/Belt_transport_system)).
- A belt carries 15 items/s of coal, enough for about 33 boilers or 60 MW ([wiki Boiler](https://wiki.factorio.com/Boiler)).

### 2.2 Lanes: who puts items where

| Source | Lane it uses | Source |
|---|---|---|
| Inserter dropping onto a belt perpendicular to it | **Far lane** from the inserter | [wiki Inserters](https://wiki.factorio.com/Inserters) |
| Inserter dropping onto a belt that runs parallel to it (same or opposite direction) | The belt's **right** lane | wiki Inserters |
| Inserter picking from a belt | Prefers the near lane and takes the far lane when the near one is empty | wiki Inserters |
| Mining drill output | **Near lane** | FA Transport Belt Basics. Also `vector_to_place_result = {0, -1.85}` in FD puts the drop point 0.35 tiles past the drill edge, which is the near half of the tile `[INFERENCE]` |
| Belt side-loading onto the middle of another belt | **Both lanes** of the feeding belt go onto the **near lane** of the receiving belt | FA Transport Belt Basics |
| Two belts side-loading the same tile from opposite sides | Each fills its own lane, so the lanes do not mix | FA Transport Belt Basics |
| Underground belt entry or exit tile | Only the half with belt on it accepts side input. The tunnel half blocks, which can be used to split lanes | wiki Belt transport system |

**Application.** Two rows of drills facing one belt fill both lanes (layout C2). A row of inserters dropping onto one belt fills only one lane, so 7.5 items/s is the cap for a yellow belt fed from one side `[INFERENCE]`.

### 2.3 Belt direction pitfalls

- A belt that ends at nothing stops its items at the end; they don't fall off (wiki Transport belt history, 0.12). An inserter can take from that end tile, and items waiting there are easy to pick up.
- When the only belt feeding a belt tile comes in from the side, that tile turns into a curve instead of side-loading. This can happen when an agent lays a branch next to an existing line. UNVERIFIED (well-known game behaviour; no fetched page states it). Check it by inspecting the downstream tile or watching where items go.
- Rotating a belt that carries items picks those items up (wiki Transport belt history, 0.2.2).

---

## 3. Inserters

### 3.1 2.x speeds

Rotation and extension speeds are from FD. Cycle times and throughput are the wiki's 2.0.26 measurements ([wiki Inserters](https://wiki.factorio.com/Inserters)).

| Inserter | Pickup / drop offset | Rotation (turns/tick) | Ticks per cycle | Chest to chest, items/s (no bonus) | Power |
|---|---|---|---|---|---|
| Burner | 1 / 1.2 | 0.013 | 76 | 0.79 | burner fuel, 50 kJ per movement |
| Inserter (yellow) | 1 / 1.2 | 0.014 | 70 | **0.86** | 5 kJ per movement, 0.4 kW drain |
| Long-handed | **2 / 2.2** | 0.02 | 48 | 1.25 | 5 kJ, 0.4 kW drain |
| Fast | 1 / 1.2 | 0.04 | 24 | **2.5** | 7 kJ, 0.5 kW drain |
| Bulk | 1 / 1.2 | 0.04 | 24 | 5 (hand size 2) | 20 kJ, 1 kW drain |

- **Hand size (stack bonus).** Non-bulk inserters carry 1 item, 2 after capacity-bonus research level 2, and 3 at level 7. Bulk inserters carry 2, 4 and 12 at the same levels (wiki Inserters throughput table).
- Chest to belt, with one item per swing: inserter 0.85 items/s, burner 0.78 (wiki, 2.0 data). Belt to chest is a little slower and depends on lane and belt speed (wiki, 1.1 data; UNVERIFIED-2.x).
- The stack inserter is Space Age only (wiki). Base 2.x has the bulk inserter, the old "stack inserter" renamed.
- FA: "burner inserters can only keep up with basic belts, regular inserters can keep up with fast belts, and fast inserters can keep up with any belts."

### 3.2 Behaviour that matters for layouts

- **Auto-filtering.** An inserter picks up only what its target can use. Feeding an assembler, it takes only recipe ingredients (plus fuel for burner machines). Taking from a machine, it takes only products, never fuel (FA Inserters). One inserter can therefore pull several ingredients for one recipe from a single mixed chest `[INFERENCE from the same rule]`.
- **Insertion limits.** An inserter stops topping up once a target has enough (wiki Inserters):
  - Fuel in boilers, furnaces and burner inserters: 5 items.
  - Assembler, furnace, chemical plant and refinery ingredients: enough for 1 craft plus the crafts finished during one 1.166 s inserter swing, at least 2 crafts and at most 100.
  - Lab packs: the same rule per research unit.
  - So an assembler buffers only a few crafts of input, and extra input belongs in a chest.
- **Chests have no limit.** An inserter fills a chest completely. Speedrunners cap mall chests at about 3 stacks with the chest's limit bar (Zaspar). fac has no limit command, so pick the chest size as the cap: wooden 16 slots, iron 32, steel 48 (FD).
- **Dropping on the ground.** With nothing on its drop tile, an inserter places items on the ground, at most one item per tile (wiki Inserters). `inspect` reports this as `drops_at` instead of `drops_into`.
- **Burner inserters** run on fuel and refuel themselves from fuel they pick up (FA Inserters). Electric inserters stop during a blackout, so the inserter feeding a boiler should be a burner inserter. A whole grid can't restart if every boiler feeder is electric ([wiki Boiler](https://wiki.factorio.com/Boiler)).
- **Long-handed inserters** reach 2 tiles and skip the adjacent tile. Use them to take from a second belt, or to reach over a pole or belt (FA Inserters).

**Application.** The yellow inserter's 0.86 items/s is enough for a science assembler's own inputs: a red-science assembler 1 needs 0.1 gears/s and 0.1 copper/s. A furnace needs 0.3125 ore/s. It is not enough for a shared gear or circuit assembler: an assembler 1 on gears can use 2 iron/s and one on circuits 3 cable/s, so one yellow inserter caps it at 0.43 gears/s or 0.29 circuits/s. Feed those through several input inserters or a fast inserter. The other limit is the last inserter of a belt line that empties into a chest (layout C).

---

## 4. Mining drills and ore patches

| Drill | Size | Mining area | Speed | Ore/s (iron, copper, coal, stone; mining_time 1) | Energy | Output point (facing north, from center) |
|---|---|---|---|---|---|---|
| Burner | 2x2 | 2x2 (radius 0.99) | 0.25 | **0.25** | 150 kW burner, 0.0375 coal/s | (-0.35, -1.3): the **front-left** tile of the two front tiles |
| Electric | 3x3 | **5x5** (radius 2.49) | 0.5 | **0.5** | 90 kW electric | (0, -1.85): the tile **straight ahead**, near half |

Sources: FD mining-drill.lua (`mining_speed`, `resource_searching_radius`, `vector_to_place_result`, `energy_usage`), FD resources.lua (`mining_time = 1` for all four ores), [wiki Electric mining drill](https://wiki.factorio.com/Electric_mining_drill), [wiki Burner mining drill](https://wiki.factorio.com/Burner_mining_drill).

- The output point rotates with the drill. Rotating (dx, dy) clockwise gives (-dy, dx). Facing east, a burner drill drops at (+1.3, -0.35), into the upper of the two tiles to its east. That is why a burner drill at (5,0) facing east feeds a furnace at (7,0) (factobot test) `[INFERENCE: rotation arithmetic]`.
- A drill drops into any entity covering its output point: a furnace, a chest, another drill's fuel slot, or a belt (wiki). With nothing there, it drops one item on the ground and then waits.
- A burner drill on coal makes about 7 coal per coal burned (wiki), so 0.25 - 0.0375 = **0.2125 net coal/s** `[INFERENCE]`.
- `fac place` rejects a drill with nothing to mine under it (`protocol.md`). Only the drill's mining area needs ore. Furnaces, belts and inserters may stand on ore.
- **Ratios** (FA Ratios Cheat Sheet, consistent with FD):
  - 30 electric drills fill a yellow belt, 15 per lane.
  - One electric drill (0.5/s) more than feeds one stone furnace (0.3125/s), so 1.6 stone furnaces per drill.
  - One steel furnace (0.625/s) slightly outpaces one electric drill.
- **Patch layout.** Rows of electric drills sit edge to edge, 3 tiles apart. Two rows face a shared belt between them, which makes a band 7 tiles wide. Mining areas overlap by 1 tile each side, so bands can repeat every 7 tiles. Small poles go in a 1-tile gap after every 2 drills, as in layout C2 `[INFERENCE: geometry]`. Speedrunners stop at about half a lane per patch early (15 drills feeding 24 furnaces) (Zaspar).

**Application.** Prefer drill-into-furnace (layouts B and C) until the agent needs plates at a central place. A furnace output slot holds one stack (100 plates). At 0.25 plates/s it fills in 400 s, so a drill-to-furnace pair needs a `take` about every 6 minutes or it stalls `[INFERENCE]`.

---

## 5. Smelting

| Furnace | Size | Crafting speed | Plates/s (iron, copper: 3.2 s recipe) | Bricks/s (2 stone, 3.2 s) | Steel/s (5 iron, 16 s) | Fuel |
|---|---|---|---|---|---|---|
| Stone | 2x2 | 1 | **0.3125** | 0.3125 | 0.0625 | 90 kW = 0.0225 coal/s |
| Steel | 2x2 | 2 | 0.625 | 0.625 | 0.125 | 90 kW = 0.0225 coal/s |
| Electric | 3x3 | 2 | 0.625 | 0.625 | 0.125 | 180 kW electric |

Sources: FD entities.lua (`crafting_speed`, `energy_usage`) and FD recipe.lua (`iron-plate` 3.2 s, `stone-brick` 3.2 s for 2 stone, `steel-plate` 16 s for 5 iron). The [wiki Stone furnace](https://wiki.factorio.com/Stone_furnace) table agrees.

- **Furnaces per belt** (FA, and arithmetic on FD):
  - One yellow belt of ore feeds 48 stone or 24 steel furnaces.
  - One yellow belt of stone feeds 24 brick furnaces.
  - Steel takes 0.3125 iron/s per stone furnace, exactly one stone furnace of iron. So "iron furnace -> inserter -> steel furnace" is a balanced direct-insertion pair (FA).
- **Fuel endurance**, from coal at 4 MJ (FD `item.lua`) `[INFERENCE: arithmetic]`:

| Consumer | Coal/s at full load | 50 coal lasts |
|---|---|---|
| Stone or steel furnace | 0.0225 | 37 min |
| Burner drill | 0.0375 | 22 min |
| Boiler at 1.8 MW | 0.45 | 111 s |
| Boiler at 0.2 MW (early base) | 0.05 | 17 min |

- **Speedrun smelting** (Zaspar): half lanes of 15 drills and 24 stone furnaces, coal fed from a chest. Later a "compressor" (a merge) puts drill belts together. Steel gets ore priority, and its 24+24 furnaces run as a direct pair of rows.

**Application.** A full belt-fed smelting column takes per furnace one furnace, 2 inserters, about 2 belt tiles and a share of a pole: about 5 placements. Drill-into-furnace needs 2 placements per furnace and no ore belt. For the agent, columns are worth it only once a single belt of plates feeds a large consumer (for example 10 or more red-science assemblers) `[INFERENCE]`.

---

## 6. Power, pipes and fluids

### 6.1 Electric poles

| Pole | Size | Supply area | Wire reach | Notes |
|---|---|---|---|---|
| Small | 1x1 | **5x5** (2.5 from center) | **7.5** | available at start |
| Medium | 1x1 | 7x7 (3.5) | 9 | |
| Big | 2x2 | 4x4 (2) | 32 | for long runs |
| Substation | 2x2 | 18x18 (9) | 18 | |

Source: FD (`supply_area_distance`, `maximum_wire_distance`), [wiki Small electric pole](https://wiki.factorio.com/Small_electric_pole), [wiki Medium electric pole](https://wiki.factorio.com/Medium_electric_pole). Since 2.0.7, poles have no limit of 5 copper connections (wiki Medium electric pole history).

- A machine is powered when any part of its collision box overlaps a pole's supply area. Steam engines join the network the same way `[INFERENCE from layout F: one pole at 2 tiles' distance powers the engine and the lab]`.
- Poles placed by script **auto-connect** to neighbouring poles in wire reach (`auto_connect` defaults to true, [LuaSurface.create_entity](https://lua-api.factorio.com/latest/classes/LuaSurface.html)), so `fac place` connects them. Small poles therefore connect when at most 7 tiles apart on one axis (7.5 reach).
- Pole chains between a power plant and a remote site: small poles every 7 tiles, so 100 tiles take 15 poles and 15 `place` calls. Medium poles every 9 tiles take 12 `[INFERENCE]`.

**Power budgets** (FD `energy_usage`):

| Consumer | Power |
|---|---|
| Electric drill | 90 kW |
| Assembler 1 / 2 / 3 | 75 / 150 / 375 kW |
| Lab | 60 kW |
| Electric furnace | 180 kW |
| Chemical plant | 210 kW |
| Refinery | 420 kW |
| Pumpjack | 90 kW |
| Pump | 29 kW |

The offshore pump needs no power (energy source `void`, FD).

### 6.2 Pipes and fluids in 2.x

- **2.x fluid model** ([FFF #416](https://factorio.com/blog/post/fff-416), [wiki Fluid system](https://wiki.factorio.com/Fluid_system)):
  - Connected pipes, underground pipes and tanks form one segment holding one fluid.
  - Within a segment, flow is not limited by distance as long as the segment fits in 320x320 tiles. Past that it stops until a pump splits it.
  - Each input or output connection is capped at 6,000/s in theory and about 4,200/s in practice.
  - The 1.1 rule of thumb about pipe length and throughput does not apply in 2.x.
- Early demands are far below the cap: a boiler takes 6 water/s, a refinery on basic oil takes 20 crude/s, and a plastic plant takes 20 petroleum/s `[INFERENCE: from recipes below]`.
- **Volumes** (FD): pipe and underground pipe 100; boiler and steam engine 200; refinery and chemical plant inputs 1,000, outputs 100; storage tank 25,000.
- **Underground pipe** (pipe-to-ground):
  - Its normal pipe port faces its direction. Its underground port faces the opposite way, with a maximum distance of 10, which is a gap of up to **9 tiles** (FD `max_underground_distance = 10`; [wiki Pipe to ground](https://wiki.factorio.com/Pipe_to_ground)).
  - To bridge west to east, put the west piece facing **west** (pipe enters from the west) and the east piece facing **east** `[INFERENCE from the port definitions]`.
  - The gap holds no fluid, and the pair crosses belts and other undergrounds.
- **Mixing.** One segment holds one fluid, and mixing deletes all but one (wiki Fluid system). The game blocks most accidental mixes when placing, but not all. Keep different fluids at least one empty tile apart, or use underground pipes to cross.
- **Offshore pump**: 1,200 water/s (FD `pumping_speed = 20` per tick). It is placed on land at the shore, facing the water. `fac` rejects a bad spot and names the nearest one that fits within 4 tiles, with its direction (`docs/decisions.md` #42).

### 6.3 Steam

- Boiler (3x2): 1.8 MW. In 2.x, 1 water becomes 10 steam (2.0.7). Water heat capacity is 2 kJ/°C and steam 0.2 kJ/°C (FD fluid.lua). Steam at 165 °C carries 30 kJ per unit, so a boiler outputs 60 steam/s from 6 water/s ([wiki Boiler](https://wiki.factorio.com/Boiler)).
- Steam engine (3x5): 30 steam/s (FD `fluid_usage_per_tick = 0.5`), which gives **900 kW**.
- **Ratio 1 pump : 200 boilers : 400 engines** ([wiki Power production](https://wiki.factorio.com/Power_production)). This matches FD: 1200 / 6 = 200, and 1.8 / 0.9 = 2. 1.1-era guides say 1:20:40, because 1 water made 1 steam before 2.0.7. That ratio is wrong for 2.x, so do not use it.
- Boiler ports facing north (FD):
  - Water: input-output at (-1, +0.5) facing west and (+1, +0.5) facing east, on the short ends of the back row. Water passes through, so boilers chain end to end.
  - Steam: output at (0, -0.5) facing north.
- Engine ports facing north: (0, +2) south and (0, -2) north (FD). Engines chain end to end along their long axis.
- Zaspar's first-power advice: build a minimal plant and feed it a stack of coal. Frequent mistake number 1 on his list is "Connect power plants properly (water, fuel, poles)".

### 6.4 Oil

- **Refinery** (5x5), facing north (FD):
  - Inputs on the south side: box 1 at (-1, +2) and box 2 at (+1, +2). Pipes connect on the tiles (cx-1, cy+3) and (cx+1, cy+3).
  - Outputs on the north side: box 1 at (-2, -2), box 2 at (0, -2), box 3 at (+2, -2). Pipe tiles are (cx-2, cy-3), (cx, cy-3) and (cx+2, cy-3).
- **Recipe to port mapping:**
  - Basic oil processing: 100 crude in through **input box 2**, 45 petroleum out through **output box 3** (explicit `fluidbox_index`, FD recipe.lua). It takes 5 s, so one refinery uses 20 crude/s and makes **9 petroleum/s**.
  - Advanced oil processing: 50 water + 100 crude -> 25 heavy + 45 light + 55 petroleum in 5 s. Fluids map in order: water to input 1, crude to input 2, heavy to output 1, light to output 2, petroleum to output 3 `[INFERENCE: ingredient order, no explicit index]`.
- **Chemical plant** (3x3), facing north (FD):
  - Inputs at (-1, -1) and (+1, -1), on the north side. Pipe tiles are (cx-1, cy-2) and (cx+1, cy-2).
  - Outputs at (-1, +1) and (+1, +1), on the south side. Pipe tiles are (cx-1, cy+2) and (cx+1, cy+2).
  - Items go in and out on any side (wiki Chemical plant).
- **Chemical plant recipes:**
  - Plastic: 20 petroleum + 1 coal -> 2 plastic in 1 s.
  - Sulfur: 30 water + 30 petroleum -> 2 sulfur in 1 s.
  - Sulfuric acid: 5 sulfur + 1 iron + 100 water -> 50 acid in 1 s.
  - Port mapping: fluid ingredients take the input boxes in recipe order. Plastic's petroleum uses input 1 (the west port when the plant faces north). Sulfur's water uses input 1 and petroleum input 2 `[INFERENCE: basic oil sets fluidbox_index = 2 explicitly, which implies the default assignment is box 1, in order]`. Check after `set_recipe` with `inspect` (`status` other than `fluid_ingredient_shortage`) before laying long pipes.
- **Pumpjack** (3x3): the output port sits at (+1, -1) facing north when the pumpjack faces north. The pipe tile is (cx+1, cy-2), and the port rotates with the pumpjack (FD). Output per second = yield% / 10, so a 100% field gives 10 crude/s ([wiki Pumpjack](https://wiki.factorio.com/Pumpjack)). Two basic refineries need 40 crude/s, which is 400% total yield `[INFERENCE]`. Zaspar brings 1,600 to 2,000% yield, about 12 pumpjacks, for 10 refineries.
- **Rotating ports.** Facing east, south or west, rotate each port offset clockwise per quarter turn: (dx, dy) becomes (-dy, dx). Since 2.0.7, refineries and chemical plants can also be flipped, but fac has no flip, so use rotation only.

---

## 7. Assemblers, labs, malls and chests

- **Assemblers:**
  - Assembler 1: 3x3, speed 0.5, 75 kW, no fluid recipes.
  - Assembler 2: speed 0.75, 150 kW. Its fluid input is at (0, -1) facing north and its output at (0, +1) facing south, active only when the recipe uses fluid (FD `fluid_boxes_off_when_no_fluid_recipe`).
  - Assembler 3: speed 1.25.
  - Inserters may feed or empty an assembler from any side.
- **Lab**: 3x3, 60 kW. Inserters can move packs from one lab into the next, so labs chain `[INFERENCE: inserters take from any entity with an inventory, wiki Inserters]`.
- **Recipe switching.** `set_recipe` returns ingredients the new recipe doesn't use to the agent's inventory (`protocol.md`). An assembler 1 has no fluid ports, so switching it costs nothing in layout.
- **Early recipes** (FD recipe.lua; default craft time 0.5 s where none is given):

| Recipe | Time (s) | Inputs | Output |
|---|---|---|---|
| Iron gear wheel | 0.5 | 2 iron | 1 |
| Copper cable | 0.5 | 1 copper | 2 |
| Electronic circuit | 0.5 | 1 iron + 3 cable | 1 |
| Automation (red) pack | 5 | 1 copper + 1 gear | 1 |
| Logistic (green) pack | 6 | 1 inserter + 1 transport belt | 1 |
| Inserter | 0.5 | 1 circuit + 1 gear + 1 iron | 1 |
| Transport belt | 0.5 | 1 gear + 1 iron | 2 |
| Pipe | 0.5 | 1 iron | 1 |

- **Ratios with assembler 1:**
  - One red assembler makes 0.1 packs/s and one green assembler 0.083 packs/s.
  - One gear assembler (1 gear/s) supplies 10 red assemblers.
  - One inserter assembler, half a belt assembler and 1.5 gear assemblers supply 12 green assemblers (FA Ratios).
  - 3 cable assemblers feed 2 circuit assemblers (FA).
  - Zaspar's lab block uses 10 red and 12 green assemblers for 32 labs.
- **Mall (assemblers that make buildings).**
  - The speedrun pattern is assembler -> inserter -> chest, with chests limited to about 3 stacks. Zaspar's mall makes gears, belts, pipes, inserters, drills, undergrounds, splitters and assemblers.
  - An agent can skip the inserter and chest: hand-feed the assembler and `take` from its output. That saves 2 placements per mall item. The assembler stops when its output slot is full. The size of that cap is UNVERIFIED-2.x (I believe it is about one stack of the product).
  - How much one hand `insert` can put into an assembler's input slots is UNVERIFIED for fac. Read the `inserted` count it returns.
- **Hand-crafting runs alongside walking.** One `craft --count N` call queues N crafts at speed 1 (`docs/decisions.md` #32). Mall assemblers pay off for items needed in bulk while the craft queue is busy with other things `[INFERENCE]`.

---

## 8. Common building mistakes and how to catch them with `inspect`

`inspect` returns `status`, `direction`, `drops_into`, `drops_at`, `pipes_to`, `fluids`, `burning`, `inventories` and `recipe`. Status names are the game's `defines.entity_status` values (`protocol.md`; [defines](https://lua-api.factorio.com/latest/defines.html)).

| Mistake | Symptom | Inspect check | Fix |
|---|---|---|---|
| Inserter faces the wrong way | Items move backwards or not at all | Inserter `drops_into` names the wrong entity, or `drops_at` shows ground. Remember that direction D means it takes from D | `rotate` twice |
| Drill output points at nothing | Drill stops after one ore | Drill has `drops_at` instead of `drops_into`, status `waiting_for_space_in_destination` | `rotate` until `drops_into` names the furnace, chest or belt |
| Drill placed off ore or patch exhausted | No output | status `no_minable_resources` | Move the drill (`mine` + `place`) |
| Furnace, drill or boiler out of fuel | Production stops | status `no_fuel`, `burning` empty, fuel inventory empty | `insert` coal. Use the endurance table in section 5 to batch refuels |
| Furnace output full | Furnace idle, drill backs up | Furnace status `full_output`, output slot holds 100 plates | `take`, or add an output inserter |
| Pole gap or no grid | Machine idle | status `no_power`, or `low_power` when the grid is overloaded | Add a pole within 7 tiles of the network and within 2.5 tiles of the machine edge |
| Boiler not connected | Engines idle, lab `no_power` | Boiler `pipes_to` must list both `offshore-pump` and `steam-engine` (as in the factobot test). The engine's `fluids` should show steam | Re-place on the port tiles from section 6.3 |
| Fluid machine starved | Refinery or chem plant idle | status `fluid_ingredient_shortage`, `pipes_to` missing the pipe, `fluids` empty | Pipe on the exact port tile for that recipe's box (section 6.4) |
| Output fluid blocked | Refinery stops | `fluids` shows a full output box (100) | Give every product an outlet: a tank or a consumer |
| Fluid mixing | One fluid vanishes | `fluids` on a pipe shows the wrong fluid | Separate the segments; at least one tile or an underground pipe between fluids |
| Assembler without recipe or ingredients | Idle | status `no_recipe`, `item_ingredient_shortage` or `no_ingredients` | `set_recipe`; check the feeding inserter's `drops_into` |
| Lab idle | No research progress | status `no_research_in_progress` or `missing_science_packs` | `research`; feed packs |
| Belt runs the wrong way | Items pile at the start | `inspect` the belt `direction` | `rotate` (twice for a reversal). Rotating picks up the items on that tile |
| Burner inserter on a boiler starved | Grid dies and can't restart | Burner inserter `burning` empty | Put a coal in the inserter too; it refuels from what it carries |
| Electric inserter feeding the boilers | Blackout never recovers | Any boiler feeder that is not a burner inserter | Use a burner inserter for at least one boiler (wiki Boiler) |
| Underground belt pair not linked | Items stop at the entry | `inspect` on each end: `underground` should be `input` on the entrance and `output` on the exit, both facing the way items travel, and `paired_with` names the other end | Mine the wrong end and place it again with the right `--belt-type` or `--direction`, within 4 tiles for yellow |

**A sweep after each build costs one `inspect` per key entity:** every drill, every inserter that bridges machines, the boiler, and one consumer at the far end of each pole chain. Zaspar's "General hint: Take the time to double and triple check every setup before moving on" applies even more when each fix costs an agent turn.

---

## 9. Compact layouts to place entity by entity

Notation: O = (X, Y) is an origin you choose. Every position is (X + dx, Y + dy) with the offsets shown. Pick X and Y as integers, and the `.5` offsets land on tile centers. Directions use fac's convention from the table at the top. Each grid cell is one tile, with x increasing to the right and y increasing downward. Legend letters are listed under each grid.

### A. Burner drill coal pair (self-fuelling)

Both drills sit entirely on coal (2x4 tiles). Each drill fills the other's fuel slot.

```
dy\dx   -1  0 | 1  2
 -1      A  A | B  B
  0      A  A | B  B
A = burner-mining-drill at (0, 0) facing east  -> drops at (1.3, -0.35), inside B
B = burner-mining-drill at (2, 0) facing west  -> drops at (0.7, 0.35), inside A
```

- 2 placements, plus 2 `insert` of a few coal each to start.
- Net output is about 0.43 coal/s, which accumulates in the two fuel slots. They fill up (100 coal) from empty in about 4 minutes (50 / 0.2125 = 235 s per drill; the [wiki](https://wiki.factorio.com/Burner_mining_drill)'s "just under 3 minutes" disagrees), and then both stop.
- The agent collects with `take` item `coal` from each drill. `take` with an item name reads any inventory (`protocol.md`).
- Agent note: useful as a coal pickup point visited every few minutes. For steady coal, point a coal drill into a wooden chest (800-coal buffer) and refuel the drill by hand every 22 min.

### B. Burner iron column (drill into furnace)

```
dy\dx  -1  0 | 1  2
 -1     D  D | F  F
  0     D  D | F  F      row k: D at (0, 2k) facing east, F = stone-furnace at (2, 2k)
  1     D  D | F  F
  2     D  D | F  F      (k = 0, 1, 2, ...)
```

- Per pair: 2 placements, plus coal into both. The drill gives 0.25 ore/s and the furnace keeps up (0.3125/s).
- Collect plates by `take` on each furnace, at most 100 plates per furnace, which takes 400 s to fill.
- Agent note: this is the speedrun opening (Zaspar: 14 iron, 6 copper, 4 stone burners). Keep the furnaces on the outer edge of the patch so a later inserter or belt can reach them. Add a second column 4 tiles west (drills at x = -4 facing east into furnaces at x = -2), as seed-1.md has it.

### C. Electric drill -> stone furnace -> inserter -> belt -> chest (n cells)

```
dy\dx    0   1   2   3   4   5   6  ...  e   e+1  e+2
 -4.5    >   >   >   >   >   >   >  ...  >   Iw   C
 -3.5    Is  .   .   Is  .   .   Is
 -2.5    F   F   P   F   F   .   F       (F rows: furnace k spans x 3k..3k+2, y -3..-1)
 -1.5    F   F   .   F   F   .   F
 -0.5    D   D   D   D   D   D   D       (drill k spans x 3k-1..3k+2, y -1..2)
  0.5    D   D   D   D   D   D   D
  1.5    D   D   D   D   D   D   D
```

Cell k (k = 0..n-1):

| Entity | Position | Direction |
|---|---|---|
| electric-mining-drill | (3k+0.5, 0.5) | north. Drops at (3k+0.5, -1.35), inside the furnace |
| stone-furnace | (3k+1, -2) | none |
| inserter | (3k+0.5, -3.5) | **south**: takes from the furnace below, drops on the belt above (far lane) |
| transport-belt | (x, -4.5) for x = 0.5 .. e | east |

Shared entities:

| Entity | Position | Direction / note |
|---|---|---|
| small-electric-pole | (6j+2.5, -2.5), one per 2 cells | Covers x 6j..6j+5, y -5..0: both inserters and both drills. 6 tiles apart, within 7.5 reach |
| Pole for the end | near (e+1, -2.5) | must reach the end inserter |
| End inserter | (e+1, -4.5) | **west**: takes from the last belt tile |
| wooden-chest | (e+2, -4.5) | collection point |

- Placements: n x (drill + furnace + inserter + 3 belts) + n/2 poles + inserter + chest + pole, which is about 6.5n + 3 placements. Add n coal inserts (37 min each).
- Output: n x 0.3125 plates/s. The drill-limited alternative uses steel furnaces at 0.5/s per cell.
- **Bottleneck:** one yellow end inserter moves about 0.85 items/s, which is only 2.7 cells' worth. For n > 2, use a fast inserter (2.5/s, up to 8 cells). Or end the belt between 2 or 3 inserters, each into its own chest. Or run the belt straight into consumers `[INFERENCE: wiki throughput]`.
- Agent note: versus layout B with electric drills, this costs about 4.5 extra placements per cell but turns n `take` calls into one. It pays off once the line runs longer than about 10 minutes of collection rounds `[INFERENCE]`.

### C2. Two drill rows on one belt (ore to a smelter elsewhere)

```
dy\dx  -2 -1  0  1  2  3  4  5  6  7  8
 -2.5   .  N  N  N  N  N  N  .  N  N  N ...   N = drill facing south, centers (7q+0.5, -1.5), (7q+3.5, -1.5)
 -1.5   p  N  N  N  N  N  N  p  N  N  N       p = small pole (7q-1.5, -1.5) from q = 0
 -0.5   .  N  N  N  N  N  N  .  N  N  N
  0.5   .  >  >  >  >  >  >  >  >  >  > ...   belt, east (north row fills left lane, south row fills right lane)
  1.5   .  S  S  S  S  S  S  .  S  S  S
  2.5   p  S  S  S  S  S  S  p  S  S  S       S = drill facing north, centers (7q+0.5, 2.5), (7q+3.5, 2.5); p = (7q-1.5, 2.5)
  3.5   .  S  S  S  S  S  S  .  S  S  S
```

- Drills go in pairs, then one pole column. Drill centers are at x = 7q + 0.5 and 7q + 3.5, with small poles at x = 7q - 1.5 in both rows from q = 0, so one pole column stands before the first pair and then one in every gap (7 apart, within 7.5 reach). Each pole covers x 7q-4..7q+1, so it overlaps the drill on each side of its column, and the first column powers the first drill.
- 30 drills fill a yellow belt.
- Agent note: 3 placements per 2 tiles of belt per drill pair. Worth it only for a dedicated smelting column.

### D. Red science direct-insertion cell

```
dy\dx    0   1   2   3   4   5   6   7   8   9  10
  0.5    .   Ci  .   .   .   Cc  .   .   .   .   .
  1.5    .   In  .   P   .   In  .   P   .   .   .
  2.5    G   G   G   .   R   R   R   .   L   L   L
  3.5    G   G   G   Iw  R   R   R   Iw  L   L   L
  4.5    G   G   G   .   R   R   R   .   L   L   L
```

| Code | Entity | Position | Direction |
|---|---|---|---|
| Ci | wooden-chest, iron plates | (1.5, 0.5) | |
| In | inserter, chest to gear assembler | (1.5, 1.5) | north |
| G | assembling-machine-1, recipe iron-gear-wheel | (1.5, 3.5) | |
| Iw | inserter, gear to red | (3.5, 3.5) | west |
| Cc | wooden-chest, copper plates | (5.5, 0.5) | |
| In | inserter, chest to red | (5.5, 1.5) | north |
| R | assembling-machine-1, recipe automation-science-pack | (5.5, 3.5) | |
| Iw | inserter, red to lab | (7.5, 3.5) | west |
| L | lab | (9.5, 3.5) | |
| P | small-electric-pole | (3.5, 1.5) and (7.5, 1.5) | covers everything above |

- 11 placements, 2 `set_recipe`, 2 chest fills.
- Output: 0.1 red/s (6/min). That matches one lab on a 10 s research unit (automation is 10 units x 10 s).
- One wooden chest of 1,600 copper lasts 4.4 h. One of 1,600 iron lasts 2.2 h at 0.2 iron/s `[INFERENCE]`.
- To scale, chain a second lab with inserter (11.5, 3.5) west and lab (13.5, 3.5), plus pole (11.5, 1.5). For a second red assembler, build a second cell like this one beside it, with its own chests, poles and lab.
- Agent note: no belts at all. The milestone needs assembler-made packs only, so this cell is enough to score red.

### E. Green science direct-insertion block

Grid of 3x3 machines with a 4-tile pitch. Inserters sit in the 1-tile gaps.

```
dy\dx  0  1  2  3  4  5  6  7  8  9 10 11 12
 -1.5  .  Cc .  .  .  Ci .  .  .  .  .  .  .
 -0.5  .  In .  P  .  In .  .  .  .  .  .  .
  0.5  K  K  K  .  E  E  E  .  .  .  .  .  .
  1.5  K  K  K  Iw E  E  E  .  .  .  .  .  .
  2.5  K  K  K  .  E  E  E  .  .  Ci .  .  .
  3.5  .  .  .  P  .  In .  P  .  In .  .  .
  4.5  .  .  .  .  N  N  N  .  G  G  G  .  .
  5.5  .  .  Ci Iw N  N  N  Ie G  G  G  .  .
  6.5  .  .  .  .  N  N  N  .  G  G  G  .  .
  7.5  .  .  .  .  .  In .  P  .  In .  P  .
  8.5  .  .  .  .  S  S  S  .  B  B  B  .  .
  9.5  .  .  .  .  S  S  S  Ie B  B  B  Ie Ci
 10.5  .  .  .  .  S  S  S  .  B  B  B  .  .
 11.5  .  .  .  .  .  In .  P  .  .  .  .  .
 12.5  .  .  .  .  L  L  L  .  .  .  .  .  .
```

| Code | Entity / recipe | Position | Direction |
|---|---|---|---|
| K | AM1 copper-cable | (1.5, 1.5) | |
| Cc + In | chest of copper; inserter | (1.5, -1.5); (1.5, -0.5) | north |
| Iw | inserter, K to E | (3.5, 1.5) | west |
| E | AM1 electronic-circuit | (5.5, 1.5) | |
| Ci + In | chest of iron for E; inserter | (5.5, -1.5); (5.5, -0.5) | north |
| In | inserter, E to N | (5.5, 3.5) | north |
| N | AM1 inserter | (5.5, 5.5) | |
| Ci + Iw | chest of iron for N; inserter | (2.5, 5.5); (3.5, 5.5) | west |
| G | AM1 iron-gear-wheel | (9.5, 5.5) | |
| Ci + In | chest of iron for G; inserter | (9.5, 2.5); (9.5, 3.5) | north |
| Ie | inserter, G to N | (7.5, 5.5) | east |
| In | inserter, G to B | (9.5, 7.5) | north |
| B | AM1 transport-belt | (9.5, 9.5) | |
| Ci + Ie | chest of iron for B; inserter | (12.5, 9.5); (11.5, 9.5) | east |
| Ie | inserter, B to S | (7.5, 9.5) | east |
| In | inserter, N to S | (5.5, 7.5) | north |
| S | AM1 logistic-science-pack | (5.5, 9.5) | |
| In | inserter, S to lab | (5.5, 11.5) | north |
| L | lab, or a chest | (5.5, 13.5) | |
| P | small-electric-pole | (3.5, -0.5), (3.5, 3.5), (7.5, 3.5), (7.5, 7.5), (11.5, 7.5), (7.5, 11.5) | all 4 apart |

- About 30 placements, 6 `set_recipe`, 5 chest fills.
- Output: 0.083 green/s (5/min). As drawn, the block supports about 3 green assemblers: G's one iron inserter gives 0.43 gears/s and the one cable inserter K to E gives 0.29 circuits/s, and a pack takes 1.5 gears and 1 circuit, so both cap near 0.29 packs/s. 12 green assemblers (the FA ratio) need about 4 times the input inserters, or fast inserters, and a feed path per assembler `[INFERENCE: recipe arithmetic]`.
- Iron per green pack: 5.5 plates (2 gear + 1 for the inserter, 1 circuit, 1.5 for the belt), so 0.46 iron/s. Copper: 1.5 plates per pack `[INFERENCE: recipe arithmetic]`.
- **Fewer-action alternative for the milestone.** One green assembler, one chest and 2 inserters plus a pole, about 5 placements. Keep the chest stocked with hand-crafted inserters and belts; the auto-filtering inserter pulls both from one chest.
  - Hand-crafting costs about 2.25 s per inserter and 0.5 s per belt, so about 2.75 s of queue per pack `[INFERENCE: FD recipe times]`.
  - That is fine to unlock the green milestone and the first green techs. It is too slow for the roughly 5,800 green packs on the rocket path (`human-baselines.md` §3c).

### F. Steam power block (1 pump, 1 boiler, 2 engines, fed from a coal chest)

Tested geometry (`test_research_needs_a_powered_lab`) for water to the **east**, with the pump at P = (px, py):

```
dy\dx(rel P)  -4  -3  -2  -1   0   +1
   -11         .   E   E   E   .   .
   ...         .   E   E   E   .   .        E2 = steam-engine at (px-2, py-9), north
    -7         p   E   E   E   .   .        p  = small-electric-pole at (px-4, py-7)
   ...         .   E   E   E   .   .        E1 = steam-engine at (px-2, py-4), north
    -1         .   Bo  Bo  Bo  .   ~        Bo = boiler at (px-2, py-0.5), north (steam up)
     0         .   Bo  Bo  Bo  O   ~        O  = offshore-pump at (px, py), east (water ~)
    +1         .   .   Ib  .   .   ~        Ib = burner-inserter at (px-2, py+1), south
    +2         .   .   Ch  .   .   .        Ch = wooden-chest of coal at (px-2, py+2)
```

The test placed: pump (4.5, -3.5) east, boiler (2.5, -4) north, engine (2.5, -7.5) north, pole (0.5, -7.5), lab (-2.5, -7.5). The boiler's `pipes_to` then lists `offshore-pump` and `steam-engine`.

- E2 (second engine) at (2.5, -12.5) joins E1 through their end ports (FD ports at (0, ±2)) `[INFERENCE]`.
- Moving the pole to (0.5, -10.5) lets one pole cover both engines (supply y -13..-8) `[INFERENCE: geometry]`.

Offsets for the other shores. Rotate offsets and directions clockwise per quarter turn `[INFERENCE: rotation arithmetic, verified for east only]`:

| Water side (pump direction) | Boiler | Engine 1 | Engine 2 | Pole | Burner inserter | Coal chest |
|---|---|---|---|---|---|---|
| east | (-2, -0.5) N | (-2, -4) N | (-2, -9) N | (-4, -7) | (-2, +1) S | (-2, +2) |
| south | (+0.5, -2) E | (+4, -2) E | (+9, -2) E | (+7, -4) | (-1, -2) W | (-2, -2) |
| west | (+2, +0.5) S | (+2, +4) S | (+2, +9) S | (+4, +7) | (+2, -1) N | (+2, -2) |
| north | (-0.5, +2) W | (-4, +2) W | (-9, +2) W | (-7, +4) | (+1, +2) E | (+2, +2) |

- 7 placements, plus coal into the chest (800 max) and 1 coal into the burner inserter.
- The block gives 1.8 MW. At 0.2 MW of early load, 800 coal lasts about 4.4 h; at full load, 30 min `[INFERENCE]`.
- To expand, add boilers on the free water port at the other end of the boiler, then 2 engines per boiler.
- Agent note: let `place` find the pump spot first (its rejection names the spot and direction). Then use the row for that direction. Verify once with `inspect` on the boiler (`pipes_to`) and one consumer (`status` `working`).

### G. Two-refinery basic oil block (plus one plastic plant)

```
dy\dx  -2 -1  0  1  2  3  4  5  6  7  8
 -9.5   .  .  .  .  .  .  Ch .  .  .  .     Ch (4.5,-9.5) plastic out chest
 -8.5   .  .  .  .  .  .  Is .  p  .  .     Is (4.5,-8.5) south ; p pole (6.5,-8.5)
 -7.5   .  .  .  .  .  C  C  C  .  .  .
 -6.5   .  .  .  .  .  C  C  C  Ie Cc .     C = chemical-plant (4.5,-6.5) facing SOUTH, recipe plastic-bar
 -5.5   .  .  .  .  .  C  C  C  .  .  .     Ie (6.5,-6.5) east ; Cc coal chest (7.5,-6.5)
 -4.5   .  .  .  .  .  .  .  =  .  .  .     petroleum stub (5.5,-4.5) -> plant input box 1
 -3.5   .  .  .  .  =  =  =  =  =  =  =>    petroleum header y=-3.5, x 2.5..7.5 (+ onward)
 -2.5   .  .  .  .  =  .  .  .  .  =  .     stubs (2.5,-2.5) R1 box 3, (7.5,-2.5) R2 box 3
 -1.5   R  R  R  R  R  Q  Q  Q  Q  Q  .
 ...    R1 at (0.5,0.5) north | R2 at (5.5,0.5) north   (each 5x5)
  2.5   R  R  R  R  R  Q  Q  Q  Q  Q  .
  3.5   .  .  .  =  .  p  .  .  =  .  .     stubs (1.5,3.5) R1 box 2, (6.5,3.5) R2 box 2 ; pole (3.5,3.5)
  4.5   .  .  .  =  =  =  =  =  =  =  <=    crude header y=4.5, x 1.5..6.5, fed from the pumpjack
```

- **Refineries:** R1 at (0.5, 0.5) and R2 at (5.5, 0.5), both north-facing, recipe basic-oil-processing.
- **Crude in** through input box 2, tile (cx+1, cy+3): (1.5, 3.5) and (6.5, 3.5). **Petroleum out** through output box 3, tile (cx+2, cy-3): (2.5, -2.5) and (7.5, -2.5).
- Both headers run one row further out, so no pipe touches an unused port. That keeps the switch to advanced oil (water into box 1, heavy and light out of boxes 1 and 2) from mixing fluids `[INFERENCE: precaution; behaviour of pipes on unused ports not tested]`.
- **Plastic plant** faces south, so its inputs sit on its south side. Rotated 180°, input box 1 is at (+1, +1) facing south, pipe tile (cx+1, cy+2) = (5.5, -4.5).
- **Power:** pole (3.5, 3.5) covers both refineries (supply x 1..6, y 1..6). Pole (6.5, -8.5) covers the plant and both its inserters. The two are 12.4 tiles apart, past the 7.5-tile wire reach, so a link pole at (8.5, -1.5), east of R2, joins them (7.07 and 7.28 tiles). The block needs a chain to the grid (7-tile steps).
- **Numbers:**
  - 2 refineries take 40 crude/s (400% total pumpjack yield) and make 18 petroleum/s, which is 0.9 of one plastic plant (20/s) at 1.8 plastic/s `[INFERENCE: FD recipes]`. That needs fast inserters for coal in (0.9/s) and plastic out (1.8/s); yellow ones (0.86/s) cap the plant at about 0.86 plastic/s.
  - Power: 2 x 420 kW + 210 kW = 1.05 MW, plus at least 4 pumpjacks at 90 kW each for 400% yield, about 1.4 MW, within one boiler's 1.8 MW `[INFERENCE]`.
- About 2 refineries + 1 plant + 2 fast inserters + 2 chests + 3 poles + about 20 pipes, roughly 30 placements before the pumpjack pipeline.
- Use underground pipes (9-tile gaps) on the long run from the pumpjacks to cut placements by up to 5x `[INFERENCE: 2 pieces per 11 tiles instead of 11 pipes]`.
- Agent note: after `set_recipe`, `inspect` each refinery and the plant. `pipes_to` should list the header pipes, and `status` should not be `fluid_ingredient_shortage`. Fix the stub tile before extending the pipe.

---

## 10. Design approaches compared for this agent

| Approach | What it is | Placements per useful machine `[INFERENCE]` | Fit for fac |
|---|---|---|---|
| Hand-fed machines | Agent inserts inputs and takes outputs | 1 | Best for short-lived needs. Zaspar's "mini science" is 7 assemblers hand-fed near the iron burners |
| Drill into furnace | Drill output tile on a furnace | 2 per furnace | Best smelting start (Zaspar burner phase) |
| Direct insertion | Machine -> inserter -> machine, chests as buffers | 2 to 3 | Best for science cells and circuits. Speedrunners build purple and the mixed circuit/LDS block this way (Zaspar) |
| Belt lines and columns | Ore and plate belts with inserters | 4 to 6 | Worth it for high-volume plates once one belt feeds many consumers |
| Main bus | Parallel plate and intermediate belts with splitters off to production rows ([wiki Tutorial:Main bus](https://wiki.factorio.com/Tutorial:Main_bus)) | High: many belt runs (one `place --to` each), splitters and the inserters off them | Poor. It is designed for growth, not speed, and needs many undergrounds, each end its own `place` |
| Spaghetti | Ad-hoc belts between nearby blocks | Medium | Acceptable for short links. Zaspar leaves a 10-tile gap after the smelter "so you have space to spaghetti things later" |
| Construction robots and blueprints | Speedrunners switch to bots and blueprints after blue science (Zaspar: roboports, "print" smelters, the mixed build copied 3 times) | n/a | **Not available.** fac has no ghosts or blueprints, so construction bots have nothing to build |
| Logistic robots | Requester and provider chests | n/a | Possible in principle, but it needs roboports, a logistic tech and bot production. Speedrunners don't use them for the main chains. Not worth it for this agent `[INFERENCE]` |

**What this means for the agent `[INFERENCE]`.** Speedrunners place most entities by drag-building and, after blue science, by blueprint, so a single action places many entities. An agent at 5 to 30 s per action makes 2 to 12 placements per game minute, one entity each. The agent should:
- Build about 5 to 10 times fewer entities than a speedrunner for the same output.
- Lean on hand-fed assemblers, drill-into-furnace and direct-insertion cells.
- Keep each cell inside one 10-tile build radius.
- Size the factory to the minimum the research needs (the closure costs are in `docs/human-baselines.md` §3c), not to speedrun throughput.

---

## 11. Gaps and unverified items

- Chemical plant port assignment for single-fluid recipes (plastic petroleum on input box 1) is `[INFERENCE]`. Confirm with `inspect` in game.
- The assembler output cap and how much one hand `insert` can put into an assembler are UNVERIFIED-2.x in fac.
- The belt auto-curve behaviour when a belt only feeds from the side is UNVERIFIED (no fetched source).
- Burner drill flipping (2.1.7, wiki Burner mining drill) changes the output tile of a flipped drill. fac doesn't flip, so the default (front-left tile) applies.
