# Science block: red, green, 16 labs and a mall between two plate trunks (tested)

This block turns an iron plate belt and a copper plate belt into red and green science, runs 16 labs on one chain, takes blue, purple and yellow packs in on two belts at lab 1, and fills five chests you take buildings and intermediates from. Inputs: the iron trunk and the copper trunk arrive from the west and run east 6 tiles apart; blue, purple and yellow arrive on two belts from the north at the west end. Nothing leaves except research and what you take out of the mall chests.

Measured with assembling machine 1 everywhere: 12.0 red/min (0.20/s) and 20.1 green/min (0.33/s). With the two red and four green assemblers swapped for assembling machine 2: 18.0 red/min (0.30/s) and 30.1 green/min (0.50/s). 16 labs on a 30 s technology used 31.5 red and 31.5 green a minute (their maximum is 32), and with all five packs on a 60 s technology 16.0 red, 15.9 green and 15.9 each of blue, purple and yellow (maximum 16). At the AM2 rate the science needs about 3.4 iron/s and 1.1 copper/s (from the recipes). Plan to bring more: with 5.1 iron/s and up to 3.4 copper/s arriving, the mall used the surplus. The block draws up to 2.7 MW (2,745 kW with every lab and assembler running; 141 kW idle). 138 buildings plus 47 belt tiles of its own.

The mall goes downstream (east) of the science on the trunks. Put upstream, it takes the science's iron first and costs about an hour of science from empty chests (see "Mall: downstream on purpose").

## Layout

Tested orientation: belts run east, x east and y south. The anchor is the iron trunk tile where the block starts: every position below is an offset (dx, dy) of an entity centre from the centre of that tile. Other orientations are untested.

```
dx          0         1         2         3         4         5         6
            |         |         |         |         |         |         |
dy  -17 .......................LLL
dy  -16 .......................LLL
dy  -15 .......................LLL
dy  -14 .k......................^.*
dy  -13 .k.....LLL.LLL.LLL.LLL.LLL.LLL.LLL.LLL.LLL
dy  -12 .k.....LLL<LLL<LLL<LLL<LLL>LLL>LLL>LLL>LLL
dy  -11 .k.....LLL.LLL.LLL.LLL.LLL.LLL.LLL.LLL.LLL
dy  -10 .k........*...*...*...*nnn*...*...*...*
dy   -9 .k.......bbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
dy   -8 .k.k.....v..v...v..v...LLL............b
dy   -7 .k.k....XXXXXX.XXXXXX..LLL............b
dy   -6 .k.k....XXXXXX.XXXXXX..LLL............b
dy   -5 .k.k....XXXXXX.XXXXXX..........GGG.TTTb
dy   -4 .k.k.....v*.v.*.v.*v..*nnn*....GGG>TTTb
dy   -3 .k.kkk>LLL.LLL.LLL.LLL.LLL.....GGG.TTTb
dy   -2 .kkkkk>LLL>LLL>LLL>LLL>LLL......n.*vn.b
dy   -1 ......*LLL.LLL.LLL.LLL.LLL...bbbbbbbbbb
dy    0 ====@==============================================================
dy    1 ..*.v.*.n...v.*.n.......v.*v.n*vv.......v.....v....vv...v.....v
dy    2 ...GGG.RRR.GGG.RRR.CCC>EEE.III.GGG.CCC>EEE..*III..*GGG*TTT..*PPP
dy    3 ...GGG>RRR.GGG>RRR.CCC*EEE>III<GGG.CCC*EEE>c>III.w.GGG>TTT>c.PPP
dy    4 ...GGG.RRR.GGG.RRR.CCC>EEE.III.GGG.CCC>EEE.c<III.c<GGG.TTT.c<PPP
dy    5 ........^.*.....^.*.^...............^
dy    6 -------------------------------------------------------------------
```

