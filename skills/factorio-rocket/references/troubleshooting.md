# Troubleshooting with `fac inspect`

Read this when something stopped producing, or right after a build to check it. `fac inspect X,Y` works on anything within 32 tiles and returns `status`, `direction`, `drops_into` or `drops_at`, `picks_from`, `burning`, `pipes_to`, `fluids`, `recipe`, `missing`, `rates`, `power` and `inventories` (named `fuel`, `crafter_input`, `crafter_output`, `chest`, `lab_input`, `lab_modules` and so on). `status` is the game's entity status, e.g. `working`, `no_fuel`, `no_power`, except that a machine connected to no generator shows `not_plugged_in_electric_network`.

## The check after each build

- `fac observe --problems`: every machine in the block that is not working, with what it is `missing` (a lab shows only `missing_science_packs`).
- every drill and every inserter that bridges two machines: `drops_into` (and `picks_from`) names the building or the belt lane you meant;
- the boilers: `pipes_to` lists `offshore-pump` (or the next boiler) and `steam-engine`;
- one consumer at the far end of each pole chain: `status` is `working`, not `not_plugged_in_electric_network` or `no_power`;
- every fluid machine after `fac recipe`: `status` is not `fluid_ingredient_shortage`, and `pipes_to` names the pipes you laid;
- `fac screenshot`: no plug, lightning or fuel icon, no gap in a belt, no pipe ending open;
- then wait for the first product at the far end of the line and see it arrive.

## Finding the cause of a stall

Start at the machine that should make the thing that is missing and walk upstream, one ingredient at a time (SKILL.md, "The stall protocol"). The statuses tell you which way to look:

| Status | Look |
|---|---|
| `item_ingredient_shortage`, `fluid_ingredient_shortage`, `no_ingredients` | upstream: `missing` names what is short; follow that item back |
| `missing_science_packs` | upstream: a lab shows no `missing`. The pack that is short is the one in `cost.packs` of `fac research TECH --show` that the lab's `lab_input` does not hold; follow that pack back |
| `full_output`, `waiting_for_space_in_destination` | downstream: what should take the output is not taking |
| `no_power`, `low_power` | the generators: fuel, water, too few boilers |
| `not_plugged_in_electric_network` | the poles: none reaches the machine, or the chain to the generators is broken |
| `no_fuel` | the coal lane, or a burner you still feed by hand |
| `no_minable_resources` | the ore under the drill is gone: move the drill |
| `no_recipe` | `fac recipe` |

## Symptom to cause

