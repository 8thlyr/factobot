# Production: machines, recipes, ratios, factory sizes

Read this when you size a build or need a recipe. Numbers are Factorio 2.1.24 base game (`research/production-chains.md`). AM1 and AM2 are assembling machines 1 and 2.

## Machines

| Machine | Speed | Power | Notes |
|---|---|---|---|
| Burner mining drill (2x2) | 0.25 ore/s | 150 kW, 50 coal lasts 22 min | mines only the 2x2 under it |
| Electric mining drill (3x3) | 0.5 ore/s | 90 kW | mines 5x5 |
| Stone furnace (2x2) | 0.3125 plates/s | 90 kW, 50 coal lasts 37 min | |
| Steel furnace (2x2) | 0.625 plates/s | 90 kW | same fuel per minute, twice the plates |
| Electric furnace (3x3) | 0.625 plates/s | 180 kW | needed mainly as a purple-pack ingredient |
| AM1 / AM2 | 0.5 / 0.75 | 75 / 150 kW | only AM2 takes fluid recipes |
| Lab | 1 | 60 kW | |
| Boiler | 60 steam/s, 1.8 MW | 0.45 coal/s at full load | 1 boiler feeds 2 engines |
| Steam engine | 900 kW | | |
| Offshore pump | 1,200 water/s | none | one pump feeds 200 boilers; never build a second for power |
| Pumpjack | yield% / 10 crude/s | 90 kW | a 100% well gives 10 crude/s |
| Refinery | 1 | 420 kW | |
| Chemical plant | 1 | 210 kW | |
| Rocket silo | 1 | | 100 rocket parts, 4 module slots |
| Inserter / long / fast | 0.83 to 0.88 / about 1.2 / 2.5 items/s (measured) | | burner inserter about 0.8/s (49 coal/min) |
| Belt / fast belt | 15 / 30 items/s | | 7.5 per lane on yellow |

Character: hand-mining 2 s per ore (1 s after the steel axe), crafting speed 1, 80 slots, reach 10, running 8.9 tiles/s. The character can't craft engine units, anything with a fluid ingredient (processing units, electric engines, rocket fuel, concrete) or smelt.

## Stack sizes

100: plates, steel, gears, pipes, bricks, plastic, rails, belts, concrete, processing units. 200: circuits, advanced circuits, cables, science packs. 50: ore, coal, stone, sulfur, solid fuel, engines, electric engines, LDS, robot frames, drills, assemblers, furnaces, inserters. 20: rocket fuel, pumpjacks, offshore pumps. 10: labs, refineries, chemical plants, steam engines.

## Recipes on the rocket path

Time is at speed 1.

