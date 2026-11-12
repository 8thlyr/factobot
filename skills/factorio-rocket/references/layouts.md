# Layouts: fac rules and the tested blocks

Read this before building a block. The tested blocks are in their own files ("The tested blocks" below); this file holds the rules they share and the small layouts of the burner start. Every position is an offset (dx, dy) from an anchor you choose on your map, x east and y south, as `fac place` takes entity centers: 1x1, 3x3 and 5x5 entities center on `.5`, 2x2 entities (furnaces, burner drills) on whole numbers. Add the offsets to your anchor and write the anchor into `notes.md`. "Tested" means built with `fac` in a factobot test world, run for several game minutes and checked with `fac inspect`, `fac observe` and a screenshot; anything else follows fac's direction rules but has not been built, so check it as you go. The drawings show belts running east; to turn a block, turn every offset and every direction the same way, then check `drops_into` and `picks_from` on what you place, since only the drawn orientation was tested unless a section says otherwise.

## Directions in fac

| Entity | `--direction D` means |
|---|---|
| Transport belt | items flow toward D; which lane things land on is in belts.md |
| Inserter (all kinds) | picks up from the D side, drops on the opposite side |
| Burner or electric drill | output chute faces D |
| Offshore pump | D points at the water; a rejection names the nearest spot and direction that fit |
| Boiler | steam leaves on the D side; water enters and passes through on the two short ends |
| Steam engine | joins on its two short ends; north equals south, east equals west |
| Pipe-to-ground | the pipe end faces D, the underground end the opposite way. A pair joins when its two pieces stand in one row, at most 10 tiles apart (9 tiles between), facing away from each other: for a line running east the first piece faces west and the second east. `fac place` shows `paired_with` once the two ends join, and warns "its underground end joins nothing yet" while a piece has no partner. `--to` does not lay pipe-to-ground: place each end (oil.md, "Long pipes: pipe-to-ground") |
| Underground belt | both pieces face the way items travel; the entrance comes first, then the exit with `--belt-type output`, at most 4 tiles between for yellow |
| Refinery, chemical plant, pumpjack, assembling machine 2 with a fluid recipe | fluid ports rotate with D; read `ports` after `fac recipe` (oil.md, "1. Fluid ports"). An assembling machine 2 faces north until it has a fluid recipe: set the recipe, then `fac rotate` |
| Furnace, chest, lab, pole, pipe, assembling machine 1 | direction has no effect |

`fac rotate` turns a quarter turn clockwise; twice reverses an inserter or belt. Rotating a belt picks up the items on it.

Placing a faster building on a slower one of the same size (an assembling machine 2 on an assembling machine 1) swaps it in place: the answer shows `replaced`, the new building keeps the recipe and contents, the old one goes to your inventory, and the inserters around it name the new building at once (science.md, "12. Assembling machine 2"; smelting.md, "Variants measured").

Drop points: a burner drill facing east at (x, y) drops into a 2x2 furnace at (x + 2, y); north (x, y - 2), south (x, y + 2), west (x - 2, y). An electric drill facing north at (x.5, y.5) drops at (x.5, y - 1.35). A drill also drops straight onto a belt or into a chest. `drops_into` names the building or belt lane a drill or inserter feeds, even before it has power or fuel; `drops_at` means nothing is at the drop point, so fix it before moving on.

Reach: build and interact reach are 10 tiles to the entity's edge, so pick a standing spot outside the block and place everything from there. `fac walk` stops up to 1 tile short of its target, so pick spots 9 tiles or less from everything you place. Small poles connect up to 7.5 tiles apart and power anything whose edge is within 2.5 tiles of the pole; medium 9 and 3.5; big 32 and 2.

## The tested blocks

Each block was built with `fac` in a test world, run for several game minutes and measured. Its file is the authority for its layout and its numbers: build it from that file, and only in the orientation it was tested in unless you turn every offset and direction yourself and check `drops_into`, `picks_from` and `ports` as you go.

