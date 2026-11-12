# Opening: an empty map to the first assembler-made red pack

Read this at the start of a run on a fresh map. Every map is different: nothing here is a coordinate. You find each place with `fac map`, `fac observe --radius 32` and `fac screenshot --zoom 0.5`, and you write what you find into your notes file before you build on it (SKILL.md, "Notes"). Source: `research/early-game.md`.

## Numbers that drive the opening

- You start with 1 burner mining drill, 1 stone furnace, 8 iron plates and 1 wood.
- Hand-mining: 2 s per ore. A huge rock: 6 s for 24 to 50 coal and as much stone. A big rock: 4 s for 20 stone. A tree: 1.1 s for 4 wood. Rocks and trees show in `fac observe`, never in `fac map`.
- A burner pair (burner drill into a stone furnace) makes 0.25 plates/s, burns 3.33 coal/min, costs 9 iron and 10 stone, and stalls after 400 s when nobody takes its 100 plates.
- A burner drill on coal dropping into a chest nets about 13 coal/min, enough for 3.8 burner pairs.
- Trigger technologies: smelting 50 iron plates unlocks pipes, the offshore pump, boiler and steam engine; smelting 10 copper plates unlocks cables, circuits, inserters, labs and small poles; crafting the first lab unlocks the red pack recipe. Apart from the burner inserter and the chests, nothing in the power block or the lab can be crafted before these fire.
- Shopping list to the milestone, with a 1-boiler start: lab (36 iron, 15 copper), offshore pump (7 iron), boiler (4 iron, 5 stone), 2 steam engines (62 iron), burner inserter (3 iron), a chest, small poles (1 wood and 1 copper make 2), 10 red packs (20 iron, 10 copper), 2 assembling machine 1 (44 iron, 9 copper), 1 inserter and 1 long-handed inserter. About 250 iron and 60 copper plus the poles between the water and the base; each further boiler with its 2 engines and burner inserter costs about 70 iron and 5 stone.

## Look first (one or two turns)

1. `fac observe`, `fac map` and `fac research`. `fac map` lists iron, copper, coal, stone and water with a center, a nearest tile and a size. Write each into your notes.
2. Pick the base site now, before the first building, because everything else is measured against it (base-plan.md), and choose the science block's anchor on the iron trunk's line there (science.md): open ground beside the iron patch, on the side that faces the copper and the water, with room for a block at least 100 by 60 tiles clear of water, cliffs and other ore. Walk there once and take `fac screenshot --zoom 0.5` to see trees, rocks, cliffs and water that `fac map` doesn't list.
3. If no water shows in `fac map`, walk toward unexplored ground (a walk reveals the map around you) until one does. Power needs it, and the fish you launch at the end live in it.

## The sequence

Each step is one or a few shell calls. Queue crafts the moment their ingredients exist; they run while you walk and mine.

1. **Rocks on the way to the iron.** `fac observe --radius 32` names `huge-rock` and `big-rock` entities; walk within 2 tiles of each and `fac mine X,Y --wait`. Aim for 150 coal and 150 stone before you settle. Craft stone furnaces as stone comes in.
2. **First burner pair on iron.** `fac map iron-ore` shows the patch row by row. Place the starting drill on the patch edge facing off the patch, with the furnace at its drop point (layouts.md, "Burner start", has the offsets, and `fac place` on the drill says `drops_into` the furnace). Coal into both. Hand-mine ore beside it into two more furnaces while it runs.
3. **Grow the iron column to 6 to 8 pairs** as plates allow (9 iron per drill), all reachable from one standing spot outside the ore. `steam-power` fires at 50 plates.
4. **Copper: 3 burner pairs.** `electronics` fires 10 plates later.
5. **Coal: 3 or 4 burner drills into chests** on the coal patch. A drill mining into a chest does not refuel itself: on each pass take the coal from the chest and put about 20 back into the drill.
6. **Loop iron, copper, coal**: take plates, refuel from the coal chests, 20 to 30 coal per burner so a round lasts 10 minutes. Queue the power and lab crafts as each trigger fires: offshore pump, boiler, steam engine, burner inserter, chest, small poles, lab, then `fac craft automation-science-pack --count 10` once the lab is crafted. Chop a few trees whenever you pass some: every 7.5 tiles of pole line costs half a wood.
7. **Power at the nearest shore**: the start of power.md at its final place, with as many boilers as you can afford (layouts.md, "First power", says which steps make a 1-boiler start). A wooden chest under the burner inserter holds its coal until the coal belt arrives; write it under `HAND`. Mine a fish while you stand there (SKILL.md) and keep it for the launch.
8. **The first lab goes at the base site, not at the shore.** The base hangs on power.md's breaker pole from the start, so that mining it cuts the load in a blackout: from S1 place the mine line poles at P + (1, +1) and P + (1, +8) and the breaker at P + (7, +8) (layouts.md, "First power"). Then lay small poles from the breaker to the base with one `fac place small-electric-pole X1,Y1 --to X2,Y2 --spacing 7 --wait`, starting at the breaker and kept more than 7.5 tiles from every other pole of the power block. Place the lab at lab 1's position of the science block, insert the 10 packs, and queue research (research.md, Q1). The 10 packs research `automation`, which the red cell's long-handed inserter needs.
9. **Red milestone at the base**, once `automation` is researched: red cell 1 of science.md at its final place (science.md, "1. Red milestone cell, before any belt"): a gear assembler, an inserter passing gears to a red assembler, a long-handed inserter lifting packs over the iron trunk's line into lab 1. Hand-feed plates into the two assemblers until the trunks arrive. Feed the gear assembler iron plates, not gears you carry: your craft queue spends carried gears on the next drill.
10. **Check it before you walk off.** `fac inspect` the lab (`working`), each inserter (`drops_into` the machine you meant, not `not_plugged_in_electric_network`), then `fac screenshot` and look for plug or fuel icons. Then `fac research`: progress moves.

Coal balance: 11 burner pairs burn about 37 coal/min and 4 coal drills make about 51. If the coal patch is far from the iron, every refuel is a round trip, so carry a lot each time and mine rocks before you hand-mine coal.

## Right after the milestone

- Queue the next research before the current one ends.
- `electric-mining-drill` comes first (25 red packs). With it, build the iron smelting column of smelting.md with its trunk running to the science block (base-plan.md), and its coal from the power block's coal belt. Then copper the same way. The red cell's two belt inserters go in when the trunks arrive. Pick the burner pairs up as electric rows replace them.
- Furnace rows end on a belt, never in chests you empty by hand. Two test runs that ended rows in chests carried 11,000 to 16,000 plates by hand and lost a quarter of their first hour to it.
- Hand-craft no science beyond the first 10 red packs.
- Smelt 50 steel as soon as `steel-processing` is done (5 furnaces with 50 iron plates each): it fires the steel axe, which doubles hand-mining speed.
- Before `demand_kw` comes within 1,800 of `capacity_kw` (one boiler is 1.8 MW, about 20 electric drills), add a boiler and its engines, and build power.md's coal mine and belt so no boiler takes coal from your hands (power.md, "Build order"; troubleshooting.md, "Symptom to cause").
