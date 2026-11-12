# Oil site: plastic and sulfur on one belt, then advanced oil with cracking (tested)

Four pumpjacks on 100% wells feed two oil refineries through a crude row. On basic oil processing the refineries make 18 petroleum/s (1,080/min). A plastic plant takes coal by inserter off a coal belt, a sulfur plant takes water from a water header, and both drop onto ONE output belt that leaves the block to the east: sulfur on the left (north) lane, plastic on the right (south) lane. Measured: 42 to 46 plastic/min and 42 to 44 sulfur/min, 976 kW for the whole site.

The advanced site is a change to the basic one. It switches the refineries to advanced processing with water and adds 1 heavy-oil cracker, 2 light-oil crackers, a storage tank on each fluid, a lubricant plant, a sulfuric acid plant and a solid fuel plant whose solid fuel leaves on its own belt. Measured: 78 to 92 plastic/min, 78 to 93 sulfur/min (60 to 70 of it into the acid plant), 32 to 34 solid fuel/min, 255 to 270 lubricant/min and 570 to 650 sulfuric acid/min, at 1,572 kW. When nothing takes the lubricant or the solid fuel, the refineries keep `working` and plastic and sulfur rise to 92 and 93/min. A 2-plant battery block fed by a 66-tile pipe-to-ground acid line makes 30 batteries/min. Placements: about 45 `fac place` calls for the basic site (pipe and belt runs count as one call each) and about 75 more for the advanced change.

Measured on Factorio 2.1.24. Tested orientation: refineries facing north with the crude row south of them, all chemical plants facing south (one lubricant plant facing west), product belts running east. Other orientations of the whole site are untested; the port tables below cover every direction of each machine.

## 1. Fluid ports

### The procedure for every machine with pipes

`ports` in the answer is the authority. The offset tables further down are only for choosing a facing before you place.

1. `fac place` the machine with its `--direction`.
2. `fac recipe` it. The ports change with the recipe: a refinery has 5 ports with no recipe, 2 on basic oil, 5 on advanced.
3. Read `ports` in the `fac recipe` answer. Each entry has `flow` (`input`, `output`), `fluid` and `pipe_at`, the tile a pipe must stand on.
4. Lay a pipe, pipe-to-ground end or header tile on each `pipe_at` you need.
5. `fac inspect` the machine and read `ports` again. Every fluid of the recipe must have a port with `joined_to` and no `problem`. Ports of the same fluid share one box, so one joined port per fluid is enough. `joined_to.fluid` is what the joined pipe holds; `problem` appears when that is another fluid than the port's.

A pumpjack's port has no recipe; its `fluid` names the well's fluid.

An assembling machine 2 placed with `--direction` before a fluid recipe is set stays facing north. Set the recipe, then `fac rotate` until the `pipe_at` is your pipe, then read `ports`.

### Planning rule

Offsets are from the machine centre, x east, y south, and name the tile the pipe stands on. Turning the machine a quarter turn clockwise (`--direction` north, east, south, west, or one `fac rotate`) turns every offset (dx, dy) into (-dy, dx). This matches `ports` for all 52 combinations below (4 directions of 2 refinery recipes, 7 chemical plant recipes, 4 AM2 recipes) and for the pumpjack in every direction.

To remember it without the table:

- A chemical plant and an assembling machine 2 face their inputs. Facing north, the inputs are on the north side and the outputs on the south side.
- A refinery and a pumpjack face their outputs. Facing north, the refinery's outputs are on the north side and its inputs on the south side, and the pumpjack's output is on the north side.
- With two input fluids, the water goes on the left input as you look the way the machine faces, the oil on the right (a chemical plant facing north takes water at (-1, -2) and oil at (+1, -2); a refinery facing north takes water at (-1, +3) and crude at (+1, +3)).
- In a chemical plant, a recipe with one input fluid, or one output fluid, joins both of its tiles into one fluid box: one pipe on either tile is enough. A refinery does not: each of its fluids has exactly one tile, so basic oil takes crude only on (+1, +3) and gives petroleum only on (+2, -3), facing north.
- Basic and advanced oil share the crude tile (+1, +3) and the petroleum tile (+2, -3), facing north. Switching a refinery from basic to advanced only adds water at (-1, +3), heavy oil at (-2, -3) and light oil at (0, -3).

### Port table, facing north

Rotate with (dx, dy) to (-dy, dx) per quarter turn clockwise. "or" means both tiles reach one box.

| Machine, recipe | Inputs (pipe tile) | Outputs (pipe tile) |
|---|---|---|
| pumpjack | | crude (+1, -2) |
| oil refinery, no recipe | (-1, +3), (+1, +3) | (-2, -3), (0, -3), (+2, -3) |
| oil refinery, `basic-oil-processing` | crude (+1, +3) | petroleum (+2, -3) |
| oil refinery, `advanced-oil-processing` | water (-1, +3), crude (+1, +3) | heavy (-2, -3), light (0, -3), petroleum (+2, -3) |
| chemical plant, no recipe | (-1, -2), (+1, -2) | (-1, +2), (+1, +2) |
| chemical plant, `plastic-bar` | petroleum (-1, -2) or (+1, -2) | |
| chemical plant, `sulfur` | water (-1, -2), petroleum (+1, -2) | |
| chemical plant, `sulfuric-acid` | water (-1, -2) or (+1, -2) | acid (-1, +2) or (+1, +2) |
| chemical plant, `lubricant` | heavy (-1, -2) or (+1, -2) | lubricant (-1, +2) or (+1, +2) |
| chemical plant, `heavy-oil-cracking` | water (-1, -2), heavy (+1, -2) | light (-1, +2) or (+1, +2) |
| chemical plant, `light-oil-cracking` | water (-1, -2), light (+1, -2) | petroleum (-1, +2) or (+1, +2) |
| chemical plant, `solid-fuel-from-light-oil` | light (-1, -2) or (+1, -2) | |
| AM2, `electric-engine-unit` / `processing-unit` / `rocket-fuel` / `concrete` | lubricant / sulfuric acid / light oil / water at (0, -2) | |
| AM2 with no recipe or an item recipe | no fluid box, and it can't face any way but north | |

