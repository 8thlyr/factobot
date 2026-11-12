# Belts, lanes and inserters

Read this before you lay a belt that more than one machine puts items on. Every rule here was probed on Factorio 2.1.24 in a factobot test world, and every pattern was built there with the `fac` commands shown and checked with `fac inspect`, `fac observe` and a screenshot. Coordinates are for a build around (0, 0); shift them to your site. In fac, a belt's `--direction` is the way items travel, and an inserter's `--direction` is the side it picks up from.

## The rules

A belt has two lanes, `left` and `right` facing the way items travel. On a belt running east the left lane is the north half:

```
          north
  > > > > > > > >    left lane     items travel east
  > > > > > > > >    right lane
          south
```

Each lane holds 4 items a tile and moves 7.5 items/s on a transport-belt (15 for the whole belt). The lanes never mix on their own. Items on a lane move in single file: an item that no machine along the belt takes piles up at the belt's end. A source that keeps dropping one, such as a stone drill or brick furnace beside a plate belt, fills that lane backwards from the end until the machines along it starve. Keep one item on each lane and put two on one lane only on purpose, with something at the end that takes both.

| What | Which lane |
|---|---|
| Inserter dropping onto a belt that crosses in front of it | the far lane |
| Inserter dropping onto a belt running toward or away from it | the right lane |
| Inserter dropping onto a curve | the lane farther from it |
| Inserter taking from a belt that crosses in front of it | the near lane first, then the far one |
| Inserter taking from a belt running toward or away from it | the left lane first, then the right |
| Mining drill (burner or electric) onto a belt crossing in front of it | the near lane |
| Electric drill onto a belt running toward or away from it | the right lane |
| Burner drill onto a belt running away from it / toward it | the right lane / the left lane |
| Drill beside a curve's outer side | the outer lane |
| A belt pointing into the side of a belt with a belt behind it (sideload) | both its lanes go onto the near lane |
| A belt pointing into the side of a belt tile with nothing behind it | that tile turns into a curve; both lanes carry on |
| A belt pointing into the side of an underground entrance or exit | only the lane over the tile's belt half gets on, onto the near lane |
| A belt pointing into another's back, or through a splitter | each lane stays on its side |

An inserter takes only what the machine it feeds uses, so an assembler beside a two-lane belt takes what it needs from either lane.

You don't have to work the lanes out. `fac place` and `fac inspect` on a drill or inserter show `drops_into` with the `lane` its output lands on, and an inserter's `picks_from` shows the `lane` it takes from first. `fac place` on a belt says what it does to the belt it points into: `continues` it, `sideloads` onto one `lane` of it (with `blocked_lane` on an underground belt), or `curves` it; `fac rotate` says the same. A belt that is a curve shows `turns` (left or right) in `fac inspect`. `fac observe` gives every belt run its `lanes`, so two items on one lane show at a glance. And `warnings` in `fac place` says when a drill or inserter would drop an item onto a lane that already carries another within 32 tiles of you, or a drill over two resources would drop both onto a belt. A `--to` line lists no buildings, so place a feeder belt's last tile with plain `fac place` to see `sideloads` or `curves`.

## Two drill rows fill both lanes (tested)

Electric drills on both sides of an ore belt, each row facing the belt. Each drill drops onto its near lane, so the north row fills the left lane and the south row the right one: 8 drills, 4 ore/s, about a quarter of the 15 items/s a transport-belt carries.

```
  y -1.5    [D v][D v][D v][D v]     electric drills facing south: left lane
  y  0.5     >  >  >  >  >  >  >     belt running east, x 0.5 to 12.5
  y  2.5    [D ^][D ^][D ^][D ^]     electric drills facing north: right lane
```

```sh
fac place transport-belt 0.5,0.5 --to 12.5,0.5 --wait
fac walk 6.5,-5.5 --wait
fac place electric-mining-drill 1.5,-1.5 --direction south   # drops_into lane: left
fac place electric-mining-drill 4.5,-1.5 --direction south
fac place electric-mining-drill 7.5,-1.5 --direction south
fac place electric-mining-drill 10.5,-1.5 --direction south
fac place small-electric-pole -1.5,-3.5
fac place small-electric-pole 4.5,-3.5
fac place small-electric-pole 10.5,-3.5
fac walk 6.5,6.5 --wait
fac place electric-mining-drill 1.5,2.5 --direction north    # drops_into lane: right
fac place electric-mining-drill 4.5,2.5 --direction north
fac place electric-mining-drill 7.5,2.5 --direction north
fac place electric-mining-drill 10.5,2.5 --direction north
fac place small-electric-pole -1.5,4.5
fac place small-electric-pole 4.5,4.5
fac place small-electric-pole 10.5,4.5
```

