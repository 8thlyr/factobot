# Processing units and low density structures (tested)

Two blocks make what yellow science and the rocket need most: the processing unit block turns iron plates, copper plates, plastic and sulfuric acid into processing units, and the LDS row turns copper, steel and plastic into low density structures. Both are sized for a launch near 6:20: about 1,700 processing units (667 for 1,000 yellow packs, 720 for the rocket with 4 productivity module 3 in the silo, 200 for the silo, 100 for the modules) and 1,720 low density structures (1,000 yellow, 720 rocket) between the first yellow pack and the launch.

Measured on Factorio 2.1.24, built with the scripts below in test worlds and fed at full rate, over the 10 game minutes before minute 16 and before minute 22 (`fac stats` `made_10m`): **18.0 processing units a minute** and **18.0 low density structures a minute**, which is every machine at full speed (4 processing unit assemblers at 4.5 a minute, 6 LDS assemblers at 3). Behind the processing units: 438 to 448 green circuits, 37.4 to 41 advanced circuits and 1,466 to 1,506 cables a minute. Used: copper 1,093 to 1,113 plates a minute (733 in the processing unit block, 360 in the LDS row), iron 438 to 448, plastic 165 to 172 (75 and 90), steel 36, sulfuric acid 90. The two drew 5,080 to 5,490 kW together (with the test's dozen feeder inserters on the same network): three boilers with their six engines. The processing unit block is 26 assembling machine 2, 78 inserters and 26 poles; the LDS row 6 assembling machine 2, 18 inserters and 3 poles. Together 144 single `fac place` calls, 32 `fac recipe` calls and 12 `--to` lines (316 belt tiles, 16 pipes, 29 poles).

Why it looks like this. A green circuit machine needs 4.5 cables a second and an inserter moves about 0.85, so every cable crosses from its cable machine to the circuit machine through two fast inserters, never on a belt and never through one yellow inserter: a test run's line made 1.7 processing units a minute because basic inserters carried its cable. Two cable machines feed each circuit machine from both sides (C G C G C), and green circuits and advanced circuits share one belt, S, one per lane, which the processing unit assemblers take both from.

Tested orientation: belts running east, the processing unit assemblers facing north. Other orientations are untested.

## Layout

Anchor @ = the west tile of belt S, offset (0, 0). Each character is one tile, x from -4 to 71 and y from -7 to 6; the digit row gives |x| mod 10. Belts run east (`>`).

```
      4321012345678901234567890123456789012345678901234567890123456789012345678901
   -7 #>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>.>>>>>>>>>>>>>>>>>>>#   iron in (x -3..50), processing units out (x 52..70)
   -6 #>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>#================....   copper in (x -3..50), acid in at # (51, -6), acid header
   -5 .....f..l.l..f..l.l..f...f..l.l..f..l.l..f...f..l.l..f...=l..=l..=l..=l.....
   -4 ....cccfgggfcccfgggfccc.cccfgggfcccfgggfccc.cccfgggfccc.uuu.uuu.uuu.uuu.....
   -3 ....cCcPgGgPcCcPgGgPcCcPcCcPgGgPcCcPgGgPcCcPcCcPgGgPcCcPuUuPuUuPuUuPuUuP....   C cable, G green circuit, U processing unit
   -2 ....cccfgggfcccfgggfccc.cccfgggfcccfgggfccc.cccfgggfccc.uuu.uuu.uuu.uuu.....
   -1 .........f.......f...........f.......f...........f......f...f...f...f.......
    0 ....@>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>...   belt S: green right lane, advanced circuits left lane
    1 ..................i.i.....i.i.i.i.....i.i.i.i.....i.i.......................
    2 ..................aaa.ccc.aaa.aaa.ccc.aaa.aaa.ccc.aaa.......................
    3 ..................aAaicCciaAa.aAaicCciaAa.aAaicCciaAa.......................   A advanced circuit
    4 ..................aaaPcccPaaaPaaaPcccPaaaPaaaPcccPaaaP......................
    5 ...................i...i...i...i...i...i...i...i...i........................
    6 ...............#>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>.......................   copper one lane, plastic the other (x 12..48)
```

`f` fast inserter, `l` long-handed inserter, `i` inserter, `P` medium pole, `=` pipe, `#` where a line from elsewhere hands items or acid in, or takes them away.

LDS row, anchor @ = the west column of the first LDS assembler, in its middle row (the assembler's centre is (1, 0)); x from -6 to 25 and y from -4 to 3:

```
      65432101234567890123456789012345
   -4 #>>>>>>>>>>>>>>>>>>>>>>>>>>>>>..   plastic one lane, steel the other (x -5..23)
   -3 #>>>>>>>>>>>>>>>>>>>>>>>>>>>>>..   copper on both lanes: a smelting column's trunk (x -5..23)
   -2 ......f.l.f.l.f.l.f.l.f.l.f.l...
   -1 ......lll.lll.lll.lll.lll.lll...
    0 ......@LlPlLl.lLlPlLl.lLlPlLl...   L low density structure
    1 ......lll.lll.lll.lll.lll.lll...
    2 .......i...i...i...i...i...i....
    3 ......>>>>>>>>>>>>>>>>>>>>>>>>>#   LDS out (x 0..24)
```

## Entities

### Processing unit block (anchor @)

| Entity | Offset | Direction | Note |
|---|---|---|---|
| transport-belt, iron | y -7, x -3 to 50 | east | iron on both lanes; it arrives at (-3, -7) |
| transport-belt, copper | y -6, x -3 to 50 | east | copper on both lanes, 11 plates/s: two smelting columns joined (Feeding it) |
| assembling-machine-2, circuit row | (1 + 4i, -3) for i 0 to 12 | | C G C G C C G C G C C G C: C `copper-cable`, G `electronic-circuit` |
| fast-inserter, copper into C | (x, -5) | north | |
| long-handed-inserter, iron into G | (x - 1, -5), (x + 1, -5) | north | over the copper belt |
| fast-inserter, cable C to G | (g, -4), (g, -2) in each gap between a C and a G | west when the C is west of its G, east when it is east | 10 gaps, 20 inserters |
| fast-inserter, green out of G | (x, -1) | north | `drops_into` belt S, lane right |
| medium-electric-pole | y -3, x 3 to 67 every 4 | | one in every gap; the grid joins any of them |
| transport-belt S | y 0, x 0 to 68 | east | green circuits on the right lane, advanced circuits on the left |
| assembling-machine-2, advanced circuit row | (15 + 4j, 3) for j 0 to 8 | | A C A A C A A C A: A `advanced-circuit`, C `copper-cable` |
| inserter, green into A | (x - 1, 1) | north | picks from belt S |
| inserter, advanced circuits out of A | (x + 1, 1) | south | `drops_into` belt S, lane left |
| inserter, plastic or copper in | (x, 5) | south | under every A and every C |
| inserter, cable C to A | (g, 3) in each gap between a C and an A | west when the C is west, east when it is east | |
| medium-electric-pole | y 4, x 17 to 49 every 4 | | |
| transport-belt, advanced circuit row input | y 6, x 12 to 48 | east | copper on one lane, plastic on the other; they arrive at (12, 6) |
| assembling-machine-2, processing units | (53, -3), (57, -3), (61, -3), (65, -3) | stays north | `processing-unit`: acid port `pipe_at` (0, -2) |
| pipe | (x, -5) | | joins the port to the header |
| pipe, acid header | y -6, x 52 to 67 | | acid arrives at (51, -6) |
| fast-inserter, circuits in | (x - 1, -1) | south | takes green and advanced circuits off belt S |
| long-handed-inserter, processing units out | (x + 1, -5) | south | over the header onto the output belt |
| transport-belt, processing units out | y -7, x 52 to 70 | east | leaves at (70, -7); the iron belt's end at x 50 stays one tile away |

### LDS row (its own anchor @)

| Entity | Offset | Direction | Note |
|---|---|---|---|
| transport-belt, plastic and steel | y -4, x -5 to 23 | east | plastic on one lane, steel on the other |
| transport-belt, copper | y -3, x -5 to 23 | east | copper on both lanes, 6 plates/s: one smelting column's trunk |
| assembling-machine-2 | (1 + 4k, 0) for k 0 to 5 | | `low-density-structure` |
| fast-inserter | (x - 1, -2) | north | copper |
| long-handed-inserter | (x + 1, -2) | north | plastic and steel, over the copper belt |
| inserter | (x, 2) | north | LDS out, `drops_into` lane right |
| medium-electric-pole | (3, 0), (11, 0), (19, 0) | | |
| transport-belt, LDS out | y 3, x 0 to 24 | east | leaves at (24, 3) |

## Build order

Clear ground first: x -6 to 73 and y -10 to 9 for the processing unit block, x -7 to 26 and y -7 to 6 for the LDS row. Craft first: for the block 26 assembling machine 2, 37 fast, 14 long-handed and 27 inserters, 26 medium poles, 233 belts and 20 pipes; for the row 6 assembling machine 2, 6 fast, 6 long-handed and 6 inserters, 3 medium poles, 83 belts. Fast inserters need `fast-inserter` researched: queue it before `processing-unit` finishes.

Save each script to a file and run it with the anchor tile, for example `AX=120 AY=-40 bash pu.sh`. `A dx dy` prints the `fac` coordinate of an offset. Each answer goes to `build.log`; the script prints every `warnings` and stops at the first refused command or failed walk, saying which. In the test the only warnings were machines `not_plugged_in_electric_network` until the pole lines went in; any other warning is a fault to fix before you go on.

```sh
# pu.sh: the processing unit block, anchor AX,AY
set -euo pipefail
LOG=${LOG:-build.log}
f(){ local r; r=$(fac "$@") || { echo "FAILED: fac $*: $r"; return 1; }; echo "fac $*: $r" >>"$LOG"
     local w; w=$(echo "$r" | jq -c '[.result.warnings // empty, .hud.warnings // empty] | flatten | select(length>0)'); [ -n "$w" ] && echo "WARN fac $*: $w"; return 0; }
A(){ awk -v x="$1" -v y="$2" -v ax="$AX" -v ay="$AY" 'BEGIN{printf "%g,%g", ax+x+0.5, ay+y+0.5}'; }
walk(){ fac walk "$1" --wait >/dev/null || { echo "FAILED walk $1"; return 1; }; }

# 1. the belts and the pipe north and south of the rows
walk "$(A -3 -9)"
f place transport-belt "$(A -3 -7)" --to "$(A 50 -7)" --wait     # iron
walk "$(A -3 -9)"
f place transport-belt "$(A -3 -6)" --to "$(A 50 -6)" --wait     # copper
walk "$(A 52 -9)"
f place pipe "$(A 52 -6)" --to "$(A 67 -6)" --wait               # acid header
walk "$(A 52 -9)"
f place transport-belt "$(A 52 -7)" --to "$(A 70 -7)" --wait     # processing units out
walk "$(A 12 8)"
f place transport-belt "$(A 12 6)" --to "$(A 48 6)" --wait       # copper and plastic for the advanced circuits

# 2. the machines, standing on row 0, where belt S goes last
G_ROW=(C G C G C C G C G C C G C)     # x = 1 + 4i, y -3
AC_ROW=(A C A A C A A C A)            # x = 15 + 4j, y 3
last=-1
for i in "${!G_ROW[@]}"; do
  x=$((1 + 4 * i)); c=$((x / 12))
  [ $c -ne $last ] && { walk "$(A $((c * 12 + 6)) 0)"; last=$c; }
  f place assembling-machine-2 "$(A $x -3)"
  if [ "${G_ROW[$i]}" = C ]; then
    f recipe "$(A $x -3)" copper-cable
    f place fast-inserter "$(A $x -5)" --direction north
  else
    f recipe "$(A $x -3)" electronic-circuit
    f place long-handed-inserter "$(A $((x - 1)) -5)" --direction north
    f place long-handed-inserter "$(A $((x + 1)) -5)" --direction north
  fi
  if [ $i -gt 0 ] && [ "${G_ROW[$((i - 1))]}" != "${G_ROW[$i]}" ]; then
    g=$((x - 2)); [ "${G_ROW[$((i - 1))]}" = C ] && d=west || d=east
    f place fast-inserter "$(A $g -4)" --direction $d
    f place fast-inserter "$(A $g -2)" --direction $d
  fi
done
last=-1
for j in "${!AC_ROW[@]}"; do
  x=$((15 + 4 * j)); c=$((x / 12))
  [ $c -ne $last ] && { walk "$(A $((c * 12 + 6)) 0)"; last=$c; }
  f place assembling-machine-2 "$(A $x 3)"
  [ "${AC_ROW[$j]}" = C ] && r=copper-cable || r=advanced-circuit
  f recipe "$(A $x 3)" $r
  f place inserter "$(A $x 5)" --direction south
  if [ $j -gt 0 ] && [ "${AC_ROW[$((j - 1))]}" != "${AC_ROW[$j]}" ]; then
    g=$((x - 2)); [ "${AC_ROW[$((j - 1))]}" = C ] && d=west || d=east
    f place inserter "$(A $g 3)" --direction $d
  fi
done
walk "$(A 59 0)"
for x in 53 57 61 65; do
  f place assembling-machine-2 "$(A $x -3)"
  f recipe "$(A $x -3)" processing-unit      # ports: acid pipe_at (x, -5)
  f place pipe "$(A $x -5)"
  f place long-handed-inserter "$(A $((x + 1)) -5)" --direction south
done

# 3. poles, then belt S
walk "$(A 0 0)"
f place medium-electric-pole "$(A 3 -3)" --to "$(A 67 -3)" --spacing 4 --wait
walk "$(A 50 1)"
f place medium-electric-pole "$(A 49 4)" --to "$(A 17 4)" --spacing 4 --wait
walk "$(A 0 1)"
f place transport-belt "$(A 0 0)" --to "$(A 68 0)" --wait        # belt S

# 4. the inserters on both sides of belt S, from outside the block
last=-1
for i in "${!G_ROW[@]}"; do
  [ "${G_ROW[$i]}" = G ] || continue
  x=$((1 + 4 * i)); c=$((x / 12))
  [ $c -ne $last ] && { walk "$(A $((c * 12 + 6)) -8)"; last=$c; }
  f place fast-inserter "$(A $x -1)" --direction north
done
walk "$(A 59 -8)"
for x in 53 57 61 65; do
  f place fast-inserter "$(A $((x - 1)) -1)" --direction south
done
last=-1
for j in "${!AC_ROW[@]}"; do
  [ "${AC_ROW[$j]}" = A ] || continue
  x=$((15 + 4 * j)); c=$((x / 12))
  [ $c -ne $last ] && { walk "$(A $((c * 12 + 6)) 8)"; last=$c; }
  f place inserter "$(A $((x - 1)) 1)" --direction north
  f place inserter "$(A $((x + 1)) 1)" --direction south
done
echo "processing unit block placed"
```

```sh
# lds.sh: the LDS row, anchor AX,AY (its own anchor)
set -euo pipefail
LOG=${LOG:-build.log}
f(){ local r; r=$(fac "$@") || { echo "FAILED: fac $*: $r"; return 1; }; echo "fac $*: $r" >>"$LOG"
     local w; w=$(echo "$r" | jq -c '[.result.warnings // empty, .hud.warnings // empty] | flatten | select(length>0)'); [ -n "$w" ] && echo "WARN fac $*: $w"; return 0; }
A(){ awk -v x="$1" -v y="$2" -v ax="$AX" -v ay="$AY" 'BEGIN{printf "%g,%g", ax+x+0.5, ay+y+0.5}'; }
walk(){ fac walk "$1" --wait >/dev/null || { echo "FAILED walk $1"; return 1; }; }

walk "$(A -5 -6)"
f place transport-belt "$(A -5 -4)" --to "$(A 23 -4)" --wait     # plastic and steel
walk "$(A -5 -6)"
f place transport-belt "$(A -5 -3)" --to "$(A 23 -3)" --wait     # copper
walk "$(A 0 5)"
f place transport-belt "$(A 0 3)" --to "$(A 24 3)" --wait        # LDS out
walk "$(A 5 5)"
for x in 1 5 9 13 17 21; do
  [ $x -eq 13 ] && walk "$(A 17 5)"
  f place assembling-machine-2 "$(A $x 0)"
  f recipe "$(A $x 0)" low-density-structure
  f place fast-inserter "$(A $((x - 1)) -2)" --direction north
  f place long-handed-inserter "$(A $((x + 1)) -2)" --direction north
  f place inserter "$(A $x 2)" --direction north
done
walk "$(A 0 5)"
f place medium-electric-pole "$(A 3 0)" --to "$(A 19 0)" --spacing 8 --wait
echo "LDS row placed"
```

## Feeding it

| Input | Where | Rate at 18 a minute |
|---|---|---|
| iron plates | west end of the iron belt, (-3, -7), both lanes | 7.3/s (438 to 448 a minute) |
| copper plates | west end of the copper belt, (-3, -6), both lanes | 11/s (about 660 a minute) |
| copper plates and plastic | (12, 6), one lane each (belts.md, "Merging two belts, one onto each lane") | 1.2/s each |
| sulfuric acid | a pipe onto (51, -6), from the north through (51, -7) or by pipe-to-ground (oil.md, "Long pipes") | 1.5/s (90 a minute) |
| LDS row: copper | (-5, -3), both lanes: a smelting column's trunk | 6/s (360 a minute) |
| LDS row: plastic and steel | (-5, -4), one lane each | plastic 1.5/s (90 a minute), steel 0.6/s (36 a minute) |

- **Copper.** The block's copper belt needs 11 plates/s and one smelting column makes 7.5 (smelting.md). Join two columns' trunks with a splitter facing east: one trunk into each of its two inputs, the copper belt on one output, nothing on the other, so all of both trunks goes on (measured: two single-lane belts of about 6.9 plates/s each through a splitter kept the block at 18 a minute). The LDS row takes a third column's trunk whole (6 of its 7.5). The advanced circuit row's 1.2/s comes off the copper that feeds the science, blue and purple, which then needs two columns. So the end of the game needs five copper columns (37.5 plates/s) for the about 27 plates/s (1,600 a minute) the factory uses: each block takes whole trunks, and what a trunk does not use backs up at its end. That is 75 drills and 120 stone furnaces on copper, the fifth column built before the processing unit block (production.md, "Planned factory sizes").
- **Plastic.** The two use 165 to 172 plastic a minute, and with blue and purple the factory uses about 310; the tested advanced oil site makes 78 to 92 (oil.md). Before you build them, bring the oil to 4 refineries and 3 plastic plants (production.md, "Planned factory sizes"; oil.md, "Extending").
- **Acid.** 90 a minute; the tested acid plant makes 570 to 650 (oil.md), so the battery block and this share one acid line.

## Outputs: yellow first, the silo's chests next

Run each output belt past the yellow assemblers and end it at a chest beside the silo site, filled by an inserter from the belt's last tile: the yellow assemblers take what they need first and the chest stocks the rest (tested with an iron chest at each end; an iron chest holds 3,200 processing units or 1,600 low density structures). Three yellow assemblers at 6.4 packs a minute use 12.9 processing units and 19.3 low density structures a minute, so while `rocket-silo` researches about 5 processing units a minute go to the chest; the rest of the 720 each, and the silo's 200, come after the research.

## Checks after building

- `fac recipe` on each processing unit assembler: `ports` acid `pipe_at` is (x, -5), then `fac inspect` shows it `joined_to` that pipe.
- `fac place` answers for the inserters by belt S: green out `drops_into` lane right, advanced circuits out lane left.
- Two minutes after the inputs arrive, `fac stats processing-unit low-density-structure electronic-circuit advanced-circuit copper-cable`: all made in the last minute. After ten minutes `made_10m` is 18 for both (measured at minutes 16 and 22).
- `fac observe --problems` at the block: one or two cable machines of the advanced circuit row at `full_output` is normal, since three of them make more cable than six advanced circuit assemblers use. A circuit assembler with `missing` cable, or a processing unit assembler with `missing` electronic-circuit, means a cable inserter or a copper lane: walk it back (SKILL.md, the stall protocol).
- `fac observe` on belt S: `right: electronic-circuit`, `left: advanced-circuit`. A screenshot shows green circuits on S's south lane and red ones on its north lane.

## Not tested

- Real smelting columns and an acid line feeding it: the test fed the block from chests through loaders and fast inserters, the copper through two belts and a splitter, and the acid from an infinite pipe.
- The yellow assemblers on the output belts; the chests at the ends were tested.
- Any orientation other than belts east, processing unit assemblers north.