### Every direction

| Machine, recipe | north | east | south | west |
|---|---|---|---|---|
| pumpjack, crude out | (+1, -2) | (+2, +1) | (-1, +2) | (-2, -1) |
| refinery basic, crude in | (+1, +3) | (-3, +1) | (-1, -3) | (+3, -1) |
| refinery basic, petroleum out | (+2, -3) | (+3, +2) | (-2, +3) | (-3, -2) |
| refinery advanced, water in | (-1, +3) | (-3, -1) | (+1, -3) | (+3, +1) |
| refinery advanced, crude in | (+1, +3) | (-3, +1) | (-1, -3) | (+3, -1) |
| refinery advanced, heavy out | (-2, -3) | (+3, -2) | (+2, +3) | (-3, +2) |
| refinery advanced, light out | (0, -3) | (+3, 0) | (0, +3) | (-3, 0) |
| refinery advanced, petroleum out | (+2, -3) | (+3, +2) | (-2, +3) | (-3, -2) |
| chemical plant, input 1 (water for sulfur and both crackings) | (-1, -2) | (+2, -1) | (+1, +2) | (-2, +1) |
| chemical plant, input 2 (petroleum for sulfur, heavy or light for cracking) | (+1, -2) | (+2, +1) | (-1, +2) | (-2, -1) |
| chemical plant, single input (plastic, acid, lubricant, solid fuel): either of | (-1, -2), (+1, -2) | (+2, -1), (+2, +1) | (+1, +2), (-1, +2) | (-2, +1), (-2, -1) |
| chemical plant, output (acid, lubricant, cracking): either of | (-1, +2), (+1, +2) | (-2, -1), (-2, +1) | (+1, -2), (-1, -2) | (+2, +1), (+2, -1) |
| AM2 fluid input (all four recipes) | (0, -2) | (+2, 0) | (0, +2) | (-2, 0) |

### What wrong piping looks like

The status alone does not tell you a facing is wrong: a refinery with an unpiped output says `working` for its first crafts, and a pumpjack with no pipe says `working`. Read `ports`.

| Case | `fac inspect` | `ports` |
|---|---|---|
| Refinery north, basic, crude on (+1, +3), petroleum on (+2, -3) | `working`, `fluids` crude 400, `pipes_to` both pipes | both entries have `joined_to` |
| Refinery east, crude pipe on the north-facing tile (+1, +3) | `fluid_ingredient_shortage`, `missing` crude-oil 100, `fluids: []`, `pipes_to: []` | crude entry `pipe_at` (-3, +1), no `joined_to` |
| Refinery south, basic, crude right, petroleum pipe on (0, +3) (the light oil port of advanced) | `fac recipe` answers `working`, `pipes_to` only the crude pipe; about 20 s later `full_output` with petroleum 135 inside | petroleum entry `pipe_at` (-2, +3), no `joined_to` |
| Sulfur plant east, water and petroleum pipes swapped | `fluid_ingredient_shortage`, `missing` water 30 and petroleum-gas 30, `fluids: []`, `pipes_to` both pipes | both entries joined; each `joined_to.fluid` is the other fluid, and each has a `problem` |
| Sulfur plant south, one petroleum header touching both input tiles | `fluid_ingredient_shortage`, `missing` water 30, `fluids` petroleum 120, `pipes_to` two header pipes | water entry joined to a header pipe with `joined_to.fluid` petroleum-gas, and a `problem` |
| Sulfur plant north, right | `working`, `fluids` petroleum 120 and water 120 | both joined |
| Plastic plant south, one pipe-to-ground on (-1, +2), nothing on (+1, +2) | `working` | one of the two petroleum entries joined, the other not: correct, they are one box |
| Pumpjack east, pipe on the north-facing tile | `working`, `fluids` crude 50 and rising, `pipes_to: []`; after about 20 s `waiting_for_space_in_destination` with crude 509 | the entry has no `joined_to` |
| AM2 placed with `--direction east`, no recipe | the answer has no `direction`; after `fac recipe ... processing-unit` it says `direction: north` | acid `pipe_at` (0, -2). `fac rotate` once gives (+2, 0) |

## 2. Diagram

Anchor @ = centre of refinery R1, offset (0, 0). Each character is one tile, x from -26 (left edge) to +39, y from -30 (top) to +7; the digit row over the map gives |x| mod 10. Belts run east (`>`), the output belt's first tiles run north (`^`).