`@` anchor (iron trunk tile). `=` iron trunk, both lanes iron, running east. `-` copper trunk, both lanes copper, running east. `b` green feed belt: east along dy -1, north along dx 34, west along dy -9; inserters on its left lane, transport belts on its right lane. `k` pack entry belts: belt A down dx -3 and east along dy -2 (blue on its left lane, purple on its right), belt B down dx -1 and east along dy -3 (yellow on its right lane, left lane free). `L` lab. Assemblers: `G` gears, `R` red packs, `C` copper cable, `E` electronic circuits, `I` inserters, `T` transport belts, `P` pipes, `X` green packs. Inserters (basic or fast, see the table) are drawn as the way items move: `^ v < >`. Long-handed inserters as the way items move: `n` north, `s` south, `w` west, `e` east. `*` small pole, `c` wooden chest. The two `c` at dx 39 and the ones at dx 45 and 55 are the mall's output chests.

## Entities

Inserter direction is the side it picks up from, as `fac place --direction` takes it.

| Entity | Offset (dx, dy) | Direction | Note |
|---|---|---|---|
| transport-belt (iron trunk) | (x, 0) for x from the west edge to 62 | east | iron on both lanes |
| transport-belt (copper trunk) | (x, 6), same x | east | copper on both lanes |
| **Red cell 1 (the milestone cell)** | | | |
| assembling-machine-1, `iron-gear-wheel` | (0, 3) | | |
| inserter | (0, 1) | north | iron off the trunk into the gear assembler (placed when the trunk arrives) |
| inserter | (2, 3) | west | gears into the red assembler |
| assembling-machine-1 (AM2 later), `automation-science-pack` | (4, 3) | | |
| inserter | (4, 5) | south | copper off the trunk (placed when the trunk arrives) |
| long-handed-inserter | (4, 1) | south | picks red packs at dy 3, drops them over the iron trunk into lab 1 at dy -1 |
| small-electric-pole | (-2, 1), (2, 1), (6, -4), (6, 5) | | (6, 5) goes in with the copper inserter |
| **Red cell 2** | | | |
| assembling-machine-1, `iron-gear-wheel` | (8, 3) | | inserter (8, 1) north for iron |
| inserter | (10, 3) | west | gears into red assembler 2 |
| assembling-machine-1 (AM2 later), `automation-science-pack` | (12, 3) | | inserter (12, 5) south for copper |
| long-handed-inserter | (12, 1) | south | red packs over the iron trunk into lab 3 |
| small-electric-pole | (10, 1), (14, 5) | | |
| **Green strip** (between the trunks) | | | |
| assembling-machine-1, `copper-cable` | (16, 3) | | inserter (16, 5) south for copper |
| inserter | (18, 2), (18, 4) | west | cable into the circuit assembler: two, since one inserter moves about 0.83 items/s |
| assembling-machine-1, `electronic-circuit` | (20, 3) | | inserter (20, 1) north for iron |
| inserter | (22, 3) | west | circuits into the inserter assembler |
| assembling-machine-1, `inserter` | (24, 3) | | inserter (23, 1) north for iron |
| long-handed-inserter | (25, 1) | south | lifts the inserters over the iron trunk onto the feed belt at dy -1 (left lane) |
| inserter | (26, 3) | east | gears into the inserter assembler |
| assembling-machine-1, `iron-gear-wheel` | (28, 3) | | inserters (27, 1) and (28, 1) north for iron |
| small-electric-pole | (18, 3), (22, 1), (26, 1) | | |
| **North row** (north of the iron trunk) | | | |
| assembling-machine-1, `iron-gear-wheel` | (28, -4) | | long-handed-inserter (28, -2) south: iron from the trunk, reaching over the feed belt |
| inserter | (30, -4) | west | gears into the belt assembler |
| assembling-machine-1, `transport-belt` | (32, -4) | | long-handed-inserter (32, -2) south for its iron |
| inserter | (31, -2) | north | transport belts onto the feed belt (right lane) |
| small-electric-pole | (30, -2) | | |
| transport-belt (feed belt) | (25..33, -1) east, (34, -1..-8) north, (34..5, -9) west | | 47 tiles; corners turn by themselves |
| **Green assemblers** | | | |
| assembling-machine-1 (AM2 later), `logistic-science-pack` | (5, -6), (8, -6), (12, -6), (15, -6) | | the two west ones touch, the two east ones touch |
| inserter | (x, -8) for each | north | inserters and belts off the feed belt |
| inserter | (x, -4) for each | north | green packs into labs 1, 2, 3, 4 below |
| **Labs** | | | |
| lab 1 to 5 | (4, -2), (8, -2), (12, -2), (16, -2), (20, -2) | | |
| fast-inserter | (6, -2), (10, -2), (14, -2), (18, -2) | west | lab to lab, eastward (basic inserters until `fast-inserter` is researched) |
| small-electric-pole | (10, -4), (14, -4), (18, -4), (22, -4) | | |
| lab 6 | (20, -7) | | long-handed-inserters (19, -4), (20, -4), (21, -4) south, from lab 5 |
| lab 7 | (20, -12) | | long-handed-inserters (19, -10), (20, -10), (21, -10) south, from lab 6 over the feed belt |
| labs 8 to 11 | (16, -12), (12, -12), (8, -12), (4, -12) | | fast-inserters (18, -12), (14, -12), (10, -12), (6, -12) east |
| labs 12 to 15 | (24, -12), (28, -12), (32, -12), (36, -12) | | fast-inserters (22, -12), (26, -12), (30, -12), (34, -12) west |
| lab 16 | (20, -16) | | fast-inserter (20, -14) south |
| small-electric-pole | (18, -10), (22, -10), (14, -10), (10, -10), (6, -10), (26, -10), (30, -10), (34, -10), (22, -14) | | |
| **Pack entry at lab 1** | | | |
| transport-belt (belt A) | (-3, y) south down to dy -3, then (-3..1, -2) east | | blue on the left lane, purple on the right |
| transport-belt (belt B) | (-1, y) south down to dy -4, then (-1..1, -3) east | | yellow on the right lane; left lane free |
| fast-inserter | (2, -2) | west | from belt A's end into lab 1 |
| fast-inserter | (2, -3) | west | from belt B's end into lab 1 |
| small-electric-pole | (2, -1) | | |
| **Mall** (downstream of the science) | | | |
| assembling-machine-1, `copper-cable` | (32, 3) | | inserter (32, 5) south for copper; inserters (34, 2), (34, 4) west, cable into circuits |
| assembling-machine-1, `electronic-circuit` | (36, 3) | | inserter (36, 1) north for iron; inserter (38, 3) west into the circuit chest |
| wooden-chest, circuits | (39, 3) | | you take circuits here |
| inserter | (40, 3) | west | circuits from the chest into the inserter assembler |
| assembling-machine-1, `inserter` | (42, 3) | | inserter (42, 1) north for iron; inserter (40, 4) east into the inserter chest |
| wooden-chest, inserters | (39, 4) | | |
| long-handed-inserter | (45, 3) | east | gears straight from the gear assembler into the inserter assembler |
| assembling-machine-1, `iron-gear-wheel` | (48, 3) | | inserters (47, 1), (48, 1) north for iron; inserter (46, 4) east into the gear chest |
| wooden-chest, gears | (45, 4) | | |
| inserter | (50, 3) | west | gears into the belt assembler |
| assembling-machine-1, `transport-belt` | (52, 3) | | inserter (52, 1) north for iron; inserter (54, 3) west into the belt chest |
| wooden-chest, transport belts | (55, 3) | | |
| assembling-machine-1, `pipe` (optional) | (58, 3) | | inserter (58, 1) north for iron; inserter (56, 4) east into the pipe chest |
| wooden-chest, pipes | (55, 4) | | |
| small-electric-pole | (34, 3), (40, 2), (46, 2), (50, 2), (56, 2) | | |