| File | Gives | Inputs | Outputs | Anchor | Tested orientation |
|---|---|---|---|---|---|
| [power.md](power.md) | steam power: boilers in pairs with 2 engines each (1.8 MW a boiler), a coal mine of electric drills, burner inserters off one coal belt, a breaker pole, blackout recovery | a shore for the offshore pump; a coal patch for the mine | power through the breaker pole P + (7, +8); surplus coal east on the coal belt at P + (x, +2) | P, the offshore pump's centre; M, the mine belt's east tile | water west, coal belt running east, boilers and engines facing north |
| [smelting.md](smelting.md) | a column of 24 stone furnaces on one ore belt with coal on its other lane: 7.5 plates/s from 15 electric drills; steel and brick variants | ore under the drill row; the power block's coal belt, arriving from the south at A + (-1.5, 2.5) | plates on both lanes of the trunk at A + (x, 5.5), running east | A, the north-west corner of the ore-belt tile in front of the first input inserter | belts east, drills north of the ore belt, trunk south of the block |
| [science.md](science.md) | red and green science, 16 labs on one chain, a mall of five chests, the entry for blue, purple and yellow at lab 1 | iron trunk at dy 0 and copper trunk at dy 6, both from the west; blue, purple and yellow on belts A and B from the north at dx -3 and -1 | research; gears, circuits, inserters, belts and pipes in the mall chests | the iron trunk tile where the block starts | trunks running east, labs north of the iron trunk |
| [oil.md](oil.md) | fluid port tables for every machine and direction; the basic oil site (plastic and sulfur on one belt), the advanced site with cracking, lubricant, acid and solid fuel; long pipe-to-ground lines; a battery block | 4 wells at 100%; water at R1 + (-26, 6); coal (and iron for acid) on the coal belt at R1 + (-9, -25) | sulfur (left lane) and plastic (right lane) at the output belt's east end, R1 + (38, -24); solid fuel at R1 + (38, -25); lubricant and acid in tanks; batteries from the battery block | R1, the first refinery's centre; B, the first battery plant's centre | refineries facing north, chemical plants facing south, product belts running east |

## First power: the 2-boiler start of power.md

Build the first power plant as the start of power.md at its final place, with as many boilers as you can afford: the 2-boiler start is 11 placements (pump, 2 boilers, 4 engines, 2 burner inserters, 2 poles). For a 1-boiler start, take only boiler 1 from power.md's "Build order": the pump; from S1 the boiler at (2.5, 0), its burner inserter at (2.5, 1.5) and the first engine at (2.5, -3.5); from N the second engine at (2.5, -8.5) and the pole at (0.5, -5.5). Boiler 2 and its two engines and the pole at (7.5, -5.5) follow from the same spots when you have them.

Then the breaker, from S1 (power.md, "Breaker and load"): the mine line poles at (1.5, 1.5) and (1.5, 8.5) and the breaker pole at (7.5, 8.5). The pole line to the base starts at the breaker and nowhere else, so that mining the breaker cuts the factory off in a blackout.

Until the coal belt and the mine of power.md arrive, the burner inserter may take its coal from a wooden chest on the belt tile under it (P + (2, +2)). Fill it by hand, write it under `HAND` in your notes, and mine the chest when you lay the coal belt. Put 5 coal into the boiler to start it ("First start" in power.md).

## First red cell: red cell 1 of science.md

The milestone red cell is red cell 1 of science.md, built by "1. Red milestone cell, before any belt" at its final position, with the science block's anchor on the iron trunk's planned line (base-plan.md). Choose that anchor in phase 1. Its lab is lab 1 of the chain. You hand-feed the two assemblers until the trunks arrive; then two inserters go into the free tiles and nothing moves.

## Burner start (phase 2 only)

These need your hands, so they are for the first half hour and come down when the electric rows run.

**Burner drill into furnace (tested).** Drill at (x, y) facing east, stone furnace at (x + 2, y). Repeat every 2 tiles in y for a column, and add a second column 4 tiles west. 0.25 plates/s a pair. Take the plates every 6 minutes or the furnace stalls at 100.

**Coal drill into a chest (tested).** Burner drill facing north at (x, y) into a wooden chest at (x - 0.5, y - 1.5), or facing east into a chest at (x + 1.5, y - 0.5). Nets 0.21 coal/s; refuel the drill from its own chest on each pass.

**Coal pair.** Two burner drills fully on coal facing each other, one at (x, y) facing east and one at (x + 2, y) facing west, fuel each other and stop when both hold 50 coal. `fac take X,Y coal` from each.

## Inserter habits

- An inserter takes only what its target uses and tops a machine up to about 2 crafts of input; chests fill completely.
- An inserter moves about 0.83 to 0.88 items/s (measured in the blocks), a long-handed one about 1.2, a burner inserter about 0.8 (49 coal/min), a fast one about 2.5. A machine that needs more gets a second inserter.
- An inserter puts items on the far lane of a belt it faces across, so a row of inserters fills one lane (7.5/s). belts.md has every lane rule.
- A long-handed inserter picks up 2 tiles away and drops 2 tiles away on the other side, so it reaches over a belt.
- One item per inserter where it matters: an inserter taking from a chest that holds two items delivers the first until its lane is full, and the second never arrives.
- The inserters that feed boilers are burner inserters, or a blackout never recovers.