```
      654321098765432109876543210123456789012345678901234567890123456789
  -30 .....................................TTT..........................   acid tank T at (12,-30)
  -29 .....................................TTTu.........uu.........uu...   acid line east (pipe-to-ground pairs)
  -28 .......................................=..........................
  -27 .................#.....................=......................P.#.
  -26 .................f.....................u........................f.
  -25 ................>>>>>>>>>>>>>>>>>>>>>>.....>>>>>>>>>>>>>>>>>>>>>>.   coal+iron belt (x -10..11), solid fuel belt (x 17..38)
  -24 .................f.............>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>.   OUTPUT belt: sulfur left lane, plastic right lane
  -23 .................#.P......P.l.P^....Pliu..Pl....P.....P......Pfff.
  -22 ...........................ccc.^.ccc.ccc.ccc..................###.   where the base takes plastic and sulfur
  -21 ...........................cpcf^fcsc.cac.cfc......................   p plastic, s sulfur, a acid, f solid fuel
  -20 ...........................ccc...ccc.ccc.ccc......................
  -19 ...........................u.....u.=...=.u........................
  -18 .....................===================..........................   water header 2 (sulfur, acid)
  -17 .....................=.....u.....u................................
  -16 .....................=P....========================TTT............   petroleum header P, tank
  -15 .....................=......=.....=.........=...=..TTT............
  -14 .....................=......=.....=.......ccc.ccc..TTT............
  -13 .....................=......=.....=.......cLcPcLc.................   L light-oil crackers
  -12 .....................=......u.....u.......ccc.ccc.................
  -11 .....................=...................u=.u.=.u.................
  -10 .....................=....=========================TTT............   light oil header L, tank
   -9 .....................=....u.....u.....=..P.........TTT............
   -8 .....................=P...............ccc..........TTT............
   -7 .....................=..............P.cHc.TTT....P................   H heavy-oil cracker, heavy tank
   -6 .....................=................ccc.TTT......ccc............
   -5 .....................=................=.u.TTT......cbc............   b lubricant (faces west)
   -4 .....................=..===========================ccc==TTT.......   heavy oil header H, lubricant tank
   -3 .....................=..=.u.u.=.u.u.....u...u...u.......TTT.......
   -2 ....P................=..RRRRR.RRRRR.=============.......TTT.......   water header W (crackers)
   -1 .....................=P.RRRRR.RRRRR.=P............................
    0 .....................=..RR@RRPRRRRR.=.............................   R1 (anchor), R2
    1 .....JJJ.JJJ.JJJ.JJJ.=..RRRRR.RRRRR.=.............................
    2 .....JJJPJJJ.JJJPJJJ.=..RRRRR.RRRRR.=.............................   J pumpjacks
    3 .....JJJ.JJJ.JJJ.JJJ.u...u.=...u.=..=.............................
    4 .....=============================..=.............................   crude row
    5 .....................u...u.....u....=.............................
    6 ~====================================.............................   water row (~ = water arrives here)
```

`=` pipe, `u` pipe-to-ground end, `P` medium pole, `f` fast inserter (lower-case f inside a plant is the solid fuel recipe), `l` long-handed inserter, `i` inserter, `#` where a line from elsewhere hands items in or takes them away, lower-case `c` chemical plant body. Power arrives from the grid to the west through the pole at (-22, -2). The basic site is everything except the crackers, tanks, lubricant, acid and solid fuel plants, headers W, H and L, the water pipe-to-ground pairs at (-1, 3)/(-1, 5) and (5, 3)/(5, 5), and the water row east of x -5.

Battery block, anchor B = centre of battery plant 1. Each character is one tile, x from B-8 to B+13, y from B-7 to B+3.

```
      B-8     B       B+8
  -7  ......................
  -6  ..#...................   iron arrives here
  -5  ..f.P.................
  -4  ..>>>>>>>>>>>>>.......   input belt: copper left lane, iron right lane
  -3  ...f...>>>>>>>>>>>>>>.   output belt: batteries on the left lane
  -2  ...#...l.i.l.i..P..i..   copper arrives at #; l in, i out
  -1  .......ccc.ccc.....#..   batteries leave at #
   0  ......PcBcPcBc........   B battery plants (face south)
   1  .......ccc.ccc........
   2  ...u==========........   acid row, from the acid line
   3  ......................
```

## 3. Entity table

### Basic site (anchor R1)

| Entity | Offset | Direction | Note |
|---|---|---|---|
| pumpjack | (-20, 2), (-16, 2), (-12, 2), (-8, 2) | south | output tile (-1, +2): the crude row at y 4 |
| pipe, crude row | y 4, x -21 to 7 | | |
| pipe, crude stubs | (1, 3), (7, 3) | | R1 and R2 crude tile (+1, +3) |
| oil-refinery R1, R2 | (0, 0), (6, 0) | north | `basic-oil-processing` |
| pipe-to-ground, petroleum | (2, -3) and (2, -12); (8, -3) and (8, -12) | south; north | under rows y -4 and -10 (used by the advanced site) |
| pipe | x 2 and x 8 for y -13 to -15 | | |
| pipe, petroleum header P | y -16, x 1 to 8 | | |
| pipe-to-ground, petroleum riser | (1, -17) and (1, -19); (7, -17) and (7, -19) | south; north | under water header 2 |
| chemical-plant | (2, -21) | south | `plastic-bar`, petroleum at (1, -19) |
| chemical-plant | (8, -21) | south | `sulfur`, petroleum at (7, -19), water at (9, -19) |
| pipe | (9, -19) | | water into the sulfur plant |
| water in | (-26, 6) | | water must arrive here from elsewhere: an offshore pump |
| pipe, water row | y 6, x -25 to -5 | | |
| pipe-to-ground | (-5, 5) and (-5, 3) | south; north | under the crude row |
| pipe, water riser | x -5, y 2 to -18 | | |
| pipe, water header 2 | y -18, x -4 to 13 | | |
| transport-belt, output | (5, -21), (5, -22), (5, -23) north; (5, -24) to (38, -24) east | | sulfur left lane, plastic right lane |
| fast-inserter | (4, -21) | west | plastic out, `drops_into` lane right |
| fast-inserter | (6, -21) | east | sulfur out, `drops_into` lane left |
| transport-belt, coal and iron | (-10, -25) to (11, -25) | east | coal right lane, iron left lane (iron only for the acid plant) |
| long-handed-inserter | (2, -23) | north | coal from (2, -25) into the plastic plant |
| coal in | onto the right lane of the coal belt near (-9, -25) | | coal must arrive here from elsewhere |
| iron in | onto the left lane of the coal belt near (-9, -25) | | iron must arrive here from elsewhere (advanced site only) |
| plastic and sulfur out | the output belt's east end near (36..38, -24) | | the base takes them from here |
| medium-electric-pole | (-22, -2), (-18, 2), (-10, 2), (3, 0), (-4, -1), (-4, -8), (-4, -16), (0, -23), (4, -23), (-7, -23), (10, -23), (16, -23), (22, -23), (28, -23), (35, -23) | | (-22, -2) joins the grid to the west |