Totals: 20 assembling machines (6 become AM2), 16 labs, 41 inserters, 15 fast inserters, 12 long-handed inserters, 29 small poles, 5 wooden chests, 47 feed-belt tiles; plus the trunks across dx 0 to 62 and the two entry belts.

## Build order

Commands below put the anchor tile's centre at (0.5, 0.5): every coordinate is the offset plus 0.5. For an anchor at (ax, ay), add ax - 0.5 and ay - 0.5. Each group is one standing spot, outside the buildings it places, and the spots are listed in build order. Every spot is within 9 tiles of what it places, because `fac walk` stops up to 1 tile short. Walk between spots round the ends of the rows or over belts; the gap at dx 10 between the green assemblers is walkable.

### 1. Red milestone cell, before any belt

Needs `automation` (long-handed inserter) and a pole line from the grid to (-2, 1).

```sh
fac walk 0.5,-4.5 --wait
fac place small-electric-pole -1.5,1.5
fac place small-electric-pole 2.5,1.5
fac place small-electric-pole 6.5,-3.5
fac place assembling-machine-1 0.5,3.5
fac recipe 0.5,3.5 iron-gear-wheel
fac place inserter 2.5,3.5 --direction west
fac place assembling-machine-1 4.5,3.5
fac recipe 4.5,3.5 automation-science-pack
fac place long-handed-inserter 4.5,1.5 --direction south
fac place lab 4.5,-1.5
fac insert 0.5,3.5 iron-plate 100
fac insert 4.5,3.5 copper-plate 50
fac research <a red technology>
```

