# Steam power fed by a coal belt (tested)

This block is a row of boilers at a shore, fed by one coal belt from a mine of electric drills, with one burner inserter per boiler, one offshore pump and two steam engines per boiler. Coal comes in by belt at the row's west end, power leaves through one breaker pole, and the surplus coal leaves east on the same belt to other coal users (furnace columns). Measured: each boiler adds 1800 to `capacity_kw`, boilers burn 15.5 coal/min per MW of load, and each drill mines 30 coal/min.

Measured on Factorio 2.1.24: `fac inspect` on a pole shows `capacity_kw` 1800 per boiler (3600 with 2 boilers, 7200 with 4). Boilers burn 15.5 coal/min per MW of load (98.6 coal/min at 6.36 MW, 110 coal/min at 7.16 MW, burner inserters included). Each electric drill mines 30 coal/min. 4 drills (120/min) only just cover 4 boilers at full load. 6 drills held a 71% brown-out with no blackout, while 4 drills went into the blackout spiral at 72%. Nobody feeds coal by hand once the block runs. Placements: 11 for the 2-boiler start (pump, 2 boilers, 4 engines, 2 burner inserters, 2 poles), 10 more for boilers 3 and 4, 7 for a 4-drill mine (13 for 6 drills), 5 poles to link the mine and the breaker, and belt lines laid with `--to`.

The breaker pole is part of the design. The factory hangs on ONE pole at P + (7, +8), so that you can cut it off in a blackout by mining that pole. Nothing else may join the factory's poles to the power block's poles.

## Layout

Tested orientation: water to the west, the coal belt runs east, boilers face north and their engines stand north of them. Two anchors: **P**, the offshore pump's centre, and **M**, the mine belt's last tile before the belt leaves the mine. The tested build had M at P + (-1, +25). Any belt route between them works.

Boiler row, one character per tile (`~` water, `P` pump, `B` boiler, `E` steam engine, `=` pipe, `o` small pole, `i` burner inserter, `>` belt):

```
dx         0123456789012345
dy -11   ~~.EEEEEE.EEEEEE.        second engine of each boiler: dy -11 .. -7
dy  -7   ~~.EEEEEE.EEEEEE.
dy  -6   ~~oEEEEEEoEEEEEEo        small poles at dx 0, 7, 14 (one per pair of boilers, plus one)
dy  -2   ~~.EEEEEE.EEEEEE.        first engine: dy -6 .. -2
dy  -1   ~~.BBBBBB.BBBBBB.        boilers 1+2, gap, boilers 3+4; steam leaves north
dy   0   ~~PBBBBBB=BBBBBB. ---->  P = anchor; water passes through the short ends; east end stays free
dy  +1   ~~.oi..i...i..i..        i = burner inserter facing south (takes from the belt); o = mine line pole
dy  +2   ~~>>>>>>>>>>>>>>>>>>>>>> coal belt east; boilers take first, the rest flows on past dx +50
dy  +3   ~~^                      feed belt from the mine (any route), arriving from the south
            (dy +8: mine line pole at dx 1, breaker pole at dx 7)
```

Coal mine, one character per tile (`D` drill, `o` small pole, `>`/`^` belt). The leftmost character is dx -13; M is at dx 0:

```
dy -4     ....o.....o...^     north poles at dx -3 and -9 (one per two drills)
dy -3     ....DDDDDDDDD.^     north row: drills facing south, coal onto the LEFT (north) lane
dy -1     ....DDDDDDDDDo^     o = east pole (0, -1), joins both rows and the power line
dy  0     >>>>>>>>>>>>>M^     mine belt runs east; M = anchor; (+1, 0) turns north toward the boilers
dy +1     ....DDDDDDDDD..     south row: drills facing north, coal onto the RIGHT (south) lane
dy +3     ....DDDDDDDDD..
dy +4     ....o.....o....     south poles at dx -3 and -9
           <- add drill pairs here (west end stays free)
```

Both lanes carry coal and nothing else. The burner inserters stand north of the belt and take the left (near) lane first, then the right lane.

## Entities

Boiler row, offsets from P (pump centre):