### Advanced site: what is added

| Entity | Offset | Direction | Note |
|---|---|---|---|
| R1, R2 recipe | (0, 0), (6, 0) | north | `advanced-oil-processing`, set LAST |
| pipe, water row extension | y 6, x -4 to 10 | | |
| pipe-to-ground, refinery water | (-1, 5) and (-1, 3); (5, 5) and (5, 3) | south; north | under the crude row into (-1, +3) |
| pipe, water riser and header W | x 10, y 5 to -1; y -2, x 10 to 22 | | |
| pipe, heavy stubs | (-2, -3), (4, -3) | | heavy tile (-2, -3) |
| pipe, heavy header H | y -4, x -2 to 24 | | |
| pipe-to-ground, light oil | (0, -3) and (0, -9); (6, -3) and (6, -9) | south; north | under H into header L |
| pipe, light oil header L | y -10, x 0 to 24 | | |
| pipe, petroleum header P extension | y -16, x 9 to 24 | | |
| chemical-plant H | (13, -7) | south | `heavy-oil-cracking`: heavy pipe (12, -5) off H; water pipe-to-ground (14, -5) north and (14, -3) south from W; light out pipe (12, -9) to L |
| chemical-plant L1, L2 | (17, -13), (21, -13) | south | `light-oil-cracking`: light pipes (16, -11), (20, -11) off L; water pipe-to-ground (18, -11)/(22, -11) north and (18, -3)/(22, -3) south from W; petroleum out pipes (18, -15), (22, -15) to P |
| chemical-plant | (26, -5) | west | `lubricant`: heavy in at (24, -4), the end of H; out pipes (28, -4), (29, -4) |
| storage-tank, heavy | (17, -6) | north | joins H at (18, -4) |
| storage-tank, light | (26, -9) | north | joins L at (24, -10) |
| storage-tank, petroleum | (26, -15) | north | joins P at (24, -16) |
| storage-tank, lubricant | (31, -3) | north | joins (29, -4) |
| chemical-plant | (12, -21) | south | `sulfuric-acid`: water pipe (13, -19) off header 2 |
| inserter | (12, -23) | north | sulfur off the output belt (12, -24) |
| long-handed-inserter | (11, -23) | north | iron off the coal/iron belt's last tile (11, -25) |
| pipe-to-ground, acid | (13, -23) and (13, -26) | south; north | under both belts |
| pipe | (13, -27), (13, -28) | | |
| storage-tank, acid | (12, -30) | north | its east tile (14, -29) starts the acid line |
| chemical-plant | (16, -21) | south | `solid-fuel-from-light-oil` |
| pipe-to-ground, light oil | (15, -19) and (15, -11) | north; south | from L, under P and header 2 |
| long-handed-inserter | (17, -23) | south | solid fuel onto (17, -25) |
| transport-belt, solid fuel | (17, -25) to (38, -25) | east | solid fuel on the left lane; its east end is where solid fuel leaves for the base |
| medium-electric-pole | (10, -7), (11, -1), (15, -9), (19, -13), (23, -7), (36, -27) | | |

### Battery block (anchor B; B = R1 + (84, -31) when fed by the 66-tile acid line below)

| Entity | Offset from B | Direction | Note |
|---|---|---|---|
| chemical-plant | (0, 0), (4, 0) | south | `battery`: acid either of (-1, +2), (+1, +2) |
| pipe, acid row | y 2, x -4 to 5 | | |
| pipe-to-ground | (-5, 2) | east | last piece of the acid line |
| transport-belt, input | (-6, -4) to (6, -4) | east | copper left lane, iron right lane |
| transport-belt, output | (-1, -3) to (12, -3) | east | batteries on the left lane |
| long-handed-inserter | (-1, -2), (3, -2) | north | reaches over the output belt to the input belt |
| inserter | (1, -2), (5, -2) | south | batteries out, `drops_into` lane left |
| medium-electric-pole | (-2, 0), (2, 0), (-4, -5), (8, -2) | | |
| iron in, copper in | right lane of the input belt near (-6, -4); left lane near (-5, -4) | | must arrive here from elsewhere |
| batteries out | the output belt's east end near (11, -3) | | the base takes them from here |

## 4. Build order

Commands put R1 at (0.5, 0.5): every `fac` coordinate is the offset plus 0.5. Pipes and belts block walking; `fac walk` finds a route round them. `fac walk` stops within 1 tile of the target, so if a `fac place` answers that the spot is out of reach, walk a few tiles closer and repeat it. Use `--wait` on every `fac mine`.

### Basic site

Wells: pumpjacks on 4 wells 4 tiles apart in a row. Water must arrive at the west end of the water row, (-26, 6), from an offshore pump.

