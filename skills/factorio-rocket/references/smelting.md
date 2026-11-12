# Smelting column: ore and coal on one belt, 24 furnaces, plates onto a trunk (tested)

One belt carries ore on its left (north) lane and coal on its right (south) lane past two rows of 12 stone furnaces, one row on each side of it. Ore comes from a row of 15 electric drills on the ore patch, all on the north side of the belt. Coal comes from the power block's coal belt, which sideloads onto the right lane at the block's west edge. The south row drops plates onto the trunk belt south of it (right lane); the north row drops onto its own belt, which turns south round the east end and sideloads onto the trunk's left lane. The trunk carries on east to the base with iron on both lanes. You feed nothing by hand, not even the first coal: the input inserters fuel the furnaces from the coal lane.

Measured on Factorio 2.1.24, built with the `fac` commands below: **7.50 iron plates/s from 24 stone furnaces** (every furnace 0.313 plates/s), 7.50 ore/s from 15 drills, 0.53 coal/s (32 coal/min) for the 24 furnaces. Power 1.55 MW (1.35 MW of it the 15 drills). 123 `fac place` calls, 4 of them `--to` lines that lay 136 belt tiles. Swapping to steel furnaces in place keeps 7.5 plates/s, but only 12 furnaces then work: one ore lane is the limit. The same column on iron plates makes steel (30 steel/min from 8 stone furnaces, 60/min from 8 steel furnaces), and on stone makes bricks (3.75 bricks/s from one stone lane).

Tested orientation: belts run east, ore patch at the west end, drills north of the ore belt, plate trunk south of the block. Every other orientation is untested.

## Sizing rules (measured)

| Quantity | Stone furnace | Steel furnace |
|---|---|---|
| Ore in, plates out (iron or copper recipe) | 0.3125/s each (measured 0.313) | 0.625/s each (measured 0.625) |
| Electric drills per furnace (0.5 ore/s each) | 0.625 (1 drill per 1.6 furnaces) | 1.25 |
| Furnaces one ore lane (7.5/s) feeds | 24 | 12 |
| Coal per furnace (90 kW, 4 MJ coal) | 1.35/min, 0.0225/s (measured 0.0222/s over 24) | the same per furnace, so half the coal per plate |
| Steel: plates in, steel out | 0.3125 plates/s, 3.75 steel/min | 0.625 plates/s, 7.5 steel/min |
| Bricks: stone in, bricks out | 0.625 stone/s, 0.3125 bricks/s (computed) | 1.25 stone/s, 0.625 bricks/s, needs a fast inserter |

- Drills per lane: **15 electric drills fill a lane** (7.5 ore/s). With 16 the last one stands `waiting_for_space_in_destination`; with 15 none waits and the lane delivers 7.50 ore/s.
- Coal for a full 24-stone-furnace block: 32.4/min, a little more than one electric drill on coal makes (30/min). The coal lane can carry 450/min, so the power block's coal belt has plenty to spare.
- One stone furnace making steel takes exactly what one stone furnace makes in iron plates (0.3125/s), so a steel column of n furnaces needs n iron furnaces of the same kind upstream.

## Diagram

Anchor `A` is the north-west corner of the ore-belt tile in front of the first input inserter, so that tile's centre is (0.5, 0.5). Each character pair is one tile, x from -4.5 (left) to 7.5, then the east end from 21.5 to 30.5. Rows are dy from -4.5 to 5.5. The pattern from dx 0 to dx 8 repeats every 4 tiles up to dx 24.