Feed the gear assembler plates, not crafted gears. The lab starts researching on the cell's first pack. If the `hud` warns "no power on the network of the pole at X, Y", the pole line does not reach a running generator yet. When the trunks arrive, nothing here moves: the two belt inserters go in the free tiles (0, 1) and (4, 5) and the hand-fed plates run out by themselves.

### 2. Trunks

The trunks come from the smelting blocks. What must arrive here from elsewhere: iron plates on both lanes of the iron trunk at dy 0 and copper plates on both lanes of the copper trunk at dy 6. 3.4 iron/s on the trunk runs the AM2 science with nothing left for the mall; 5.1 iron/s ran the science at full rate and filled the mall. Laying them through the block:

```sh
fac walk -13.5,3.5 --wait
fac place transport-belt -13.5,0.5 --to 62.5,0.5 --wait
fac walk -13.5,3.5 --wait
fac place transport-belt -13.5,6.5 --to 62.5,6.5 --wait
```

If the iron rate is lower than the smelting should give, check the `status` of every inserter that puts plates on the trunk: one at the edge of a pole's supply area that stays `not_plugged_in_electric_network` cut the iron from 5.1 to 3.4/s.

### 3. Red cells on the belts

```sh
fac walk 2.5,8.5 --wait
fac place inserter 0.5,1.5 --direction north
fac place inserter 4.5,5.5 --direction south
fac place small-electric-pole 6.5,5.5
fac walk 11.5,8.5 --wait
fac place assembling-machine-1 8.5,3.5
fac recipe 8.5,3.5 iron-gear-wheel
fac place inserter 8.5,1.5 --direction north
fac place inserter 10.5,3.5 --direction west
fac place small-electric-pole 10.5,1.5
fac place assembling-machine-1 12.5,3.5
fac recipe 12.5,3.5 automation-science-pack
fac place long-handed-inserter 12.5,1.5 --direction south
fac place inserter 12.5,5.5 --direction south
fac place small-electric-pole 14.5,5.5
```

### 4. Labs 2 to 4

Place `inserter` instead of `fast-inserter` until `fast-inserter` is researched, then swap them from the same spot (`fac mine X,Y --wait`, then `fac place fast-inserter X,Y --direction west`). The fast inserters between labs 1 to 4 matter once the chain carries all five packs (see "Rates and lab counts").

```sh
fac walk 10.5,-6.5 --wait
fac place fast-inserter 6.5,-1.5 --direction west
fac place lab 8.5,-1.5
fac place fast-inserter 10.5,-1.5 --direction west
fac place lab 12.5,-1.5
fac place fast-inserter 14.5,-1.5 --direction west
fac place lab 16.5,-1.5
fac place small-electric-pole 10.5,-3.5
fac place small-electric-pole 14.5,-3.5
```

### 5. Green strip

```sh
fac walk 23.5,8.5 --wait
fac place assembling-machine-1 16.5,3.5
fac recipe 16.5,3.5 copper-cable
fac place inserter 16.5,5.5 --direction south
fac place inserter 18.5,2.5 --direction west
fac place inserter 18.5,4.5 --direction west
fac place small-electric-pole 18.5,3.5
fac place assembling-machine-1 20.5,3.5
fac recipe 20.5,3.5 electronic-circuit
fac place inserter 20.5,1.5 --direction north
fac place inserter 22.5,3.5 --direction west
fac place small-electric-pole 22.5,1.5
fac place assembling-machine-1 24.5,3.5
fac recipe 24.5,3.5 inserter
fac place inserter 23.5,1.5 --direction north
fac place long-handed-inserter 25.5,1.5 --direction south
fac place inserter 26.5,3.5 --direction east
fac place small-electric-pole 26.5,1.5
fac place assembling-machine-1 28.5,3.5
fac recipe 28.5,3.5 iron-gear-wheel
fac place inserter 27.5,1.5 --direction north
fac place inserter 28.5,1.5 --direction north
```