```sh
# spot (-14, -3)
fac walk -13.5,-2.5 --wait
fac place pumpjack -19.5,2.5 --direction south
fac place pumpjack -15.5,2.5 --direction south
fac place pumpjack -11.5,2.5 --direction south
fac place pumpjack -7.5,2.5 --direction south      # ports: output pipe_at -8.5, 4.5, fluid crude-oil
fac place medium-electric-pole -21.5,-1.5
fac place medium-electric-pole -17.5,2.5
fac place medium-electric-pole -9.5,2.5
fac place pipe -20.5,4.5 --to 7.5,4.5 --wait       # crude row, ends beside the far end
fac place pipe 1.5,3.5
fac place pipe 7.5,3.5

# spot (-12, 8)
fac walk -11.5,8.5 --wait
fac place pipe-to-ground -4.5,5.5 --direction south
fac place pipe-to-ground -4.5,3.5 --direction north   # paired_with -4.5,5.5
fac place pipe -4.5,6.5 --to -24.5,6.5 --wait         # water row, to the offshore pump

# spot (-7, -2)
fac walk -6.5,-1.5 --wait
fac place medium-electric-pole -3.5,-0.5
fac place pipe -4.5,2.5 --to -4.5,-17.5 --wait        # water riser
fac place pipe -3.5,-17.5 --to 13.5,-17.5 --wait      # water header 2

# spot (3, -7)
fac walk 3.5,-6.5 --wait
fac place oil-refinery 0.5,0.5 --direction north
fac place oil-refinery 6.5,0.5 --direction north
fac place medium-electric-pole 3.5,0.5
fac place pipe-to-ground 2.5,-2.5 --direction south
fac place pipe-to-ground 2.5,-11.5 --direction north
fac place pipe-to-ground 8.5,-2.5 --direction south
fac place pipe-to-ground 8.5,-11.5 --direction north
fac recipe 0.5,0.5 basic-oil-processing    # ports: crude joined_to pipe 1.5,3.5; petroleum joined_to pipe-to-ground 2.5,-2.5
fac recipe 6.5,0.5 basic-oil-processing

# spot (5, -13)
fac walk 5.5,-12.5 --wait
fac place pipe 2.5,-12.5 --to 2.5,-14.5 --wait
fac place pipe 8.5,-12.5 --to 8.5,-14.5 --wait
fac place pipe 1.5,-15.5 --to 8.5,-15.5 --wait        # petroleum header P

# spot (-6, -12)
fac walk -5.5,-11.5 --wait
fac place medium-electric-pole -3.5,-7.5
fac place medium-electric-pole -3.5,-15.5

# spot (5, -27)
fac walk 5.5,-26.5 --wait
fac place chemical-plant 2.5,-20.5 --direction south
fac place chemical-plant 8.5,-20.5 --direction south
fac place pipe-to-ground 1.5,-18.5 --direction north
fac place pipe-to-ground 1.5,-16.5 --direction south
fac place pipe-to-ground 7.5,-18.5 --direction north
fac place pipe-to-ground 7.5,-16.5 --direction south
fac place pipe 9.5,-18.5
fac recipe 2.5,-20.5 plastic-bar           # ports: petroleum joined_to pipe-to-ground 1.5,-18.5
fac recipe 8.5,-20.5 sulfur                # ports: water joined_to pipe 9.5,-18.5, petroleum joined_to pipe-to-ground 7.5,-18.5
fac place transport-belt 5.5,-20.5 --direction north
fac place transport-belt 5.5,-21.5 --direction north
fac place transport-belt 5.5,-22.5 --direction north
fac place transport-belt 5.5,-23.5 --direction east
fac place fast-inserter 4.5,-20.5 --direction west    # drops_into lane right (plastic)
fac place fast-inserter 6.5,-20.5 --direction east    # drops_into lane left (sulfur)
fac place long-handed-inserter 2.5,-22.5 --direction north
fac place medium-electric-pole 0.5,-22.5
fac place medium-electric-pole 4.5,-22.5

# spot (-10, -27): coal belt, laid upstream to downstream
fac walk -9.5,-26.5 --wait
fac place transport-belt -9.5,-24.5 --to 11.5,-24.5 --wait

# spot (6, -27): output belt east toward the base
fac walk 6.5,-26.5 --wait
fac place transport-belt 6.5,-23.5 --to 38.5,-23.5 --wait
fac place medium-electric-pole 28.5,-22.5 --to 10.5,-22.5 --spacing 6 --wait
```

Coal must arrive on the right lane of the coal belt from the coal line upstream. The long-handed inserter takes only coal.

### Advanced site, as a change

Build all sinks first and switch the refineries last, so no product comes out before its pipe exists.