| Symptom | Inspect shows | Cause and fix |
|---|---|---|
| Drill mines one ore, then stops | `drops_at` instead of `drops_into` | Output points at nothing. `fac rotate` until `drops_into` names the target, or move the target to the drop point (layouts.md, "Directions in fac"). |
| Drill idle on ore | `no_minable_resources` | Placed off the ore or the area is mined out. Pick it up with `fac mine` and place it on ore. |
| You want a faster building where a slower one stands | | Place the faster one (an assembling machine 2 on an assembling machine 1) on it: it swaps in place, keeps recipe and contents, and the answer shows `replaced`. The inserters around it name the new building at once (tested, science.md and smelting.md). No `replaced` in the answer: read it before going on. |
| Burner machine idle | `no_fuel`, `burning` empty, `fuel` empty | The coal lane is empty (follow it back to the coal drills), or the machine is still hand-fed: 50 coal lasts a burner drill 22 min, a furnace 37 min, a boiler 111 s at full load. Put it on the coal lane. |
| Furnace idle, drill backed up | furnace `crafter_output` holds 100 plates | Nothing takes the plates: the output inserter is missing, unpowered or facing the wrong way, or the plate belt is full (downstream). |
| Furnace makes bricks or steel | `crafter_input` holds stone or plates | Only ore goes into iron and copper furnaces. Once `steel-processing` is done, iron plates in a furnace become steel. |
| Furnace stuck on the old ore | `crafter_input` holds the other ore | One ore type per furnace. Take the input out, and find how the other ore got on that lane. |
| Inserter moves nothing or the wrong way | `drops_into` names the wrong entity, or `drops_at`; `picks_from` names nothing | An inserter facing D picks up from the D side. `fac rotate` twice reverses it. |
| Machine idle with power poles nearby | `not_plugged_in_electric_network`, and no `power` field | No pole reaches it: no pole within 2.5 tiles of the machine's edge. One tile off is enough. |
| Machine idle on a pole, no generator | `not_plugged_in_electric_network`, and `power.capacity_kw` is 0 | The pole's network has no generator: the pole chain breaks somewhere (small poles connect at most 7.5 tiles apart), or you mined a pole that linked two parts. |
| Everything slow | `low_power`, and `power.satisfaction` below 1 in `fac inspect` on any pole; the HUD warns too | Demand is over capacity. If `capacity_kw` is lower than your last note, a boiler has no fuel (`fac observe --problems` at the boilers). Otherwise add boilers and engines: 1.8 MW per boiler with 2 engines. |
| Capacity lower than your last note, nothing slow yet | `power.capacity_kw` fell | A boiler stopped: its coal lane is empty or its inserter has no fuel. Fix it now; the brown-out comes with the next block you build. |
| Blackout: everything `no_power`, `capacity_kw` 0 or flickering | boilers `no_fuel`; the electric coal drills crawl or stand still | The loop: too little power slows the coal drills, so less coal, so less power. Coal by hand alone does not break it while the factory still hangs on the network (tested: 5 coal gave 1.8 MW for seconds, then 0). Cut the factory off first by mining the one pole that joins it to the power block, put 5 coal into the first boiler, wait about a minute for the drills to refill the belt, add boilers and coal drills until capacity is above the demand you saw, then put the pole back (power.md, "Extending, upgrading, limits, failure", the recovery steps). |
| A burner inserter stands still with coal on the belt in front of it | the inserter's own `status` is `no_fuel` | A burner inserter that has run completely dry cannot pick up its first coal. `fac insert X,Y coal 1` into the inserter itself. |
| `hud` warns "no power on the network of the pole at X, Y" | that pole's `power.capacity_kw` is 0 | The pole line does not reach the generators, or the boilers lack fuel or water. Follow the poles back to the power block; there, `fac inspect` the boilers. If the coal drills crawl, it is a blackout: power.md, "Extending, upgrading, limits, failure", the recovery steps. |
| Engines idle, lab `no_power` | boiler `ports` show a water port with no `joined_to`; engine `fluids` has no steam | Pump, boiler and engines are off their port tiles: `fac inspect` each and lay pipe on the `pipe_at` of every port that has no `joined_to`. Use the tested power block (power.md). |
| An engine makes nothing though it has steam | `not_plugged_in_electric_network` on the engine; a pole's `capacity_kw` is lower than 1800 per boiler | No pole reaches the engine. An engine without steam says `no_input_fluid` either way, so count: `capacity_kw` must rise by 1800 with every boiler and its two engines. |
| Assembler idle | `no_recipe`, or `item_ingredient_shortage` with `missing` naming the short ingredient | `fac recipe X,Y NAME`; follow the `missing` ingredient back: the feeding inserter's `picks_from`, `drops_into` and `status`, the belt lane it takes from, and `fac stats ITEM` for whether anything makes it. |
| A belt lane packed with an item nothing takes | `fac observe` shows two items on one lane, or the wrong item | Something drops a second item onto the lane: a drill over two ores, an inserter on the wrong side, a chest that holds two items feeding one inserter. Find the machine whose `drops_into` names that lane, move it, `fac take` the stray items off the belt. One inserter per item, one item per lane (belts.md). |
| One item reaches a machine and the other does not, both from one chest | the chest's `chest` inventory holds both; the machine is `missing` the second | An inserter takes from a chest in slot order and the belt lane fills with the first item. Give each item its own chest and inserter, or its own lane. |
| A pack or product piles up in a chest | the chest fills; `fac stats` shows it made but not used | A production line ends in a chest nobody empties. Put an inserter and a belt from it to where it is used. Never plan to carry it. |
| Refinery or chemical plant idle | `fluid_ingredient_shortage`, `fluids` empty (a chemical plant also missing its coal or iron shows `item_ingredient_shortage` instead) | Read `ports`: an input with no `joined_to` has no pipe on its `pipe_at` (lay one there or turn the plant); a port with `problem` is joined to a pipe of another fluid (two pipes swapped, or one header touching both inputs). Nothing flowing at all: the pumpjack is unpowered (oil.md, "1. Fluid ports" and "What wrong piping looks like"). |
| Refinery stops after running | `full_output`; `fluids` shows a full output box | Every fluid product needs a sink: a consumer, cracking, or a tank. A refinery `working` for 20 s and then `full_output` usually has an output pipe on the wrong tile: the `ports` entry for that fluid has no `joined_to`; move the pipe to its `pipe_at`. |
| Fluid line delivers nothing | `pipeline_overextended` on the pipes in `fac place` or `fac inspect` | One fluid segment spans more than 320 tiles. Put a powered pump in it at least every 300 tiles, or shorten it (oil.md, "Long pipes: pipe-to-ground"). |
| A pipe-to-ground carries nothing | no `paired_with` in its answer; `fac place` warned "its underground end joins nothing yet" | Its partner is more than 10 tiles away, not in the same row, or facing the same way. Mine it with `--wait` and place it where the warning says. |
| A machine got the wrong fluid | a port in `fac inspect` has `problem`, or a pipe's `fluids` shows another fluid than you laid | Two fluid lines are joined. The game refuses most placements that would mix two fluids, but a pipe can still meet a machine port of another fluid: the machine then starves. Keep one empty tile, or a pipe-to-ground, between different fluids, and read `ports` (oil.md, "What wrong piping looks like"). |
| Something stopped after you changed a recipe elsewhere | the stalled machine is `missing` what the changed machine used to make | You switched off its only source (sulfur, lubricant, petroleum). Before any recipe change, list what uses the old product; switch back, or build a second machine for the new product. |
| Lab idle | `no_research_in_progress` or `missing_science_packs` | Queue research (`fac research`), or feed packs. Each lab needs every pack type the current technology uses; in a lab chain, packs enter at the first lab and pass down the chain, so a pack fed into the middle never reaches the labs before it. |
| Research progress hasn't moved between two checks | `fac research` shows the same `progress`; the HUD says so after 2 minutes | Labs are starved: `fac inspect` the first lab and compare its `lab_input` with `cost.packs` of `fac research TECH --show` (a lab shows `missing_science_packs` and no `missing`); `fac stats` the pack that is not there, then the stall protocol from its assembler. Or power is `low_power`. |
| Research slower than the science assemblers make packs | every lab `working`; pack assemblers `full_output` | Too few labs, not too few packs: 0.3 packs/s on a 30 s technology needs 9 labs at speed 1 (research.md). |
| Items stop at an underground belt | both pieces are entrances | Place the exit with `--belt-type output`. |
| `take` fails or takes less than you asked | `your inventory is full`; the HUD shows few `free_slots` | Empty what you don't need into a chest. A script that hid this error left 510 purple packs lying in a chest for 2 hours in a test run. |
| `mine` job failed early | the job's `error` says the inventory is full | Same. 80 slots hold 4,000 ore. |
| `mine` job vanished | `fac jobs` is empty | A new `walk` cancels a running `mine`. Do in-reach work while mining; walk afterwards. |
| `walk` fails with no path at once | `distance_walked` 0 | You are closed in, usually in a one-tile gap between machines; the error says whether you or the target is closed in. Pick up the pole, chest or inserter beside you with `fac mine`, step out, and put it back from outside. A target inside a building fails the same way: walk to a free tile next to it. |
| You are somewhere you did not walk to | `fac observe` shows a position on a belt's path | You stood on a belt and it carried you. Stand beside belts, not on them. |
| A loop placed or filled fewer things than planned | inventory counts don't add up; `fac observe` lacks some buildings | The loop sent its errors to `/dev/null` (out of reach, standing there, out of items). Rerun it printing failures with SKILL.md's `f` helper; placing again is safe, since standing buildings answer `already_there`. |
| Recipe locked | `rejected` names the technology, and for a trigger what to do (`oil-refinery` and `chemical-plant`: `oil-processing` when you extract crude-oil with a pumpjack) | A lab technology: `fac research TECH` queues it; `--show` lists `needs`. A trigger technology such as `oil-processing` can't be queued: it finishes by itself once a powered pumpjack extracts crude. |
| Tried to mine crude oil, or to insert petroleum | `crude-oil can't be mined by hand` and a pumpjack, or `<fluid> is a fluid` | Place a pumpjack on the well and pipe the fluid. `fac inspect` shows `fluids` and `pipes_to`. |
| `plastics`, `advanced-circuit`, `sulfur-processing` or `chemical-science-pack` will not queue | the rejection names `oil-processing`; `fac research oil-processing --show` is not researched | The trigger has not fired. A pumpjack `fac inspect` must show `working` and `crude-oil` in `fluids`. `not_plugged_in_electric_network` means no generator reaches it (the pole line to the field is not joined, or big poles wait on `electric-energy-distribution-1`); `no_power` means the grid makes too little. |
| Plastic or sulfur stopped | `no_power`, `not_plugged_in_electric_network`, `full_output`, `item_ingredient_shortage` or `fluid_ingredient_shortage` on the plant | Power; room on the output belt; coal on the plastic plant's lane (`item_ingredient_shortage`); petroleum into both; water into sulfur. A plant short of petroleum part of the time while the other runs is sharing it: add a refinery or pumpjacks. |
| Advanced circuits or blue packs stopped | assembler `item_ingredient_shortage` with `missing` | Advanced circuits need plastic, circuits and cable. `chemical-science-pack` needs engines, advanced circuits and sulfur. Follow the missing one back, usually to the oil site or its belt. |