```
 dy      -4.5 ......-0.5 | 0.5 ............................ 7.5   ...   21.5 .............. 30.5
 -4.5     .  .  .  .  .  | >  >  >  >  >  >  >  >                 >  >  >  >  v               north plate belt, east, curves south at 25.5
 -3.5     p  .  .  .  .  | I  p  I  .  I  p  I  .                 p  I  .  .  v               I: output inserters facing south, p: small poles
 -2.5     D  D  D  .  .  | F  F  F  F  F  F  F  F                 F  F  F  .  v               F: stone furnaces at (2k+1, -2)
 -1.5     D  D  D  .  .  | F  F  F  F  F  F  F  F                 F  F  F  .  v               D: drill at (-3.5, -1.5)
 -0.5     D  D  D  .  .  | i  .  i  .  i  .  i  .                 .  i  .  .  v               i: input inserters facing south
  0.5     >  >  >  >  >  |A>  >  >  >  >  >  >  >                 >  >  >  .  v               ore belt: ore left lane, coal right lane, ends at 23.5
  1.5     .  .  .  ^  .  | i  p  i  .  i  p  i  .                 p  i  .  .  v               feeder ^ sideloads the coal lane; i facing north
  2.5     .  .  .  ^  .  | F  F  F  F  F  F  F  F                 F  F  F  .  v               F: stone furnaces at (2k+1, 3)
  3.5     .  .  p  ^  .  | F  F  F  F  F  F  F  F                 F  F  F  .  v               coal belt from the power block arrives from the south
  4.5     .  .  .  ^  .  | I  p  I  .  I  p  I  .                 p  I  .  .  v               I facing north
  5.5     .  .  .  .  .  | >  >  >  >  >  >  >  >                 >  >  >  >  >  >  >  >  >  > trunk east: right lane south row, left lane north row
```

The drill row (D, 3x3 drills facing south at dy -1.5) continues west every 3 tiles to dx -45.5, with poles at dy -3.5 every 6 tiles. The ore belt runs under them from dx -46.5.

## Entities

| Entity | Offset from A | Direction | Note |
|---|---|---|---|
| transport-belt (ore belt) | (x, 0.5), x = -46.5 .. 23.5 | east | left lane iron ore, right lane coal |
| electric-mining-drill x15 | (-3.5 - 3k, -1.5), k = 0 .. 14 | south | `drops_into` ore belt, `lane: left` |
| small-electric-pole x8 | (-4.5 - 6j, -3.5), j = 0 .. 7 | | drill row power |
| small-electric-pole | (-2.5, 3.5) | | links the block to the grid west of it |
| transport-belt (coal feeder end) | (-1.5, 2.5), (-1.5, 1.5) | north | end the power block's coal belt here, arriving from the south; (-1.5, 1.5) `sideloads` ore belt `lane: right` |
| stone-furnace x12 (south row) | (2k + 1, 3), k = 0 .. 11 | | |
| inserter x12 (south input) | (2k + 0.5, 1.5) | north | `picks_from` ore belt `lane: right` first, `drops_into` furnace |
| inserter x12 (south output) | (2k + 0.5, 4.5) | north | `picks_from` furnace, `drops_into` trunk `lane: right` |
| small-electric-pole x12 | (4j + 1.5, 1.5) and (4j + 1.5, 4.5), j = 0 .. 5 | | the poles at dy 1.5 also power the north input inserters |
| transport-belt (trunk) | (x, 5.5), x = 0.5 .. 30.5 and on east | east | iron on both lanes |
| stone-furnace x12 (north row) | (2k + 1, -2), k = 0 .. 11 | | |
| inserter x12 (north input) | (2k + 0.5, -0.5) | south | `picks_from` ore belt `lane: left` first |
| inserter x12 (north output) | (2k + 0.5, -3.5) | south | `drops_into` north plate belt `lane: left` |
| small-electric-pole x6 | (4j + 1.5, -3.5), j = 0 .. 5 | | |
| transport-belt (north plate belt) | (x, -4.5), x = 0.5 .. 24.5 | east | |
| transport-belt | (25.5, y), y = -4.5 .. 4.5 | south | (25.5, -4.5) is a curve (`turns: right`); (25.5, 4.5) `sideloads` trunk `lane: left` |

## Build order (anchor at 0, 0)

Carry 15 electric drills, 24 stone furnaces, 48 inserters, 27 small poles and 140 transport belts. Ore must lie under dx -48 .. -2, dy -4 .. 0 (the drills' mining areas). The drill row sits on the patch, and the ore belt can run from there to the furnaces at any length. All standing spots are outside the block; `fac walk` finds its own way between them (belts don't block walking).

Place each furnace before its inserters, and lay each belt before the inserters that drop onto it. An inserter placed before its target makes `fac place` answer with the warning `drops_at ... its output lands on the ground`. That warning clears once the target stands: `fac inspect` on the inserter then shows `drops_into` naming its furnace or belt.