```sh
# spot (-8, 8)
fac walk -7.5,8.5 --wait
fac place pipe -3.5,6.5 --to 10.5,6.5 --wait
fac place pipe 10.5,5.5 --to 10.5,-1.5 --wait
fac place pipe 11.5,-1.5 --to 22.5,-1.5 --wait        # water header W

# spot (2, 8)
fac walk 2.5,8.5 --wait
fac place pipe-to-ground -0.5,3.5 --direction north
fac place pipe-to-ground -0.5,5.5 --direction south
fac place pipe-to-ground 5.5,3.5 --direction north
fac place pipe-to-ground 5.5,5.5 --direction south

# spot (3, -7)
fac walk 3.5,-6.5 --wait
fac place pipe-to-ground 0.5,-2.5 --direction south
fac place pipe-to-ground 0.5,-8.5 --direction north
fac place pipe-to-ground 6.5,-2.5 --direction south
fac place pipe-to-ground 6.5,-8.5 --direction north
fac place pipe -1.5,-2.5
fac place pipe 4.5,-2.5
fac place pipe -1.5,-3.5 --to 24.5,-3.5 --wait        # heavy header H

# spot (24, -8)
fac walk 24.5,-7.5 --wait
fac place pipe 24.5,-9.5 --to 0.5,-9.5 --wait         # light oil header L

# spot (9, -14)
fac walk 9.5,-13.5 --wait
fac place pipe 9.5,-15.5 --to 24.5,-15.5 --wait       # petroleum header P to the tank

# spot (20, -7)
fac walk 20.5,-6.5 --wait
fac place chemical-plant 13.5,-6.5 --direction south
fac recipe 13.5,-6.5 heavy-oil-cracking   # ports: water pipe_at 14.5,-4.5, heavy 12.5,-4.5, light 14.5,-8.5 or 12.5,-8.5
fac place pipe 12.5,-4.5
fac place pipe-to-ground 14.5,-4.5 --direction north
fac place pipe-to-ground 14.5,-2.5 --direction south
fac place pipe 12.5,-8.5
fac place medium-electric-pole 15.5,-8.5
fac place storage-tank 17.5,-5.5

# spot (9, -7)
fac walk 9.5,-6.5 --wait
fac place medium-electric-pole 10.5,-6.5
fac place medium-electric-pole 11.5,-0.5

# spot (24, -12)
fac walk 24.5,-11.5 --wait
fac place chemical-plant 17.5,-12.5 --direction south
fac place chemical-plant 21.5,-12.5 --direction south
fac recipe 17.5,-12.5 light-oil-cracking
fac recipe 21.5,-12.5 light-oil-cracking
fac place pipe 16.5,-10.5
fac place pipe-to-ground 18.5,-10.5 --direction north
fac place pipe-to-ground 18.5,-2.5 --direction south
fac place pipe 18.5,-14.5
fac place pipe 20.5,-10.5
fac place pipe-to-ground 22.5,-10.5 --direction north
fac place pipe-to-ground 22.5,-2.5 --direction south
fac place pipe 22.5,-14.5
fac place medium-electric-pole 19.5,-12.5

# spot (30, -10)
fac walk 30.5,-9.5 --wait
fac place chemical-plant 26.5,-4.5 --direction west
fac recipe 26.5,-4.5 lubricant            # ports: heavy joined_to pipe 24.5,-3.5
fac place pipe 28.5,-3.5
fac place pipe 29.5,-3.5
fac place storage-tank 31.5,-2.5
fac place storage-tank 26.5,-8.5
fac place storage-tank 26.5,-14.5
fac place medium-electric-pole 23.5,-6.5

# spot (14, -28)
fac walk 14.5,-27.5 --wait
fac place chemical-plant 12.5,-20.5 --direction south
fac recipe 12.5,-20.5 sulfuric-acid
fac place pipe 13.5,-18.5
fac place pipe-to-ground 13.5,-22.5 --direction south
fac place pipe-to-ground 13.5,-25.5 --direction north
fac place pipe 13.5,-26.5
fac place pipe 13.5,-27.5
fac place storage-tank 12.5,-29.5
fac place inserter 12.5,-22.5 --direction north             # picks_from the output belt
fac place long-handed-inserter 11.5,-22.5 --direction north # picks_from 11.5,-24.5
fac place chemical-plant 16.5,-20.5 --direction south
fac recipe 16.5,-20.5 solid-fuel-from-light-oil
fac place pipe-to-ground 15.5,-18.5 --direction north       # warns: its underground end joins nothing yet
fac place long-handed-inserter 17.5,-22.5 --direction south # before the belt, whose line job leaves you 20 tiles east; warns until the belt is down, then drops_into the solid fuel belt
fac place transport-belt 17.5,-24.5 --to 38.5,-24.5 --wait
fac place medium-electric-pole 36.5,-26.5

# spot (24, -12)
fac walk 24.5,-11.5 --wait
fac place pipe-to-ground 15.5,-10.5 --direction south      # paired_with 15.5,-18.5

# spot (3, -7): switch the refineries last
fac walk 3.5,-6.5 --wait
fac recipe 0.5,0.5 advanced-oil-processing   # all 5 ports must show joined_to
fac recipe 6.5,0.5 advanced-oil-processing
```

Iron for the acid plant must arrive on the left lane of the coal belt from upstream.

### Long pipes: pipe-to-ground

A pair joins when its two pieces are at most 10 tiles apart in one row (9 tiles between them) and face away from each other. For a line running east, the first piece of a pair gets `--direction west` (its pipe end faces back the way the line comes from) and the second, 10 tiles further east, `--direction east`. The next pair starts on the next tile (11 tiles after the first piece). One pair covers 11 tiles.

- Joined: the second piece shows `paired_with` at the first piece's position, and `pipes_to` lists `pipe-to-ground` there.
- Not joined: `fac place` warns "its underground end joins nothing yet: its partner goes in a straight line behind it (the side opposite to its direction), at most 10 tiles away, facing the opposite way", and there is no `paired_with`. The first piece of every pair gives this warning until its partner stands; the second piece must not.
- `fac place pipe-to-ground --to` is refused: place each end.

A bounded loop for a long line, tested on 6 pairs (66 tiles) and used for the acid line and a 407-tile run. It stops at the end column or at the first piece that fails or doesn't join, and prints why. `c` adds 0.5 so negative offsets stay right.

```sh
c(){ awk "BEGIN{print $1+0.5}"; }
Y=-28.5      # the line's row
X=25         # offset of the first piece of the first pair
END=79       # offset of the last piece: X + 11*pairs - 1
x=$X
while [ $x -le $((END-10)) ]; do
  fac walk $(c $((x+5))),$(c -31) --wait >/dev/null
  fac place pipe-to-ground $(c $x),$Y --direction west >/dev/null || { echo "west piece at $x failed"; break; }
  r=$(fac place pipe-to-ground $(c $((x+10))),$Y --direction east) || { echo "east piece at $((x+10)) failed: $r"; break; }
  echo "$r" | jq -e '.result.paired_with' >/dev/null \
    || { echo "pair $x-$((x+10)) not joined: $r"; break; }
  x=$((x+11))
done
```

