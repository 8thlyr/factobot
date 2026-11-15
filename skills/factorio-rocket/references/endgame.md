# Oil to launch

Read this when you start the oil phase, and again before blue, purple, yellow and the silo. Recipes and ratios are in production.md, fluid ports and the tested oil site in oil.md, where each block goes in base-plan.md.

The second half of the game is where the test runs came apart, and never because a recipe was unknown. They fed plastic, sulfur, coal and packs by hand, and each of those ran dry while the agent was busy. Everything below is built so that it runs without you: plan each block's inputs and outputs as belts and pipes before you place its first machine, and write them into `notes.md`.

## Oil

`oil-processing` is a trigger technology: it finishes only when a powered pumpjack extracts crude. Until `fac research oil-processing --show` says researched, nothing that needs it can be queued.

1. Find the oil: `fac map` lists `crude-oil` once you have walked near it. If none shows, walk out in the directions the map has not explored yet, 300 to 500 tiles at a time. `fac inspect` on a well shows its amount; a 100% well gives 10 crude/s.
2. Choose the oil site: at the field if water is near, else at the nearest water on the way to the base, with the crude piped there underground (oil.md, "Long pipes: pipe-to-ground"; a pipe segment may span at most 320 tiles, so put a powered pump at least every 300). Refineries need water for advanced processing and the sulfur plant needs it from the start.
3. Power reaches the field on poles from the base grid: big poles once `electric-energy-distribution-1` is researched (30 tiles apart, one `fac place big-electric-pole X1,Y1 --to X2,Y2 --spacing 30` per straight run), with small or medium poles at each pumpjack, since a big pole supplies only 2 tiles around itself. Check `power` on a pole before and after: the tested basic site (4 pumpjacks, 2 refineries, 2 chemical plants) draws 976 kW and the advanced site 1,572 kW (oil.md, "6. Rates, extending, limits and failure").
4. Hard check, standing within 32 tiles of a pumpjack: `fac inspect` shows `working` and `crude-oil` in `fluids`. `not_plugged_in_electric_network` is the pole line; `no_power` is the grid. When it passes, `oil-processing` is researched: queue Q4.
5. Build the tested basic site (oil.md, "4. Build order", "Basic site"; it makes 42 to 46 plastic and 42 to 44 sulfur a minute) and lay its output belt to the base. Coal for the plastic plant comes on a belt lane, not from a chest you fill.
6. Every fluid product needs a sink, or the refinery stops at `full_output`. With basic processing the sinks are the plastic and sulfur plants; a storage tank on the petroleum line buys time when their belt backs up.
7. Before you leave the site: `fac observe --problems` shows nothing, `fac stats plastic-bar sulfur` shows both made in the last minute, and a screenshot shows both on the belt. At the base: both arrive.

When `advanced-oil-processing` is researched (Q6, with `lubricant`), change the site as oil.md's "Advanced site, as a change" shows: sinks first, the refinery recipes last. Check every plant's consumers before you change its recipe: build a new plant for a new product instead of switching the only plant that makes an old one.

## Blue (chemical science)

Two packs per craft from 2 engines, 3 advanced circuits and 1 sulfur, 24 s. One assembling machine 2 makes 3.75 packs a minute, so 0.25 packs/s is 4 blue assemblers, with 4 engine assemblers and 3 advanced circuit assemblers behind them.

- Engines (1 steel, 1 gear, 2 pipes, 10 s) are made only in assemblers: steel from the steel column, gears and pipes from assemblers on the iron trunk.
- Advanced circuits need plastic, circuits and cable: plastic from the oil site's belt, circuits and cable made beside them from the trunks.
- Sulfur comes on the same belt as the plastic, on the other lane.
- Packs leave on a belt to lab one's entry (science.md, "10. Pack entry at lab 1": blue on belt A's left lane).

Start building once `chemical-science-pack` is queued and plastic and sulfur arrive at the base. Exit check: all blue assemblers `working`, `fac stats chemical-science-pack` steady over 10 minutes, blue in the last lab of the chain.

## Purple (production science)

Three packs per craft from 1 electric furnace, 1 productivity module 1 and 30 rails, 21 s. One assembling machine 2 makes 6.4 packs a minute; research needs 1,600 purple packs, so build 3 or 4 purple assemblers, not one.

- Rails: stone, iron sticks and steel. Purple costs about 8 steel a pack, so it needs its own steel column and a stone drill row with its own belt.
- Electric furnaces: steel, advanced circuits and stone bricks (a furnace column fed stone).
- Productivity module 1: advanced circuits and circuits.
- Feed each purple assembler by direct insertion from the assemblers that make its three ingredients where you can, and by belt where you can't. No chest you fill.

Queue a purple technology as soon as the first purple pack reaches a lab. Purple before yellow, so that `productivity-module-3` and `speed-module-3` research while you build yellow.