| Entity | Offset from P | Direction | Note |
|---|---|---|---|
| offshore-pump | (0, 0) | west (points at the water) | `pipes_to` boiler 1 once it stands |
| boiler 1, 2 | (+2, -0.5), (+5, -0.5) | north | touching; water passes through the short ends |
| pipe | (+7, 0) | | joins boiler 2's east end to boiler 3's west end (place it with boiler 3) |
| boiler 3, 4 | (+9, -0.5), (+12, -0.5) | north | |
| boiler k (k = 1, 2, 3, ...) | (2 + 7·floor((k-1)/2) + 3·((k-1) mod 2), -0.5) | north | boilers 5 .. 13 at dx +16, +19, +23, +26, +30, +33, +37, +40, +44; pipes at dx +14, +21, +28, +35, +42 |
| steam-engine | (boiler dx, -4) and (boiler dx, -9) | north | two per boiler, in a column |
| burner-inserter | (boiler dx, +1) | south | picks from the coal belt at dy +2, drops into the boiler's fuel slot |
| small-electric-pole | (0, -6), (+7, -6), (+14, -6), then every 7 in dx | | in the 1-tile gap after each pair; each one powers the engines on both sides |
| transport-belt (coal) | (0, +2) to (+51, +2) | east | (0, +2) is a curve fed from (0, +3); it carries on to the coal users |
| small-electric-pole (mine line) | (+1, +1), (+1, +8), (+1, +15), (+1, +22) | | (+1, +1) joins (0, -6); the line runs south to the mine's east pole |
| small-electric-pole (breaker) | (+7, +8) | | the only link from the block to the factory; mine it to cut the load |