For the acid line, first place `fac place pipe-to-ground 14.5,-28.5 --direction west` (it joins the acid tank) and `fac place pipe-to-ground 24.5,-28.5 --direction east`, then run the loop with X=25 and END=79, then `fac place pipe 80.5,-28.5 --to 89.5,-28.5 --wait` for the battery block's acid row.

Length limit: one fluid segment may span at most 320 tiles (its bounding box). A segment of 312 tiles fed by a pump delivered 977 water/s into a tank at its far end. The 321st tile turns every piece of the segment `pipeline_overextended` in `fac place` and `fac inspect`, and nothing flows: a tank at the end of a 407-tile run got 0 water in 943 ticks. Removing the extra tiles makes it flow again by itself. A pump splits segments: with a pump at 312 tiles, 348 tiles in total carried 1,064 water/s to the far tank. So put a pump (it needs power) at least every 300 tiles, and stop when `fac place` answers `pipeline_overextended`.

### Battery block (acid by pipe, solids by belt)

Commands put B at (0.5, 0.5), with the acid line ending in a pipe-to-ground at B + (-5, 2) facing east.

```sh
fac walk 2.5,5.5 --wait
fac place pipe -3.5,2.5 --to 5.5,2.5 --wait
fac place chemical-plant 0.5,0.5 --direction south
fac place chemical-plant 4.5,0.5 --direction south
fac recipe 0.5,0.5 battery            # ports: acid joined_to pipe -0.5,2.5 and 1.5,2.5
fac recipe 4.5,0.5 battery
fac walk 0.5,-7.5 --wait
fac place transport-belt -5.5,-3.5 --to 6.5,-3.5 --wait   # input: iron and copper
fac walk 0.5,-7.5 --wait
fac place transport-belt -0.5,-2.5 --to 12.5,-2.5 --wait  # output: batteries
fac walk 2.5,-6.5 --wait
fac place long-handed-inserter -0.5,-1.5 --direction north  # picks_from lane right, the input belt
fac place inserter 1.5,-1.5 --direction south               # drops_into lane left, the output belt
fac place long-handed-inserter 3.5,-1.5 --direction north
fac place inserter 5.5,-1.5 --direction south
fac place medium-electric-pole -3.5,-4.5
fac place medium-electric-pole 2.5,0.5
fac place medium-electric-pole 8.5,-1.5
fac place medium-electric-pole -1.5,0.5 --to -41.5,0.5 --spacing 8 --wait   # joins the site's grid
```

Iron must arrive on the input belt's right lane and copper on its left lane. Sideload them from the plate trunks (belts.md, "Merging two belts").

## 5. Checks after building

- Every refinery and chemical plant: `fac inspect` and read `ports`. Every fluid of the recipe must have an entry with `joined_to` and no `problem`. Plastic, acid, lubricant, solid fuel and the cracking outputs list two entries for one fluid; one joined entry is enough.
- Pumpjacks: `fac inspect` must show `working` and a `ports` entry with `joined_to`. A pumpjack that says `working` with no `joined_to` is filling itself and stops after about 20 s.
- Every pipe-to-ground: `paired_with` present.
- The `hud` `warnings` of every answer: "no power on the network of the pole at X, Y" means the site's poles are not joined to a running generator.
- `fac observe --problems` standing at (9, -14). Normal in steady state: the light crackers, the solid fuel plant, the lubricant plant and the sulfur plant short of fluid for part of the time (`missing` light oil 24 of 30, petroleum 29.6 of 30 and so on); the acid plant `item_ingredient_shortage` sulfur when the sulfur lane runs low; one pumpjack `waiting_for_space_in_destination` at times (4 jacks give a little more than 2 refineries use). A refinery `full_output` or `fluid_ingredient_shortage`, or a plant with `full_output`, is a fault. `--problems` does not list boilers at `full_output` or drills waiting on a full belt, so those elsewhere on the map are no sign of trouble here.
- `fac observe` on the belts: the output belt `left: sulfur`, `right: plastic-bar`; the solid fuel belt `left: solid-fuel`; the coal belt `left: iron-plate`, `right: coal`; battery belts `left: copper-plate`, `right: iron-plate` and `left: battery`.
- `fac stats plastic-bar sulfur solid-fuel lubricant sulfuric-acid battery petroleum-gas`: compare with the rates in section 6.
- Screenshot (`fac screenshot` from (10, -12)): in alt mode each plant shows its recipe icon; the lubricant plant's arrows point west; tanks show their fluid colour (heavy brown, light yellow, petroleum grey, lubricant green).

Mistakes and their fixes:

| Symptom | Cause | Fix |
|---|---|---|
| `fac place transport-belt A --to B` answers `already stands ... facing west` | the line was first laid from B to A, so it runs the wrong way | `--to` lays toward B: start upstream. Mine the run (`--wait` on each `fac mine`) and lay it again |
| Refinery `working` for 20 s, then `full_output` | petroleum pipe on an unused tile | the `ports` petroleum entry has no `joined_to`: move the pipe to its `pipe_at` |
| Pumpjack `waiting_for_space_in_destination` | no pipe on its output | lay one on the `ports` `pipe_at` |
| AM2 acid or lubricant port on the wrong side | `--direction` ignored for an AM2 without a fluid recipe | `fac recipe` first, then `fac rotate` until `ports` `pipe_at` is your pipe |
| Plant `fluid_ingredient_shortage`, a port shows `problem` | two pipes swapped, or a header of one fluid touching both inputs | a two-fluid recipe needs its two tiles on different lines. Keep headers one tile off the port row and bring each fluid up on its own stub or pipe-to-ground, as in this layout |
| Pipe-to-ground warns "its underground end joins nothing yet" on the second piece of a pair | more than 10 tiles apart, not in one row, or facing the same way | mine it (`--wait`) and place it where the warning says |
| Fluid line `pipeline_overextended` | the segment spans more than 320 tiles | pump in the middle, or shorten it |
| Plant `full_output` after a recipe change | the new output port is joined to a header of another fluid (`problem` on that port) | see "Before changing a recipe" in section 6 |