### 6. North row and feed belt

```sh
fac walk 28.5,-7.5 --wait
fac place assembling-machine-1 28.5,-3.5
fac recipe 28.5,-3.5 iron-gear-wheel
fac place long-handed-inserter 28.5,-1.5 --direction south
fac place inserter 30.5,-3.5 --direction west
fac place assembling-machine-1 32.5,-3.5
fac recipe 32.5,-3.5 transport-belt
fac place long-handed-inserter 32.5,-1.5 --direction south
fac place inserter 31.5,-1.5 --direction north
fac place small-electric-pole 30.5,-1.5
fac place transport-belt 25.5,-0.5 --to 33.5,-0.5 --wait
fac place transport-belt 34.5,-0.5 --to 34.5,-7.5 --wait
fac place transport-belt 34.5,-8.5 --to 5.5,-8.5 --wait
```

Each line starts beside the end of the one before. The 30-belt line leaves you at about (6, -9).

### 7. Green assemblers

```sh
fac walk 10.5,-10.5 --wait
fac place assembling-machine-1 5.5,-5.5
fac recipe 5.5,-5.5 logistic-science-pack
fac place inserter 5.5,-7.5 --direction north
fac place inserter 5.5,-3.5 --direction north
fac place assembling-machine-1 8.5,-5.5
fac recipe 8.5,-5.5 logistic-science-pack
fac place inserter 8.5,-7.5 --direction north
fac place inserter 8.5,-3.5 --direction north
fac place assembling-machine-1 12.5,-5.5
fac recipe 12.5,-5.5 logistic-science-pack
fac place inserter 12.5,-7.5 --direction north
fac place inserter 12.5,-3.5 --direction north
fac place assembling-machine-1 15.5,-5.5
fac recipe 15.5,-5.5 logistic-science-pack
fac place inserter 15.5,-7.5 --direction north
fac place inserter 15.5,-3.5 --direction north
```

### 8. Labs 5 to 7

```sh
fac walk 23.5,-5.5 --wait
fac place fast-inserter 18.5,-1.5 --direction west
fac place lab 20.5,-1.5
fac place small-electric-pole 18.5,-3.5
fac place long-handed-inserter 19.5,-3.5 --direction south
fac place long-handed-inserter 20.5,-3.5 --direction south
fac place long-handed-inserter 21.5,-3.5 --direction south
fac place small-electric-pole 22.5,-3.5
fac place lab 20.5,-6.5
fac place long-handed-inserter 19.5,-9.5 --direction south
fac place long-handed-inserter 20.5,-9.5 --direction south
fac place long-handed-inserter 21.5,-9.5 --direction south
fac place small-electric-pole 18.5,-9.5
fac place small-electric-pole 22.5,-9.5
```

### 9. Lab row along dy -12

```sh
fac walk 12.5,-15.5 --wait
fac place lab 20.5,-11.5
fac place fast-inserter 18.5,-11.5 --direction east
fac place lab 16.5,-11.5
fac place fast-inserter 14.5,-11.5 --direction east
fac place lab 12.5,-11.5
fac place fast-inserter 10.5,-11.5 --direction east
fac place lab 8.5,-11.5
fac place fast-inserter 6.5,-11.5 --direction east
fac place lab 4.5,-11.5
fac place small-electric-pole 14.5,-9.5
fac place small-electric-pole 10.5,-9.5
fac place small-electric-pole 6.5,-9.5
fac walk 28.5,-15.5 --wait
fac place fast-inserter 22.5,-11.5 --direction west
fac place lab 24.5,-11.5
fac place fast-inserter 26.5,-11.5 --direction west
fac place lab 28.5,-11.5
fac place fast-inserter 30.5,-11.5 --direction west
fac place lab 32.5,-11.5
fac place fast-inserter 34.5,-11.5 --direction west
fac place lab 36.5,-11.5
fac place small-electric-pole 26.5,-9.5
fac place small-electric-pole 30.5,-9.5
fac place small-electric-pole 34.5,-9.5
fac place fast-inserter 20.5,-13.5 --direction south
fac place lab 20.5,-15.5
fac place small-electric-pole 22.5,-13.5
```