| Recipe | s | Ingredients | Output | Where |
|---|---|---|---|---|
| iron/copper plate | 3.2 | 1 ore | 1 | furnace |
| steel plate | 16 | 5 iron plate | 1 | furnace |
| stone brick | 3.2 | 2 stone | 1 | furnace |
| iron gear | 0.5 | 2 iron | 1 | hand, AM |
| copper cable | 0.5 | 1 copper | 2 | hand, AM |
| electronic circuit | 0.5 | 1 iron, 3 cable | 1 | hand, AM |
| inserter | 0.5 | 1 circuit, 1 gear, 1 iron | 1 | hand, AM |
| transport belt | 0.5 | 1 gear, 1 iron | 2 | hand, AM |
| pipe | 0.5 | 1 iron | 1 | hand, AM |
| engine unit | 10 | 1 steel, 1 gear, 2 pipe | 1 | AM only |
| plastic bar | 1 | 20 petroleum, 1 coal | 2 | chemical plant |
| sulfur | 1 | 30 water, 30 petroleum | 2 | chemical plant |
| sulfuric acid | 1 | 5 sulfur, 1 iron, 100 water | 50 | chemical plant |
| advanced circuit | 6 | 2 circuit, 2 plastic, 4 cable | 1 | hand, AM |
| processing unit | 10 | 20 circuit, 2 advanced circuit, 5 acid | 1 | AM2 |
| battery | 4 | 20 acid, 1 iron, 1 copper | 1 | chemical plant |
| lubricant | 1 | 10 heavy oil | 10 | chemical plant |
| electric engine | 10 | 1 engine, 15 lubricant, 2 circuit | 1 | AM2 |
| flying robot frame | 20 | 1 electric engine, 2 battery, 1 steel, 3 circuit | 1 | hand, AM |
| low density structure (LDS) | 15 | 2 steel, 20 copper, 5 plastic | 1 | hand, AM |
| solid fuel (from light oil) | 1 | 10 light oil | 1 | chemical plant |
| rocket fuel | 15 | 10 solid fuel, 10 light oil | 1 | AM2 |
| concrete | 10 | 5 brick, 1 iron ore, 100 water | 10 | AM2 |
| productivity module 1 / 2 / 3 | 15 / 30 / 60 | 5 AC + 5 circuit / 4 prod1 + 5 AC + 5 PU / 4 prod2 + 5 AC + 5 PU | 1 | hand, AM |
| electric furnace | 5 | 10 steel, 5 AC, 10 brick | 1 | hand, AM |
| rail | 0.5 | 1 stone, 1 iron stick, 1 steel | 2 | hand, AM |
| red pack | 5 | 1 copper, 1 gear | 1 | |
| green pack | 6 | 1 inserter, 1 belt | 1 | |
| blue pack | 24 | 2 engine, 3 AC, 1 sulfur | 2 | |
| purple pack | 21 | 1 electric furnace, 1 prod module 1, 30 rail | 3 | |
| yellow pack | 21 | 3 LDS, 2 processing unit, 1 robot frame | 3 | |
| rocket part | 3 | 10 processing unit, 10 LDS, 10 rocket fuel | 1 | silo |
| rocket silo | 30 | 1000 steel, 1000 concrete, 100 pipe, 200 processing unit, 200 electric engine | 1 | hand |

## Per 1 pack per second

AM2 throughout (multiply by 1.5 for AM1). Stone furnaces (halve for steel furnaces). Electric drills.

| Pack | AM2 | Furnaces | Chem plants | Refineries | Drills | Iron ore/s | Copper ore/s | Power MW |
|---|---|---|---|---|---|---|---|---|
| Red | 7.3 | 9.6 | 0 | 0 | 6.4 | 2.0 | 1.0 | 1.7 |
| Green | 11.7 | 22.4 | 0 | 0 | 15 | 5.5 | 1.5 | 3.1 |
| Blue | 50 | 78 | 3.9 | 1.9 | 46 | 12 | 7.5 | 13.6 |
| Purple | 68 | 373 | 7.1 | 3.4 | 190 | 52.5 | 19.2 | 30.9 |
| Yellow | 98 | 309 | 13.5 | 5.3 | 188 | 33.3 | 49.8 | 37.7 |

Simple cells: one AM1 gear machine feeds 10 AM1 red machines. One AM1 red machine makes 0.1 red/s; one AM1 green machine 0.083 green/s. Three cable machines feed two circuit machines. Steel: one stone furnace of iron feeds one stone furnace of steel.

## Planned factory sizes

Size each stage before you build it, and count again before a long technology depends on it. Every machine costs you 4 to 8 commands with its inserters and poles, so these are deliberately small, but a pack line smaller than this makes the research it feeds take hours: one AM2 makes 3.75 blue, 6.4 purple or 6.4 yellow packs a minute. Counts are the whole factory at that stage, AM2 unless noted, steel furnaces unless noted; only the last row's (+) counts add to the row above it.