## 6. Rates, extending, limits and failure

Rates (production statistics, game minutes):

| | Basic | Advanced |
|---|---|---|
| crude used | 2,400/min (40/s) | 2,400/min |
| petroleum made | 1,080/min | 1,950 to 2,320/min |
| plastic | 42 to 46/min | 78 to 92/min |
| sulfur | 42 to 44/min | 78 to 93/min (60 to 70 into acid) |
| solid fuel | | 32 to 34/min |
| lubricant | | 255 to 270/min |
| sulfuric acid | | 570 to 650/min (limited by sulfur) |
| batteries (battery block) | | 30/min |
| power, whole site | 976 kW | 1,572 kW, 2,450 kW with the battery block |

What limits it: petroleum. Plastic needs 10 petroleum per bar and sulfur 15 per piece; the plants could use 50 petroleum/s and get 18 on basic and 33 to 39 on advanced, so both plants share a shortfall. Two refineries need exactly 4 pumpjacks on 100% wells (10 crude/s each).

Cracking is sized for the case where only petroleum is used: 2 advanced refineries make 10 heavy/s and 18 light/s. One heavy cracker takes up to 20 heavy/s and makes 15 light/s. Two light crackers take up to 30 light/s against at most 25.5. With the lubricant pipe and the solid fuel inserter removed, the lubricant and solid fuel plants go `full_output`, the refineries stay `working`, the light crackers show spare capacity (`fluid_ingredient_shortage` part of the time) and petroleum rises from 1,980 to 2,320/min.

Extending: everything leaves east. The headers end at x 24 and the tanks at x 25 to 27; extend a header past its tank by joining the tank's other tile, or add plants along a header's free tiles one row off it. A third refinery would stand at (12, 0), but the water riser at x 10 and the heavy cracker's water pipe-to-ground at (14, -3) are in its way: move them 6 tiles east first, and extend the crude row and the water row to x 13 (untested). A third refinery also needs 2 more pumpjacks on 100% wells. A second copy of the site needs its own wells; keep the strip east of x 39 free for the output belts. Upgrades: more refineries before more plants (both plants are short of petroleum); at 0.86 items/s a yellow inserter can't keep up with the plastic plant (up to 2 plastic/s), so use the fast inserters shown.

Backed-up output (tested on the basic site): when nothing takes plastic and sulfur, the output belt fills and both plants go `full_output`. The petroleum line (2,200 units) fills in about 2 minutes, then both refineries go `full_output` and the pumpjacks `waiting_for_space_in_destination`. Nothing is lost: crude stays in the wells. Once the base takes again, everything is `working` within 20 s of game time without a visit. On the advanced site a refinery that stops for petroleum also stops heavy oil, light oil, lubricant and solid fuel (inferred, not run).

Inputs running dry (tested on the advanced site): with no coal, the plastic plant goes `item_ingredient_shortage`. With no water, both refineries go `fluid_ingredient_shortage`, then the crackers, and plastic and sulfur fall to 0. With coal and water back, the whole site is `working` again by itself (plastic 80/min within 160 s of game time). Advanced oil stops completely without water: the water supply matters more than anything else on the site.

The acid plant takes its sulfur off the output belt, so while its tank fills (25,000 acid, about 42 minutes at 10/s) only 10 to 30 sulfur/min goes east. Build the acid plant when processing units or batteries need it, or add a second sulfur plant for it.

Before changing any plant's recipe:

1. Find what consumes the old product. For a fluid, `fac inspect` the plant's output port's `joined_to` pipe and follow that header to the plants on it. For an item, look at the belt's consumers. Example: the heavy cracker's light oil feeds the light crackers and the solid fuel plant; switching it to lubricant leaves the lubricant plant as heavy oil's only sink, and once the heavy tank (25,000) fills, about 40 minutes at 10 heavy/s, the refineries stop.
2. Read `ports` in the `fac recipe` answer: every new fluid must be joined to a pipe carrying that fluid, with no `problem`. Tested: switching the heavy cracker at (13, -7) to `lubricant` is accepted and says `working`; its lubricant output is joined to the light-oil header pipe (12, -9), which can't take it, so the plant fills with lubricant and heads for `full_output`. Switching back to `heavy-oil-cracking` works again.
3. A refinery from basic to advanced needs water on (-1, +3) and pipes on heavy (-2, -3) and light (0, -3) first, facing north.

Power drop: not tested. A refinery and chemical plant restart by themselves when power returns, as they did after every other stop.

## 7. Not tested

- The site in any orientation other than refineries north and belts east (the port tables cover every direction).
- A real offshore pump feeding the water row, a real coal line on the coal belt, and real consumers at the belts' east ends.
- Processing units: an AM2 with `processing-unit` takes acid at (0, -2) facing north, or (0, +2) facing south, so a row of south-facing AM2s on the same acid row as the battery plants should work; not built.
- Backed-up output on the advanced site, a power drop, a third refinery.
- Whether the 977 water/s through 312 tiles was limited by the pump (rated 1,200/s) or by the pipe.