### 10. Pack entry at lab 1

Belt A and belt B are the ends of the blue, purple and yellow blocks' output belts, coming south along dx -3 and dx -1. What must arrive here from elsewhere: blue on belt A's left lane, purple on its right lane, yellow on belt B's right lane. Their last stretch and the two entry inserters:

```sh
fac walk -5.5,-7.5 --wait
fac place transport-belt -2.5,-13.5 --to -2.5,-2.5 --wait
fac place transport-belt -2.5,-1.5 --to 1.5,-1.5 --wait
fac walk -5.5,-7.5 --wait
fac place transport-belt -0.5,-7.5 --to -0.5,-3.5 --wait
fac place transport-belt -0.5,-2.5 --to 1.5,-2.5 --wait
fac walk -4.5,-3.5 --wait
fac place fast-inserter 2.5,-1.5 --direction west
fac place fast-inserter 2.5,-2.5 --direction west
fac place small-electric-pole 2.5,-0.5
```

The corner tiles (-3, -2) and (-1, -3) turn by themselves (`fac inspect` says `turns: left`).

### 11. Mall

```sh
fac walk 37.5,8.5 --wait
fac place assembling-machine-1 32.5,3.5
fac recipe 32.5,3.5 copper-cable
fac place inserter 32.5,5.5 --direction south
fac place inserter 34.5,2.5 --direction west
fac place inserter 34.5,4.5 --direction west
fac place small-electric-pole 34.5,3.5
fac place assembling-machine-1 36.5,3.5
fac recipe 36.5,3.5 electronic-circuit
fac place inserter 36.5,1.5 --direction north
fac place inserter 38.5,3.5 --direction west
fac place wooden-chest 39.5,3.5
fac place small-electric-pole 40.5,2.5
fac place inserter 40.5,3.5 --direction west
fac place inserter 40.5,4.5 --direction east
fac place wooden-chest 39.5,4.5
fac place assembling-machine-1 42.5,3.5
fac recipe 42.5,3.5 inserter
fac place inserter 42.5,1.5 --direction north
fac walk 47.5,8.5 --wait
fac place long-handed-inserter 45.5,3.5 --direction east
fac place inserter 46.5,4.5 --direction east
fac place wooden-chest 45.5,4.5
fac place small-electric-pole 46.5,2.5
fac place assembling-machine-1 48.5,3.5
fac recipe 48.5,3.5 iron-gear-wheel
fac place inserter 47.5,1.5 --direction north
fac place inserter 48.5,1.5 --direction north
fac place small-electric-pole 50.5,2.5
fac place inserter 50.5,3.5 --direction west
fac walk 55.5,8.5 --wait
fac place assembling-machine-1 52.5,3.5
fac recipe 52.5,3.5 transport-belt
fac place inserter 52.5,1.5 --direction north
fac place inserter 54.5,3.5 --direction west
fac place wooden-chest 55.5,3.5
fac place small-electric-pole 56.5,2.5
fac place inserter 56.5,4.5 --direction east
fac place wooden-chest 55.5,4.5
fac place assembling-machine-1 58.5,3.5
fac recipe 58.5,3.5 pipe
fac place inserter 58.5,1.5 --direction north
```

Take buildings and intermediates with `fac take 39.5,3.5` (circuits), `39.5,4.5` (inserters), `45.5,4.5` (gears), `55.5,3.5` (belts) and `55.5,4.5` (pipes). All five are within 9 tiles of (47, 8) by the reach rule; `fac take` on them is untested.

Do not put a gear chest between the gear assembler and the inserter assembler with an inserter from the chest into the assembler: the chest stays empty, because the inserter assembler takes gears as fast as they come. Keep the long-handed inserter (45, 3) straight from the gear assembler into the inserter assembler and the separate inserter (46, 4) into the gear chest; the chest then fills at 11 gears/min.

### 12. Assembling machine 2

Place the AM2 straight on the AM1: `fac place` swaps them in place, the AM2 keeps the recipe and contents, the AM1 returns to your inventory, and the answer shows `replaced`. If the answer has no `replaced`, read it before going on. From (2, 8) for (4, 3), from (11, 8) for (12, 3), from (10, -11) for the four green assemblers:

```sh
fac place assembling-machine-2 4.5,3.5
fac inspect 4.5,3.5          # recipe automation-science-pack, status working
```

## Checks after building

- `fac place` on (4, 1) and (12, 1) must answer `drops_into` a lab (before the lab exists, `drops_at` with the warning that output lands on the ground; place the lab and inspect again). Facing north instead, it drops red packs onto the iron trunk: rotate it twice.
- `fac place` on (25, 1) says `drops_into` the transport belt at (25, -1), lane `left`; (31, -2) says lane `right`. `fac inspect` on feed belt tiles (26, -1), (34, -5), (20, -9) and (6, -9) then shows `inserter` only on `left` and `transport-belt` only on `right`.
- `fac inspect` on (-3, -8) shows `chemical-science-pack` on `left` and `production-science-pack` on `right`; on (-1, -6) only `utility-science-pack` on `right`. Both entry fast inserters say `picks_from` the belt and `drops_into` the lab at (4, -2).
- `fac observe --problems` with research running: no `not_plugged_in_electric_network`; science assemblers `working`, or `full_output` when labs are full. Mall assemblers may show `full_output` (chest full) or `item_ingredient_shortage` (the trunk ran out before reaching them): both are normal; see "Mall: downstream on purpose".
- `fac inspect` on lab 16 (20, -16) and lab 15 (36, -12) lists every pack type in `lab_input` once packs reach lab 1.
- The `hud` `warnings` of every answer: read them on every inserter you place beside a trunk.
- `fac screenshot` (alt mode, with its coordinate grid): both trunks grey and copper all the way, the feed belt with inserters on its inner (north on the eastward run) lane and belts on the outer lane, and every lab icon showing the pack types.

Mistakes and their signs:

| Symptom | Cause | Fix |
|---|---|---|
| `fac place` rejected for reach right after a `fac walk` | Standing spot 9.8 to 10.4 tiles from the far entity; the walk ended 1 tile short | Use the spots above; keep any new spot within 9 tiles |
| Several `fac mine X,Y` in a row, only the last building gone | Each mine without `--wait` is replaced by the next body job | `--wait` on every `fac mine` |
| Gear chest in the mall stays empty | Chest placed between the gear and inserter assemblers | Layout as in the table: long-handed inserter (45, 3) direct, inserter (46, 4) into the chest |
| A plate lane on a trunk fills with gears, circuits or packs | A mall or green output inserter drops onto a trunk | Never put gears or circuits on the plate belts; read `drops_into` on every inserter beside a trunk |
| An inserter beside a trunk moves nothing | Iron inserter placed on the copper side, or the other way round | Read `picks_from` and the `hud` `warnings`; move it |

## Extending, upgrading, limits, failure

**Rates and lab counts.** One lab at speed 1 uses 2 packs a minute of each type on a 30 s technology and 4 on a 15 s one. Measured pack supply and the 30 s labs it keeps busy:

| Science assemblers | Red | Green | Labs kept busy on 30 s technologies |
|---|---|---|---|
| AM1 | 12.0/min | 20.1/min (labs used 20.9 red, 21.3 green with extra red at the entry) | red 6, green 10 |
| AM2 (the 2 red and 4 green assemblers swapped) | 18.0/min | 30.1/min (labs used 31.5 of each) | red 9, green 15 |

Sizing rule: labs kept busy = packs per minute of the scarcest type ÷ (60 ÷ technology time in seconds).

With red only from the two cells, red sets the rate: AM1 labs used 11.7 red and 12.4 green a minute, AM2 18.2 red and 18.4 green, and the green assemblers waited `full_output`. For more red, put red packs on belt B's free left lane from a red block elsewhere (untested on that lane; red on belt A's two lanes reached all 16 labs), or build a third red cell (not built).

Fast inserters between labs 1 to 4 matter once the chain carries all five packs: with basic inserters there the 16 labs used 14.6 to 14.8 of each pack a minute on a 60 s technology, with fast inserters 15.9 to 16.0 (maximum 16).