Ore belt and drill row:

```sh
fac walk -46.5,3.5 --wait
fac place transport-belt -46.5,0.5 --to 23.5,0.5 --wait 120
fac walk -42.5,-6.5 --wait
fac place electric-mining-drill -42.5,-1.5 --direction south    # drops_into lane: left
fac place electric-mining-drill -45.5,-1.5 --direction south
fac place small-electric-pole -40.5,-3.5
fac place small-electric-pole -46.5,-3.5
fac walk -28.5,-6.5 --wait
for x in -24.5 -27.5 -30.5 -33.5 -36.5 -39.5; do fac place electric-mining-drill $x,-1.5 --direction south; done
for x in -22.5 -28.5 -34.5; do fac place small-electric-pole $x,-3.5; done
fac walk -10.5,-6.5 --wait
for x in -3.5 -6.5 -9.5 -12.5 -15.5 -18.5 -21.5; do fac place electric-mining-drill $x,-1.5 --direction south; done
for x in -4.5 -10.5 -16.5; do fac place small-electric-pole $x,-3.5; done
```

South side: trunk, south row, coal feeder (east to west, since the trunk line leaves you at its east end):

```sh
fac walk 2.5,8.5 --wait
fac place transport-belt 0.5,5.5 --to 30.5,5.5 --wait
fac walk 20.5,8.5 --wait
for k in 9 10 11; do                      # furnace x = 2k+1, inserters x = 2k+0.5
  fac place stone-furnace $((2*k+1)),3
  fac place inserter $((2*k)).5,1.5 --direction north
  fac place inserter $((2*k)).5,4.5 --direction north     # drops_into lane: right
done
for x in 17.5 21.5; do fac place small-electric-pole $x,1.5; fac place small-electric-pole $x,4.5; done
fac walk 11.5,8.5 --wait
# the same loop for k = 5 6 7 8, poles at x 9.5 and 13.5
fac walk 2.5,8.5 --wait
# the same loop for k = 0 1 2 3 4, poles at x 1.5 and 5.5
fac place small-electric-pole -2.5,3.5
fac place transport-belt -1.5,2.5 --direction north   # the power block's coal belt ends here, coming from the south
fac place transport-belt -1.5,1.5 --direction north   # sideloads lane: right (must not say curves)
```

North side: plate belt, its turn and join, then the north row:

```sh
fac walk 2.5,-7.5 --wait
fac place transport-belt 0.5,-4.5 --to 24.5,-4.5 --wait
fac place transport-belt 25.5,-4.5 --to 25.5,3.5 --wait
fac place transport-belt 25.5,4.5 --direction south   # sideloads lane: left of the trunk
fac walk 20.5,-7.5 --wait
for k in 9 10 11; do
  fac place stone-furnace $((2*k+1)),-2
  fac place inserter $((2*k)).5,-0.5 --direction south
  fac place inserter $((2*k)).5,-3.5 --direction south    # drops_into lane: left
done
for x in 17.5 21.5; do fac place small-electric-pole $x,-3.5; done
fac walk 11.5,-7.5 --wait
# the same loop for k = 5 6 7 8, poles at x 9.5 and 13.5
fac walk 2.5,-7.5 --wait
# the same loop for k = 0 1 2 3 4, poles at x 1.5 and 5.5
```

The shell loops are written for a site with positive x; shift every offset to the real anchor and write half tiles out in full (SKILL.md). Power comes from the grid west of the block through the pole at (-2.5, 3.5) and the drill poles.

## Checks after building