The poles at x -1.5 connect to the grid west of the block. `fac observe` then shows the run with `iron-ore` on both `lanes`. A furnace row feeding a plate belt works the same way through its output inserters, but an inserter drops onto the far lane: the row north of an eastward belt fills the right lane (smelting.md, "Entities": the south row's output inserters onto the trunk).

Only one resource may lie under a row. A drill over the edge of a patch mines both resources and drops both onto its lane; `fac place` warns `it mines iron-ore and stone here`. In the speedrun of 2026-11-04 the agent put an electric drill on stone beside the iron trunk's feed belt, for bricks, and it dropped stone onto the plate lane. Nothing at the trunk's end took stone, so the lane filled with it: 19 minutes later a circuit assembler on the trunk starved for plates, and stone still sat on the lane 40 minutes after the drill went down.

## Merging two belts, one onto each lane (tested)

Two feeder belts point into the sides of a trunk tile that has trunk belt behind it, from opposite sides. Each feeder's items, both its lanes, go onto the trunk's near lane: the north feeder onto the left lane, the south feeder onto the right one.

```
             v        iron feeder running south, x 3.5
             v
  >  >  >  [>]  >  >  >  >    trunk running east, y 0.5: iron on the left lane
             ^
             ^        copper feeder running north: copper on the right lane
```

```sh
fac place transport-belt 0.5,0.5 --to 10.5,0.5 --wait        # the trunk first
fac walk 6.5,-2.5 --wait
fac place transport-belt 3.5,-5.5 --to 3.5,-1.5 --wait
fac place transport-belt 3.5,-0.5 --direction south          # sideloads: lane left
fac place transport-belt 3.5,6.5 --to 3.5,2.5 --wait
fac place transport-belt 3.5,1.5 --direction north           # sideloads: lane right
```

In the test, a chest and an inserter at the far end of each feeder (`fac place wooden-chest 3.5,-7.5`, `fac place inserter 3.5,-6.5 --direction north`, and the same at y 8.5 and 7.5 facing south, with small poles) fed iron and copper; `fac observe` showed the trunk with iron alone on `left` and copper alone on `right`. A sideloaded lane takes at most 7.5 items/s, so a feeder that carries more than that backs up.

**The curve trap.** Point a feeder into the side of a trunk's first tile, with no belt behind that tile, and the tile turns into a curve instead: the feeder's two lanes carry on round the corner as the trunk's two lanes, and nothing sideloads. `fac place` says `curves` and `fac inspect` on the tile says `turns`.

```sh
fac walk 22.5,-3.5 --wait
fac place transport-belt 20.5,0.5 --to 26.5,0.5 --wait
fac place transport-belt 20.5,-5.5 --to 20.5,-1.5 --wait
fac place transport-belt 20.5,-0.5 --direction south   # curves: the tile at 20.5,0.5
fac place transport-belt 19.5,0.5 --direction east     # continues: the tile is straight again
```

The belt behind the tile straightens it, and the feeder then sideloads. To merge two feeders into the very start of a trunk with nothing behind it, point them into that first tile from both sides, and place both feeders' last tiles before items reach them: the first one's `fac place` says `curves`, since the tile curves until the second goes down, and with an input on each side the tile then stays straight and each feeder sideloads its near lane (the second one's `fac place` says `sideloads`).

## Iron on one lane, copper on the other (tested)

Inserters dropping onto a belt from opposite sides fill opposite lanes, each the lane far from it. Here iron goes on from the north (right lane) and copper from the south (left lane).

```
          [iron chest]  y -1.5
            I v         inserter facing north, y -0.5: drops onto the far lane, right
  >  >  >  [>]  >  >  >  >    belt running east, y 0.5
            I ^         inserter facing south, y 1.5: drops onto the far lane, left
          [copper chest] y 2.5
```

```sh
fac place transport-belt 0.5,0.5 --to 10.5,0.5 --wait
fac walk 5.5,-3.5 --wait
fac place small-electric-pole -1.5,-0.5
fac place small-electric-pole 3.5,-0.5
fac place wooden-chest 2.5,-1.5
fac insert 2.5,-1.5 iron-plate 100
fac place inserter 2.5,-0.5 --direction north    # drops_into lane: right
fac place wooden-chest 2.5,2.5
fac insert 2.5,2.5 copper-plate 100
fac place inserter 2.5,1.5 --direction south     # drops_into lane: left
fac place small-electric-pole 3.5,1.5
```

The chests stand in for furnaces or assemblers. A second copper inserter on the iron side would put copper onto the iron lane, and `fac place` says so:

```sh
fac place wooden-chest 5.5,-1.5
fac insert 5.5,-1.5 copper-plate 50
fac place inserter 5.5,-0.5 --direction north
# warnings: it drops copper-plate onto the right lane of the transport-belt at 5.5, 0.5,
# which already carries iron-plate: a lane moves in single file, ...
```

Mine it and put it on the south side. Such a belt serves a row of machines that together use both items (copper cable machines feeding green circuits, gear machines feeding red packs): each inserter takes what its machine needs from either lane. The warning knows what a drill's resources, a chest's contents and a crafter's recipe give, and what lies on the lane now; a furnace that has never smelted and an empty belt tell it nothing, so inspect the lanes again once the line runs.

## Splitting the lanes of a belt (tested)

A belt pointing into the side of an underground entrance lets through only the lane over the half of the entrance's tile that is belt; the lane over the tunnel half stays on the feeder (`blocked_lane`). So a splitter's two outputs, each sideloaded into an entrance from opposite sides, give one belt of each lane's item. Here a belt with copper on its left lane and iron on its right is split into a copper belt (north) and an iron belt (south).

```
                        [U>] .   .  [U>] >   >   >   >    y -1.5: copper only
                         ^                                y -0.5: sideloads the entrance (iron backs up here)
 >   >   >   >   >  [S]  ^                                y 0.5: north output turns north
                    [S]  v                                y 1.5: south output turns south
                         v                                y 2.5: sideloads the entrance (copper backs up here)
                        [U>] .   .  [U>] >   >   >   >    y 3.5: iron only
```

```sh
fac walk 6.5,-4.5 --wait
fac place transport-belt -1.5,0.5 --to 2.5,0.5 --wait
fac walk 6.5,-4.5 --wait
fac place small-electric-pole -2.5,-0.5
fac place wooden-chest -0.5,-1.5
fac insert -0.5,-1.5 iron-plate 100
fac place inserter -0.5,-0.5 --direction north        # iron onto the right lane
fac place wooden-chest -0.5,2.5
fac insert -0.5,2.5 copper-plate 100
fac place inserter -0.5,1.5 --direction south         # copper onto the left lane
fac place small-electric-pole -1.5,1.5
fac place splitter 3.5,1 --direction east
fac place underground-belt 4.5,-1.5 --direction east
fac place underground-belt 7.5,-1.5 --direction east --belt-type output
fac place transport-belt 4.5,0.5 --direction north    # turns: left
fac place transport-belt 4.5,-0.5 --direction north   # sideloads the entrance, blocked_lane: right
fac place transport-belt 8.5,-1.5 --to 11.5,-1.5 --wait
fac walk 6.5,6.5 --wait
fac place underground-belt 4.5,3.5 --direction east
fac place underground-belt 7.5,3.5 --direction east --belt-type output
fac place transport-belt 4.5,1.5 --direction south    # turns: right
fac place transport-belt 4.5,2.5 --direction south    # sideloads the entrance, blocked_lane: left
fac place transport-belt 8.5,3.5 --to 11.5,3.5 --wait
```

The north belt then carries only copper and the south belt only iron: the splitter keeps each lane on its side, and once a feeder's blocked lane is full the splitter sends that item to the other output. An entrance's belt half is its back half and an exit's its front half, so sideloading an exit lets through the other lane.

## Keeping lanes clean

- Decide what each lane carries before you lay a belt, and write it down with the coordinates.
- Check `drops_into.lane` on every drill and inserter you place onto a belt, and read `warnings`.
- Feed each consumer's lane on purpose: an inserter fills the far lane, a drill the near one; to fill the other lane, build on the other side of the belt or sideload it.
- Point a feeder at a trunk tile with belt behind it, and check that `fac place` on its last tile says `sideloads`, not `curves`. The one exception is the first of two feeders merging into a trunk's first tile from both sides, which says `curves` until the second is down; the second must say `sideloads`.
- After a line runs, `fac observe` its belts: a run whose lane lists two items where you planned one is contaminated. Find the machine whose `drops_into` names that lane, move it, then `fac take` the stray items off the belt.