**Adding labs.** A pack put into lab 1 reaches every lab on the chain; a pack put into a later lab never reaches the labs before it, so new pack types enter at lab 1 only. Add labs at the chain's east end: lab (40, -12) with a fast inserter (38, -12) facing west and a small pole (38, -10) (not built). Use fast inserters between labs, and three long-handed inserters side by side wherever the chain lifts over something (one long-handed inserter moves about 1.2 packs/s; not re-measured). The west end is closed: dx -3 and -1 belong to the entry belts.

**Mall: downstream on purpose.** The mall's inserters take from the trunks after every science inserter, so it only gets plates the science left. With AM1 science and the mall filling, the iron trunk was empty between dx 30 and 58 and the mall's gear assembler waited for iron. With AM2 science at full rate (17.9 red and 30.1 green made a minute, every iron plate on the trunk used) the mall's circuit and gear chests kept filling and the science did not slow. Fill rates measured: with AM1 science 13 circuits, 21 inserters, 43 belts and 46 pipes a minute; with AM2 science 23 circuits, 11 inserters, 11 gears, 22 belts and 19 pipes a minute.

The cost of a mall upstream (west of the science, empty chests), measured: with 3.4 iron/s on the trunk the mall took all of it and the science made nothing for 19 game-minutes. At 5.1 iron/s, over 8-minute windows, red and green per minute went 4.3/6.2, 8.4/12.2, 9.4/15.8 (inserter, belt and pipe chests full), 16.2/24.1, 16.5/25.1 (gear chest full), then 18.0/30.0, the full rate, about 44 game-minutes after the supply rose. A wooden chest holds 800 inserters or 1,600 belts, pipes or gears and 3,200 circuits, and all of it comes out of the science's iron first. The `hud` warns "research has not moved for 20 minutes: the labs lack science packs or power" during it. An upstream mall costs about an hour of science from empty; put it downstream.

**Extending east.** Keep these tiles free so both trunks can be extended for later blocks: dy 0 and dy 6 from dx 63 east (the trunks end at dx 62; extend with `fac place transport-belt 63.5,0.5 --to X,0.5` and the same at dy 6.5), and the strip dy 1 to 5 from dx 60 east for the next block's machines. North of the iron trunk everything from dx 38 east is free (the lab row ends at dx 37.5 and the feed belt turns at dx 34). A third belt can run along dy 7, directly south of the copper trunk, from the west edge east: nothing of the block stands there, the standing spots at dy 8 stay usable beside it, and long-handed inserters at dy 5 facing south reach it over the copper trunk (untested). Keep dx -3 and dx -1 free north of dy -3 for the entry belts.

**What limits it.** Red: two cells. Green: four green assemblers; with AM2 they made 30.1/min against the recipe's 30, so the strip and the feed belt keep up. Iron: about 3.4 iron/s for the science at the AM2 rate plus the mall's surplus; 5.1 iron/s ran both, with the mall using the rest. A second copy of the block goes east of dx 63 on the extended trunks and needs its own iron.

**Failure behaviour (all measured).**

- Iron runs dry: 8 game-minutes after the iron stopped arriving, the iron trunk was empty, all 16 labs `missing_science_packs` and 10 assemblers `item_ingredient_shortage`. When iron came back, the block restarted by itself and was back at full rate (18.1 red, 16.3 green made a minute on a 60 s technology, labs using 15.7) within about 5 game-minutes. Fix the iron supply; nothing here needs touching.
- Output backs up: with no research queued all 16 labs said `no_research_in_progress` and every science assembler `full_output` within 3 game-minutes; nothing jammed. With research queued again, labs and assemblers were working again within 3 game-minutes, at the earlier rates. Keep research queued.
- Power drops: at 1.4 MW against 2.37 MW demand (satisfaction 0.59), every lab, inserter and assembler showed `low_power` and the five pack types were used at 9.8 to 11.2 a minute instead of about 16 (60 s technology). With power restored, everything was `working` again with no action.

## Not tested

- Any orientation other than belts running east.
- Red on belt B's left lane; a third red cell; labs beyond 16 at (40, -12); a third belt along dy 7.
- Feeding the block from real smelting blocks and running it on a real power grid; the supply rates above are what arrived on the trunks.
- `fac take` from the mall chests.
- Fast or steel furnaces, and AM2 in the strip and mall assemblers: only the two red and four green assemblers were swapped.