- Every drill's `fac place` says `drops_into ... lane: left`. The feeder's last tile says `sideloads ... lane: right`, and (25.5, 4.5) says `sideloads ... lane: left`. If either says `curves`, the tile it points into has no belt behind it: the ore belt must reach at least 1 tile west of the feeder (it starts at the drill row, so this holds), and the trunk must start west of 25.5.
- South input inserters show `picks_from ... lane: right` and north ones `lane: left`. That is only the lane each takes from first; each takes ore and coal as its furnace needs them.
- `fac observe` from (12.5, 8.5) a few minutes in: the ore belt run with `iron-ore` alone on `left` and `coal` alone on `right` (measured: 148 ore, 103 coal); the trunk with `iron-plate` on both lanes. `fac observe` shows only the part of a long belt run inside its view radius, so a run's `tiles`, `fill` and `lanes` describe that part, not the whole belt.
- `fac observe --problems`: nothing. It does not list drills `waiting_for_space_in_destination` on a full belt, so with 16 drills the extra one shows only in `fac inspect`. New furnaces show `no_fuel` for about a minute until the coal lane reaches them.
- `fac inspect` on a furnace: `fuel` holds 5 coal (the inserter tops it up to 5, about 3.7 minutes of burning), `status: working`.
- `fac stats iron-plate` after 2 minutes: `made_1m` about 450.
- Screenshot: ore on the north half of the ore belt, coal on the south half from the feeder eastward; plates on both halves of the trunk east of dx 25.5 and only on the south half west of it; the north belt bends south at dx 25.5.

Mistakes and their symptoms:

| Symptom | Cause | Fix |
|---|---|---|
| Coal on the ore lane, `fac observe` lists two items on `left` | coal feeder put in from the north side, or drills on both sides of the ore belt | the feeder comes from the south side; all drills on the north side |
| Feeder's last tile says `curves` | pointed at a belt tile with nothing behind it | point it at a tile with ore belt behind it |
| `drops_at ... lands on the ground` on an inserter | its furnace or belt is not placed yet | place the target, then `fac inspect` the inserter: `drops_into` names it |
| Furnaces past the 12th stay `no_ingredients` with steel furnaces | one ore lane feeds only 12 steel furnaces | expected; see Extending |
| Bricks: steel furnaces at 0.44 bricks/s, not 0.625 | a yellow inserter moves about 0.88 stone/s, a steel furnace wants 1.25 | fast inserters on the input row |
| `not_plugged_in_electric_network` on a north input inserter | the pole row at dy 1.5 is missing | those inserters are powered from the south row's poles; no pole goes at dy -0.5 |

## Variants measured

All rates are game-time averages over 3 to 6 game minutes after the line had filled, from production statistics.

| Variant | Furnaces fed | Plates/s | Notes |
|---|---|---|---|
| Stone, south row only | 8 | 2.50 | 0.3125 each, coal 0.18/s, 16 drills, 11 waiting |
| Stone, both rows | 16 | 5.00 | |
| Stone, both rows | 24 | 7.50 | every furnace 0.310 to 0.314; a second build gave 7.507 |
| Steel (swapped in place) | 8 | 5.00 | 0.625 each |
| Steel | 16 | 7.52 | ore-limited: furnaces 1 to 6 of each row at 0.625, the 6th of the south row 0.52, the 7th about 0.1, the rest 0 |
| Steel | 24 | 7.50 | the same 12 work; coal 0.275/s |

The swap: `fac mine` each stone furnace, `fac place steel-furnace` at the same (2k + 1, y). `fac inspect` on its inserters at once names `steel-furnace` in `drops_into` and `picks_from`; no drill or inserter keeps a stale target. `fac mine` on a furnace also puts the furnace's coal and ore into your inventory, without listing them in its answer.

Steel column (same geometry, one row of 8 furnaces south of the input belt): the input belt at (x, 0.5) carries iron plates on its left lane and coal sideloaded onto its right lane by the same feeder at (-1.5, 1.5); furnaces at (2k + 1, 3), k = 0 .. 7; inserters at (2k + 0.5, 1.5) and (2k + 0.5, 4.5) facing north; steel belt at (x, 5.5) east; poles at (4j + 1.5, 1.5) and (4j + 1.5, 4.5). `fac observe` shows iron alone on the input's `left` and coal alone on its `right`, steel alone on the output's `right`.

| Column | Input | Output |
|---|---|---|
| 8 stone furnaces, steel | 2.49 iron plates/s | 0.498 steel/s, 29.9 steel/min |
| 8 steel furnaces, steel (swapped in place) | 5.00 iron plates/s | 1.00 steel/s, 60 steel/min |
| 8 steel furnaces, bricks, yellow input inserters | 7.0 stone/s | 3.50 bricks/s (0.42 to 0.46 per furnace, inserter-limited) |
| 8 steel furnaces, bricks, fast input inserters | 7.5 stone/s (the lane) | 3.75 bricks/s (6 furnaces at 0.625, lane-limited) |