## Yellow (utility science)

Three packs per craft from 3 low density structures, 2 processing units and 1 flying robot frame, 21 s; one assembling machine 2 makes 6.4 packs a minute. Research needs 1,000 yellow packs and the rocket 720 each of processing units and low density structures on top: build 3 yellow assemblers, 3 robot frame assemblers, 3 electric engine assemblers (the frames take 6.4 engines a minute and the silo 200 more), and processing units and low density structures from the two tested blocks, which make the packs' share and the rocket's.

- Processing unit: 20 circuits, 2 advanced circuits, 5 sulfuric acid, 10 s, assembling machine 2 only. Build the processing unit block of processing-units.md (18 a minute) as soon as `processing-unit` is researched, with acid by pipe from the acid plant. Behind its 4 processing unit assemblers stand 22 that make the circuits and cable; fewer, or basic inserters on the cable, and the line makes a third of that.
- Low density structure: 2 steel, 20 copper, 5 plastic, 15 s: the LDS row of processing-units.md (18 a minute).
- Flying robot frame: 1 electric engine, 2 batteries, 1 steel, 3 circuits. Electric engines need lubricant (a fluid, from heavy oil), batteries need acid. Make electric engines and batteries at the oil site and belt them to the base.

The two blocks need 18 copper plates/s between them and 165 plastic a minute, more than the factory had for blue and purple: build the smelting columns and the oil they need first (processing-units.md, "Feeding it"). Exit check: `fac stats utility-science-pack processing-unit low-density-structure` shows `made_10m` 15 or more for each.

## Rocket inputs, built while `rocket-silo` researches

`rocket-silo` is 1,000 units of 60 s with all five packs. 16 labs at research speed 1.5 can use 0.4 packs/s of each (24 a minute), so the pack lines set the pace. Queue it as soon as yellow is in the labs; its finish time is the check. Ten minutes after it starts, `fac research` must show `minutes_left` 70 or less: at 15 yellow packs a minute it takes 67 minutes. A larger one means the pack in `short_of` is short: build that line's next capacity now and never wait it out (two test runs waited, and it took them 2 h 48 min and 3 h 13 min at 3 to 8 yellow packs a minute). Then use the hours it takes:

- 100 rocket parts take 1,000 each of processing units, low density structures and rocket fuel, or about 720 each with 4 productivity module 3 in the silo. Rocket fuel: solid fuel from light oil in chemical plants, then 10 solid fuel and 10 light oil per rocket fuel in an assembling machine 2 at the oil site, 15 s, onto a belt. 720 between 4:30 and 6:05 (SKILL.md, Phases) is about 8 a minute: 3 rocket fuel assemblers (3 a minute each), and 80 solid fuel a minute from 3 solid fuel plants with the light oil for them (the tested plant makes 32 to 34 a minute, oil.md).
- Send the three to chests beside the silo site by belt and inserter, so they stockpile while the research runs (processing-units.md, "Outputs"). 720 rocket fuel is 36 stacks of 20: a steel chest (48 slots), not an iron one (32). `fac stats processing-unit low-density-structure rocket-fuel` in every factory check.
- 4 productivity module 3 (from 16 productivity module 2, from 64 productivity module 1: 420 advanced circuits, 100 processing units and 320 circuits in all), hand-crafted or from a module assembler.
- The silo itself is a hand-craft from 1,000 steel, 1,000 concrete, 100 pipes, 200 processing units and 200 electric engines. Concrete: 5 bricks, 1 iron ore and 100 water make 10, in an assembling machine 2 at water. Stock the 1,000 steel and 1,000 concrete before you queue `rocket-silo`, by inserter, never off belts by hand. Steel: an inserter at the end of the steel belt into a chest, so it gets only what nothing upstream takes. Concrete: its assembling machine 2 fed bricks from a brick furnace row on a stone belt (smelting.md) and iron ore from an ore belt. A test run took its silo steel off belts after the research and waited 17 minutes for it.
- 1 raw fish. Take it at the first power plant and keep it.

## Silo and launch

1. Hand-craft `rocket-silo` and place it (9x9) where the three ingredient chests can reach it through fast inserters, one chest and one inserter per ingredient.
2. Insert the 4 productivity module 3 first, before any ingredient reaches it (place the inserters after the modules).
3. The silo holds at most 104 processing units, 54 low density structures and 24 rocket fuel, and each part takes 10 of each, so only inserters keep it fed. With the modules a part takes 7.5 s and 72 crafts make the 100 parts: about 9 minutes when the chests are full.
4. Insert the fish as the payload; it can go in while parts build.
5. `fac inspect` the silo: its `rocket` field shows status, parts and the payload. When it says `rocket_ready`, `fac launch`. A rejected launch names the reason (parts still building, still rising, no payload): fix that one thing and launch again.