Coal mine, offsets from M (mine belt's east end tile):

| Entity | Offset from M | Direction | Note |
|---|---|---|---|
| transport-belt | (-13, 0) to (0, 0) | east | (+1, 0) faces north and turns the coal toward the boilers (`turns: left`) |
| electric-mining-drill, north row | (-2, -2), (-5, -2), (-8, -2), then every 3 west | south | `drops_into` lane `left` |
| electric-mining-drill, south row | (-2, +2), (-5, +2), (-8, +2), then every 3 west | north | `drops_into` lane `right` |
| small-electric-pole, east | (0, -1) | | 2.8 tiles from the last mine line pole at M + (+2, -3) |
| small-electric-pole, north | (-3, -4), (-9, -4), then every 6 west | | each powers two drills |
| small-electric-pole, south | (-3, +4), (-9, +4), then every 6 west | | |

## Build order

Coordinates below put P at (0.5, 0.5) and M at (0.5, 0.5); shift both to your site, keeping the offsets. With water to the west, `fac place offshore-pump` names the spot. Place the pump first and anchor everything else on the pump's centre.

Pump. In the tested build you stood at P + (5, 0), the tile boiler 2 takes later. The standing spot S1 below is 7 tiles from the pump, so it works too.

```sh
fac place offshore-pump 0.5,0.5 --direction west
```

What `fac place offshore-pump` answers at a wrong spot (tested; the pump fits only at P facing west; positions shown with P at (0.5, 0.5)):

```
can't place offshore-pump at 0.5, 0.5: an offshore pump goes on the shore, with its direction pointing at the water; the nearest place it fits is 0.5, 0.5 facing west     (right spot, --direction east)
can't place offshore-pump at -0.5, 0.5: ... the nearest place it fits is 0.5, 0.5 facing west     (one tile out on the water, --direction north)
can't place offshore-pump at 9.5, -3.5: an offshore pump goes on the shore, with its direction pointing at the water; it fits nowhere within 4 tiles of there that you can reach     (9 tiles inland)
```

Standing spot S1 = P + (5, +5), south of the coal belt: boilers 1 and 2, their inserters, first engines, the coal belt and the mine line.

```sh
fac walk 5.5,5.5 --wait
fac place boiler 2.5,0 --direction north            # pipes_to: offshore-pump
fac place burner-inserter 2.5,1.5 --direction south # drops_into boiler; picks_at the belt tile (warning until the belt is down)
fac place boiler 5.5,0 --direction north            # pipes_to: boiler
fac place burner-inserter 5.5,1.5 --direction south
fac place steam-engine 2.5,-3.5 --direction north
fac place steam-engine 5.5,-3.5 --direction north
fac place transport-belt 0.5,2.5 --to 51.5,2.5 --direction east --wait
fac walk 5.5,5.5 --wait      # the line job leaves you at its far end, and a body standing on a belt rides it
fac place small-electric-pole 1.5,1.5 --to 1.5,22.5 --spacing 7 --wait
fac walk 5.5,5.5 --wait      # this line can end with you on the coal belt at dy +2 (tested: carried 35 tiles east)
```

If a line job leaves you on a belt, the HUD warns "you are standing on a transport-belt". Walk back to a standing spot after every line job anyway.

Standing spot N = P + (5, -13), north of the engines. Walk round the east end of the row, because the west side is water.

```sh
fac walk 5.5,-12.5 --wait
fac place steam-engine 2.5,-8.5 --direction north
fac place steam-engine 5.5,-8.5 --direction north
fac place small-electric-pole 0.5,-5.5
fac place small-electric-pole 7.5,-5.5
```

Mine, with M at (0.5, 0.5). The coal belt from the mine is two lines in the tested build: the mine belt west to east, then the feed from M + (1, 0) north to the boiler belt's first tile. A line's first tile must be in build reach when you start it, so walk to the east spot before each line: spot N is 38 tiles from M, and the first line leaves you at its west end.

```sh
fac walk 4.5,-1.5 --wait                          # east spot, M + (4, -2)
fac place transport-belt 0.5,0.5 --to -12.5,0.5 --direction east --wait
fac walk 4.5,-1.5 --wait                          # back from the west end of the mine belt
fac place transport-belt 1.5,0.5 --to 1.5,-21.5 --direction north --wait   # with M at P + (-1, +25) this ends at P + (0, +3)
fac walk -3.5,-6.5 --wait                         # north spot, M + (-4, -7)
fac place electric-mining-drill -1.5,-1.5 --direction south   # drops_into lane: left
fac place electric-mining-drill -4.5,-1.5 --direction south
fac place small-electric-pole -2.5,-3.5
fac place small-electric-pole 0.5,-0.5
fac walk -3.5,7.5 --wait                          # south spot, M + (-4, +7); walk finds the way round
fac place electric-mining-drill -1.5,2.5 --direction north    # drops_into lane: right
fac place electric-mining-drill -4.5,2.5 --direction north
fac place small-electric-pole -2.5,4.5
```

Drills 5 and 6, from M + (-8, -7) and M + (-8, +7):

```sh
fac walk -7.5,-6.5 --wait
fac place electric-mining-drill -7.5,-1.5 --direction south
fac place small-electric-pole -8.5,-3.5
fac walk -7.5,7.5 --wait
fac place electric-mining-drill -7.5,2.5 --direction north
fac place small-electric-pole -8.5,4.5
```

First start, with everything empty: the drills need power before any coal reaches the belt. Tested: 5 coal by hand into boiler 1 powered the drills. 15 s later `capacity_kw` read 1800, and at the next look, 50 s after the insert, the belt's coal had reached both boilers and it read 3600 (P back at (0.5, 0.5) from here on):

```sh
fac walk 5.5,5.5 --wait
fac insert 2.5,0 coal 5
```

Breaker and load. The factory hangs on ONE pole at P + (7, +8), joined only to the mine line pole at P + (1, +8). Wire the factory from this pole only, and let no other pole join the factory's poles to the power block's poles; otherwise mining the breaker no longer cuts the load in a blackout. It is in reach from S1:

```sh
fac place small-electric-pole 7.5,8.5     # then wire the factory from this pole only
```

Extend to boilers 3 and 4 from S2 = P + (10, +5) and N2 = P + (10, -13) (tested):

```sh
fac walk 10.5,5.5 --wait
fac place pipe 7.5,0.5                              # pipes_to: boiler (boiler 2)
fac place boiler 9.5,0 --direction north            # pipes_to: pipe
fac place burner-inserter 9.5,1.5 --direction south
fac place steam-engine 9.5,-3.5 --direction north
fac place boiler 12.5,0 --direction north
fac place burner-inserter 12.5,1.5 --direction south
fac place steam-engine 12.5,-3.5 --direction north
fac walk 10.5,-12.5 --wait
fac place steam-engine 9.5,-8.5 --direction north
fac place steam-engine 12.5,-8.5 --direction north
fac place small-electric-pole 14.5,-5.5             # power: capacity_kw 7200 a few seconds later
```

The new boilers fuel themselves from the belt: the burner inserters arrive with a little wood energy, enough to take their first coal.

## Checks after building

- `fac inspect` on boiler 1: `pipes_to` lists `offshore-pump`, `boiler` and `steam-engine`. Boiler 3: `pipe` and `boiler`. Each first engine: `boiler` and the engine behind it.
- `fac inspect` on a boiler or engine shows `ports`; every water and steam port that should be used has `joined_to`.
- `fac inspect` on any pole of the block: `capacity_kw` is 1800 × boilers (3600, then 7200 in the tested build). A lower number means a boiler has no coal or its engines have no pole.
- `fac inspect` on each burner inserter: `drops_into` the boiler, `picks_from` lane `left` of the belt. Each drill: `drops_into` lane `left` (north row) or `right` (south row).
- `fac observe` near the boilers: the coal belt runs show `coal` on both `lanes` and nothing else. In steady state with 6 drills and coal taken at the belt's end: the boiler belt run `fill` 0.93 (left 124, right 142 coal), feed 0.61, mine belt 0.34.
- `fac observe --problems` at the row: empty under load. It does not list boilers at `full_output` under light load or drills `waiting_for_space_in_destination` on a full belt; both are healthy (the engines don't need more steam, and the belt is a full buffer).
- The `hud` `warnings` of every `fac` answer list machines in view with a warning icon and low power on a network in view.
- Screenshot: one pole in each gap between boiler pairs at engine height, the pipe in the gap at the boilers' south row, a burner inserter under the middle of each boiler, coal on the belt under the inserters.

Mistakes made or foreseeable, with the fix:

| Symptom | Cause | Fix |
|---|---|---|
| Engines `no_input_fluid` with no `power` field; `capacity_kw` 0 on the pole | Pole in the inserter row: tested at P + (3, +1), and both first engines stayed on no network | Poles at (7j, -6) in the gaps. Boilers that all touch leave no tile from which a small pole reaches an inner column's first engine, so build them in pairs with a pipe in the gap |
| An unplugged engine says `no_input_fluid`, not `not_plugged_in_electric_network` | It shows the plug status only once steam reaches it | Read `capacity_kw` on a pole after the boiler runs; it must rise by 1800 per boiler. An engine placed where no pole reaches answers with the warning "no electric pole reaches it yet" |
| Reach errors right after a `place ... --to` near the boilers | The line job left you on the coal belt, which carried you east (tested: from P + (3, +2) to P + (35, +2) in under 30 s); the HUD warns "you are standing on a transport-belt" | `fac walk` back to a standing spot after every line job |
| One boiler `no_fuel`, its burner inserter `no_fuel` too, coal on the belt in front of it | The inserter's own fuel was emptied: a dry burner inserter never moves (tested) | `fac insert X,Y coal 1` into the inserter, not the boiler |
| Boiler shows `no_fuel` but capacity is still there | The fuel slot is empty while the boiler burns its last piece | Look again 30 s later; worry only if `capacity_kw` falls |
| A drill drops onto the wrong lane or the ground | Drill row facing the wrong way | North row faces south, south row faces north; read `drops_into.lane` |
| Coal for the furnaces taken before the boilers | Furnace takeoff upstream of the boilers | Coal users go downstream (east) of the last boiler slot, past dx +50 |

## Extending, upgrading, limits, failure

Extending the boiler row: the east end stays free. Boilers 5 to 13 go at the dx offsets in the table, in pairs, with a pipe in each gap and a pole at (gap dx, -6). Keep the strip dx +14 to +50, dy -12 to +1 empty: no belts, poles or furnaces there. The coal belt at dy +2 already runs through it. For an odd last boiler, put its east pole at (boiler dx + 2, -6) and move it when the boiler that makes the pair arrives. One pump gives 1200 water/s (`get_pumping_speed()` 20/tick) and a boiler takes 6 water/s (one water makes ten steam; the 60/s is steam), so one pump serves 200 boilers: one pump is enough for every boiler you will build. Only 4 were tested. Each boiler needs 27 coal/min at full load. A burner inserter moved 49 coal/min off the belt into a chest (measured), so one per boiler is plenty. One belt lane carries 450 coal/min (16 boilers) and the whole belt 900/min (33 boilers), shared with whatever burns coal downstream.

Extending the mine: the west end stays free. Add drill pairs at M + (-11, ∓2), M + (-14, ∓2) and so on, with poles every 6 tiles at dy ∓4, and lengthen the belt west. Use 3 drills per 2 boilers: 20 drills for 13 boilers. A row of 10 drills puts 5 coal/s on its lane, under the 7.5/s a lane carries. Only coal may lie under the drills: one at the patch edge over stone puts stone on the coal lane, and nothing downstream takes it.

Coal users downstream: the belt continues east past the last boiler slot. The boilers are upstream, so their inserters take coal first and the furnaces get what is left. Tested with takers at the belt's end that could take 98 coal/min: with 4 drills (120/min) and 6.36 MW load the boilers kept 4 or 5 coal each and the end took 28 coal/min. With 6 drills it took 47 coal/min. In the overload test the last boiler starved first and the first boiler last. A splitter that hands the furnaces half the coal would remove that priority; it is untested.

End of the belt with nobody taking coal (tested): the coal stops at the last tile and the belt fills backwards at 8 coal per tile (287 coal on 36 tiles). Once it is full back to the mine, the drills show `waiting_for_space_in_destination` in `fac inspect` and mine only what the boilers burn. The boilers never go short, and the full belt is the block's buffer: 73 belt tiles held 540 coal, 5 minutes of 4 boilers at full load. Nothing spills and nothing breaks.

Upgrading: none of this has a tier. More power means more pairs of boilers (one pump is enough for every boiler you will build; only 4 were tested) and more drills. Steel furnaces downstream use the same coal. Productivity modules or mining productivity research raise drill output; every number here is without mining productivity. Fast inserters are not needed.

Measured rates (2 boilers, then 4; "used" from `fac stats coal` and production statistics):

| Load (demand_kw on a pole) | Boilers | Drills | Coal used/min | Coal mined/min | Coal left for the belt's end |
|---|---|---|---|---|---|
| 360 kW (drills only) | 2 | 4 | not measured | 120 until the belt filled (7 min) | belt full, drills waiting |
| 6360 kW | 4 | 4 | 98.6 | 120 | 28/min |
| 6540 kW | 4 | 6 | 102 | 180 | 47/min, belt filling |
| 7160 kW | 4 | 4 | 110.4 | 120 | 13/min |
| 10176 kW asked, 7200 given (satisfaction 0.71) | 4 | 6 | 107 | 132 | 26/min, stable for 6 min |
| 9984 kW asked, 7200 given (satisfaction 0.72) | 4 | 4 | falls | falls | blackout after 8 min |

Starved (coal stops while the drills keep their power): tested. With the mine's pole link cut, the drills stopped. Under 6 MW the belt and the boilers ran dry within 2 game minutes, and `capacity_kw` fell to 0. Each burner inserter kept 1 coal in its own fuel slot. Once the drills had power again and coal came back on the belt, the row restarted by itself: at the next look, under 2 game minutes later, `capacity_kw` was back at 7200 under the same 6 MW load.

Underpowered, the dangerous loop (the drills on the boilers' network): tested. The drills slow with the network's satisfaction, so more load than capacity also cuts the coal supply. With 4 drills on 4 boilers, 9.98 MW asked of 7.2 MW gave satisfaction 0.72, so the drills could mine at most 0.72 × 120 = 86 coal/min while the boilers burned 108/min. The belt drained, and `capacity_kw` fell to 5400 within 1 minute, 3600 after 2.5 minutes and 1800 after 4.5 minutes, then flickered and reached 0 after 8 minutes. With 6 drills (1.5 per boiler) the same overload held at 0.71 for 6 minutes: the drills still mined 132 coal/min against 107/min burned. By the same arithmetic (not a separate test), one drill per boiler starts the spiral below 90% satisfaction, and 1.5 per boiler only below 60%.

Recovery from a blackout (tested exactly in this order):

1. `fac inspect` any pole: `capacity_kw` 0 (or flickering 0 to 1800), `demand_kw` above it; `fac observe --problems` shows boilers `no_fuel` and drills `no_power`.
2. Walk to S1 (P + (5, +5)) and mine the breaker: `fac mine 7.5,8.5 --wait`. The factory is now off and only the coal drills (360 kW for 4) stay on the boilers' network.
3. `fac insert 2.5,0 coal 5` into boiler 1.
4. Wait about 70 s. Tested: `capacity_kw` read 1800 after 10 s, 3600 after 20 s, 5400 after 30 s and 7200 after 40 s, and all four boilers held coal after 70 s. If a burner inserter shows `no_fuel`, `fac insert X,Y coal 1` into it.
5. Remove the cause: build boilers until `capacity_kw` exceeds the factory's demand by at least 1800, and drills to 1.5 per boiler. Then `fac place small-electric-pole 7.5,8.5`. The answer at that instant can show a surge (tested: capacity 3420, demand 8460, satisfaction 0.4); `fac inspect` it again a few seconds later (it read 7200 and 6360, satisfaction 1). If satisfaction stays below 1, mine the breaker again.

Without step 2, recovery fails. Tested: 5 coal in boiler 1 with the 10 MW load still connected gave 1800 kW for a few seconds, then 0 again, while the drills crawled.

Prevention: burner inserters on every boiler (they keep their own coal through a blackout), 3 drills per 2 boilers, a full belt as buffer (coal users downstream, so the boilers always see a full belt first), one breaker pole between the block and the factory, and a new pair of boilers before the load reaches the last boiler's worth of capacity.

Rules of thumb:

| Quantity | Value | Source |
|---|---|---|
| Power per boiler (2 engines) | 1.8 MW: `capacity_kw` 1800 per boiler | measured |
| Boilers for X MW | ceil(X / 1.8) + 1 spare; engines = 2 × boilers | from the above |
| Coal per MW | 15.5 coal/min (0.26/s) | measured at 6.36 and 7.16 MW |
| Coal per boiler at full load | 27 coal/min (0.45/s) | 110/min for 4 at 7.16 MW |
| Coal drills per boiler | 1.5 (1 is the bare minimum: 120 mined against 110 burned) | measured, spiral test |
| Burner inserters per boiler | 1 (one moves 49 coal/min) | measured |
| Boilers per offshore pump | one pump is enough for every boiler you will build (200 by water); only 4 tested | game data |
| Belt buffer | 8 coal per tile | measured |
| `fac inspect` reading that means "add a boiler now" | `demand_kw` above `capacity_kw` − 1800 (less than one boiler spare). `satisfaction` below 1 is already the spiral with 1 drill per boiler. `capacity_kw` below 1800 × boilers means a boiler lost its coal | measured readings |

## Not tested

- Any orientation other than water west, belt east, engines north. Water to the north, south or east needs every offset rotated; none was built.
- Boilers 5 and up (4 boilers built); one pump is enough for every boiler you will build. Pipe and pole positions for boilers 5 to 13 follow the tested pattern.
- A splitter that sends coal to the furnaces, a splitter priority setting, and an underground crossing for the feed belt.
- Real furnace columns downstream: coal taken at the belt's end stood in for them, and the factory load was radars on the breaker.
- A burner drill or chest buffer to restart the mine without hand coal.
- The pump placed from S1 (it was placed from P + (5, 0) before the boilers).
- More than 6 drills, and a patch edge with stone under a drill.