Bricks were made on the main block with stone under the drill row. Iron ore left on the lane past the last fed inserter stays at the belt's end and never reaches a furnace.

## Extending, upgrading, limits, failure

- **Limit:** one ore lane, 7.5 ore/s, so 7.5 plates/s whatever the furnaces. Coal takes the other lane. 24 stone or 12 steel furnaces use it all.
- **Which side stays free:** the east end of the ore belt (dx 24 and beyond) and the trunk's east end. Build nothing in column dx 25.5 from dy -4.5 to 4.5 (the north belt's return) or on dy 5.5 east of the block (the trunk). The west end is the ore patch and the coal feeder.
- **Mirrored rows onto one trunk, or two belts:** both rows onto one trunk (north row by sideload onto the left lane, south row by inserters onto the right lane) is the tested way and the better one: one belt to run to the base, each lane at 3.75 plates/s, and assembler inserters on the trunk take from either lane. Measured lane totals: 19,969 (left) and 22,441 (right) plates, the left lower only because the north row was built later; bricks 6,861 and 6,710.
- **A second column onto the same trunk:** a column's plate belt pointing into the side of a trunk tile that has trunk belt behind it puts all its plates on the trunk's near lane, as the north row's belt does at (25.5, 4.5). The lanes never mix items as long as both columns smelt the same ore. A sideloaded lane takes at most 7.5 items/s, and this block already fills each trunk lane to 3.75/s, so a second full block (7.5/s) sideloaded onto one lane would back up to half its rate. Give a second full block its own trunk [untested], or join single-row columns (3.75/s each) one per lane [untested].
- **Steel furnaces:** swap in place, as tested. Same plates (7.5/s), half the furnaces, half the coal per plate. Furnaces past the 12th starve of ore, which is harmless. For bricks in steel furnaces, use fast inserters on the input row.
- **Electric furnaces** would free the coal lane for a second ore lane (15 ore/s, 30 drills) [untested]. **Fast inserters** are not needed for iron or steel (a steel furnace wants 0.625 items/s, a yellow inserter moves about 0.88).
- **Output backs up (tested):** with the trunk end blocked for about 5 game minutes, all 24 furnaces go `full_output`, the ore lane stands still (164 ore) with 5 drills `waiting_for_space_in_destination`, and the coal lane stands still (103 coal). No ore spills onto the coal lane or the reverse. With the trunk end open again the block made 7.07 plates/s in the first 3.7 minutes and 7.5/s after: it restarts by itself.
- **Ore runs dry (tested):** within 4 game minutes every furnace is `no_ingredients`, the trunk empties, and the coal lane stays full and stationary. With the drills back on, 3.75 bricks/s again within 3 minutes.
- **Coal runs dry (tested):** each furnace burns its 5 buffered coal for about 3.7 minutes. At 3.6 minutes all still worked; at 6.9 minutes the working furnaces were `no_fuel`, output had fallen to 75 bricks/min from 225, and the ore lane had backed up (8 drills waiting). Coal back: full rate within 3 minutes, no hand action.
- **Low power (tested):** at 500 kW for a 1.73 MW demand (satisfaction 0.29) the block made 2.44 plates/s, drills and inserters `low_power`, 15 furnaces `no_ingredients`. At full power again 7.48 plates/s. The furnaces burn coal and keep heat, so only the drills and inserters slow down.

## Not tested

- Any orientation other than belts east, drills north of the ore belt, trunk south.
- Copper ore (same recipe time as iron, so the same numbers are expected).
- Stone furnaces on bricks (computed: 12 per stone lane, 3.75 bricks/s).
- A steel column fed from a real iron plate belt. A plate belt with iron on one lane only (a single-row column's trunk) plus coal sideloaded onto its other lane should do it.
- Two plate belts instead of one trunk; a second full block on the same trunk; single-row columns joining one per lane.
- Electric furnaces, fast or long inserters in this block (except fast inserters for bricks), assembling machines downstream.
- A real coal belt from the power block entering at (-1.5, 1.5); the coal feed itself was a stand-in.