| Stage | Target | Machines | Drills | Oil | Labs | Power |
|---|---|---|---|---|---|---|
| Red and green | 0.3 red, 0.5 green/s | the science block (science.md): 20 AM1, 6 of them AM2 later for 0.3 red and 0.5 green/s; one smelting column per plate (smelting.md): 24 stone furnaces each, iron 3.4 to 5.1 plates/s, copper 1.1 or more | 15 per column | none | 16 | science up to 2.7 MW plus 1.55 MW per smelting column: 4 boilers, 8 engines (power.md) |
| Blue | red and green 0.5/s, blue 0.25/s | 22 (4 blue, 4 engine, 3 advanced circuit, 3 red, 4 green, cable), 18 furnaces (2 for steel), 1 to 2 chemical plants | about 21 iron and copper | 2 refineries, pumpjacks for 40 crude/s | 16 | 4 boilers, 8 engines |
| Purple and yellow | all five at 0.25/s | 59 in total, 99 furnaces in total, 6 chemical plants in total | about 107 in total | 3 refineries, 5 to 6 pumpjacks at 100% | 16 to 24 | 13 boilers, 25 engines |
| Rocket parts | 100 parts over about 1.8 h | +18 (3 LDS, 3 rocket fuel, 2 processing unit), +26 furnaces, +3 chemical plants (solid fuel) | +32 | +1.4 refineries, +3 pumpjacks at 100% | | +4 boilers, +8 engines |

Production is back-loaded: purple, yellow and the rocket need most of the plates. Build the last third of mining while blue runs. Lower-tier machines carry over, so the red and green line keeps serving later stages.

Delivery, not mining, limits every stage. In a test run the first hour placed 68 electric drills and 79 stone furnaces, several times the first row above, yet red and green each averaged about 0.2/s, because every plate reached the assemblers in the character's inventory. Connect what you have by belt before you add more of it.

## Oil

| Process (refinery speed 1) | Per refinery per second |
|---|---|
| Basic | 20 crude to 9 petroleum |
| Advanced | 20 crude + 10 water to 5 heavy + 9 light + 11 petroleum |
| Heavy cracking (chemical plant) | 20 heavy + 15 water to 15 light |
| Light cracking (chemical plant) | 15 light + 15 water to 10 petroleum |

- Start with basic processing: one input, one output, nothing backs up. Switch each refinery to `advanced-oil-processing` with `fac recipe` once that technology is researched (Q6 in research.md, well after the first blue packs): 2.17 times the petroleum, and the only source of light oil (rocket fuel) and heavy oil (lubricant).
- Advanced processing stops when any output backs up. Give heavy oil, light oil and petroleum each a sink: cracking, solid fuel, lubricant or a storage tank.
- All petroleum: refinery : heavy cracking : light cracking about 8 : 2 : 7.
- Rocket fuel takes 110 light oil each (10 solid fuel from light oil plus 10 light oil). Make solid fuel from light oil, not petroleum.
- The whole run needs about 530k crude: about 7 pumpjacks at 100% over a 2 h oil phase.

## Power

- Boiler at full load burns 0.45 coal/s; one stack lasts 111 s. Boilers get their coal from a belt through burner inserters (power.md), never from your hands past the first lab.
- The whole run burns about 58k coal in boilers and 20k in furnaces.
- Coal per minute: a stone or steel furnace 1.35, a burner drill 2.25, a boiler up to 27. An electric drill on coal makes 30, enough for 22 stone furnaces; boilers need 1.5 coal drills each (3 per 2, power.md), and 80 stone furnaces 4 electric coal drills more.
- Load: an electric drill draws 90 kW, an AM1 75 kW, an AM2 150 kW, a lab 60 kW, an inserter about 13 kW. 70 electric drills alone are 6.3 MW, three and a half boilers. Add boilers and engines before the load gets there; a brown-out slows every machine at once.
- Solar is never worth building: about 44 placements per MW against about 2 for steam.

## Rocket

- Put 4 productivity module 3 in the silo: +40% productivity, so 72 crafts make 100 parts instead of 100 crafts. That saves about 280 each of processing units, LDS and rocket fuel. The silo then takes 7.5 s per craft, 9 min in total.
- With prod 3s you need about 720 each of processing units, LDS and rocket fuel. 720 rocket fuel is 36 slots.
- 4 prod 3 = 16 prod 2 = 64 prod 1, plus 420 advanced circuits, 100 processing units and 320 circuits in total.
- The silo recipe is a hand-craft: stage 1000 steel, 1000 concrete (100 concrete crafts from 500 bricks and 100 iron ore in an AM2 with water), 100 pipes, 200 processing units and 200 electric engines in chests ahead of time.
- The payload is 1 raw fish. No satellite and no cargo landing pad are needed.
