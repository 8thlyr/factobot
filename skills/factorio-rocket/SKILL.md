---
name: factorio-rocket
description: Playbook for building a Factorio factory that launches a rocket through the fac CLI. How to plan the base on an unknown map, keep every production line automatic, check the factory with fac and screenshots, find and fix stalls the way a player does, with references for the opening, base planning, tested layouts, belt lanes, ratios, research, troubleshooting and the endgame. Use when playing factobot toward a rocket launch, or building any factory through fac.
---

# Launching a rocket through fac

You launch a rocket with a raw fish in it. That takes a factory that makes five kinds of science pack and about 2,200 rocket ingredients, on a map you have never seen, over many hours of game time. The game runs in real time and never pauses. You are the only worker and you have two hands, so the factory has to do the work: you build it, you make it run by itself, and you notice and repair what stops. Factorio 2.1.24, base game, peaceful, no enemies.

Two long runs before this playbook reached most of the tech tree and both were ruined the same way: not by a wrong design, but by lines that needed the agent's hands (coal carried to furnaces, plastic carried to a chest, packs carried to the labs), and by stalls nobody looked at for 15 to 40 minutes while the agent built something new somewhere else. One of them inserted 363,000 items by hand and its labs stood empty for 206 of the last 347 minutes.

## The rules, highest first

1. **The factory runs without you.** Ask of every line: if I stood still for an hour, would it keep running? Ore reaches furnaces on belts. Coal reaches furnaces and boilers on a belt lane, never from your inventory. Plates, intermediates, plastic and sulfur reach assemblers by belt, pipe or direct insertion. Every pack reaches the labs by inserter or belt. A chest is a buffer inside a line (something puts in, an inserter takes out) or a shop you take buildings from; it is never where a production line ends. By hand you place buildings, bootstrap (the first 10 red packs, the first cell until its belt arrives, the first boiler's coal chest until the coal belt arrives, 5 coal to start a boiler), and nothing else. If a line must be hand-fed for a while, write it under `HAND` in your notes with the time it runs dry, and replace it before you start the next phase.
2. **A stall comes before everything else.** When the HUD warns, when research has not moved, when a pack you make shows `made_1m: 0`, stop building and run the stall protocol below until the rate is back. Never write "it should recover" and walk away: in the test runs it never did.
3. **Check every build before you leave it.** Read what `fac place` answers, run `fac observe --problems`, take a screenshot and look at it, and wait to see the first product come out the far end. A mistake caught at build time is one command. One unplugged inserter found 28 minutes later cost a test run its blue science for those 28 minutes.
4. **Never hide an answer.** Every `fac` answer says whether it worked, and carries the `hud` with warnings. A script that sends output to `/dev/null` hides the full inventory, the failed walk and the unplugged machine. Print failures, stop loops on the first error, and keep 10 inventory slots free.
5. **Plan the base before you build it, on one site.** Read references/base-plan.md before the first assembler. Plates come to the base on belts and everything is made there, along trunks that can be extended. When a patch runs low, bring the next patch's ore to the same smelters by belt. Production scattered over the map is production you carry.
6. **One item per belt lane, on purpose.** Decide what each lane carries, write it down, and read `drops_into.lane` and `warnings` on everything you place beside a belt. Two items on a lane with nothing taking the second one stops the first. references/belts.md has the rules and tested patterns.
7. **Keep power ahead of the load.** Check `power` on a pole at every expansion and add a boiler with its two engines (1.8 MW) while `capacity_kw` is still more than 1,800 above `demand_kw`. Feed boilers from a coal belt through burner inserters, with 3 coal drills for every 2 boilers: electric coal drills slow down with the network, so an overloaded network mines less coal and spirals into a blackout that coal by hand cannot stop (references/power.md has the block and the recovery).
8. **Size a line before you depend on it.** Before queueing a long technology, count the assemblers that make each pack it needs against references/production.md. One yellow assembler made 3 packs a minute for a technology that needs 1,000.
9. **Never let a lab idle, and build enough labs.** Queue research in batches (references/research.md). Put a technology that needs a new pack at the head of the queue only when that pack is already in the labs.
10. **Before you change or remove anything that runs, find what it feeds.** A recipe change on the only sulfur plant stopped batteries, processing units and yellow science two hours later.

## Notes: your memory

Keep `notes.md` in your working directory and rewrite it after every build. Your context will be cut and summarised during the run, and the summary loses coordinates. Whenever you are unsure what you were doing, read `notes.md` first, then run the factory check. It holds:

- the map: each patch, the water, the oil, with coordinates from `fac map`;
- the base plan: where the trunks run, where each block stands or will stand, what must stay free;
- every block built: its anchor, its standing spots, what each belt lane carries;
- `HAND`: every chest or machine still fed by hand, and when it runs dry;
- open problems, and the next three things to do.

## The factory check

Run it every 10 minutes of game time (the HUD's `time`), after any HUD warning, when you come back from anywhere more than a minute's walk away, and before you queue a long technology. It is five commands and it goes into your notes with the time.

1. `fac research`: the progress against your last note. No movement is a stall.
2. `fac stats` with every pack you make and its key inputs (for example `fac stats automation-science-pack logistic-science-pack chemical-science-pack plastic-bar sulfur engine-unit`): `made_1m` against `made_10m`. Zero, or a drop by half, is a stall, even while research still runs on buffered packs.
3. `fac inspect` on a pole: `power.capacity_kw` against `demand_kw`, and against your last note. Capacity that fell means a boiler lost its fuel.
4. At each block, `fac observe --problems`, then `fac screenshot --zoom 0.5` and look.
5. `HAND` in your notes: anything due to run dry.

Before you leave the base for a far site (oil, a new patch), run the check, fix what it shows, and make sure nothing in `HAND` runs dry while you are away. Run it again when you return.

## The stall protocol

1. Find the last machine of the line that stopped: the pack assembler, or the lab. `fac inspect` it. On an assembler, `missing` names the ingredient it is short of. A lab has no `missing`, only the status `missing_science_packs`: the pack it is short of is the one in `cost.packs` of `fac research TECH --show` (TECH from the HUD's `research`) that its `lab_input` does not hold.
2. Walk that one ingredient back, machine by machine: the inserter that should deliver it (`picks_from`, `drops_into`, `status`), the belt lane it should ride (`fac observe` shows each lane), the machine that should make it, and so on, until you reach the first thing that is wrong: no power, no fuel, a lane full of another item, an empty input, a full output, a wrong recipe, a pipe on the wrong port, a mined-out drill.
3. Fix that one thing where it is. Do not add a second line beside a broken one, and do not hand-feed around it.
4. Stay until the stalled machine shows `working` and its product moves, then note what it was.

`full_output` on a machine means the next step is not taking: the problem is downstream. An ingredient shortage means the problem is upstream. Every lab `working` with pack assemblers at `full_output` means too few labs.

## Looking at the game

`fac screenshot` renders what your screen shows, centred on you, with alt mode on, and prints the PNG's path: open it with your file-reading tool. `--zoom 0.5` shows 120 by 68 tiles (a whole block), the default 60 by 34, `--zoom 2` 30 by 17 (lanes and inserter arms).

- Before you build on a site: trees, rocks, cliffs and water that `fac map` does not list.
- After every build: a yellow plug over a machine no pole reaches, red lightning for too little power, a red fuel icon, a red triangle on a mined-out drill, an assembler with no recipe icon, a gap in a belt, a belt running the wrong way, a pipe that ends open, an inserter turned the wrong way, items of the wrong kind on a lane.
- In the factory check: belts that are empty where they should carry, or packed solid where they should flow.

The picture shows that something is wrong and roughly where; `fac observe` and `fac inspect` give the coordinates and the reason. The result's `area` gives the tiles at the image's corners, so a point's tile is `left + px / (32 * zoom)`, `top + py / (32 * zoom)`. Night is dark; the icons still show.

## Phases

Work through these in order. Each ends on checks you can see; don't start the next on an assumption. "Queue" is the research batch from references/research.md.

| # | Phase | Exit check | Queue |
|---|---|---|---|
| 1 | **Survey and plan**: `fac map`, a walk to the iron patch, screenshots; choose the base site and write the plan (references/base-plan.md) | `notes.md` has the map and the base plan | |
| 2 | **Burner start**: rocks for coal and stone, burner drill and furnace pairs on iron and copper, coal drills into chests (references/opening.md) | `steam-power` and `electronics` researched; each drill `working` | |
| 3 | **Power, first lab, red by machine**: the start of the power block (references/power.md, references/layouts.md "First power"), pole line to the base, lab 1, 10 hand-made red packs, then red cell 1 at its final place (references/science.md) | the lab keeps `working` after the hand-made packs are gone | Q1 |
| 4 | **Electric mining and smelting on belts**: ore rows onto belts, furnace columns with a coal lane, plate trunks into the base, the coal belt to the boilers, burner pairs picked up (references/smelting.md, references/power.md) | plates arrive at the base on the trunks; nothing in the factory takes coal from your hands; `HAND` is empty | |
| 5 | **Red and green on the trunks**: the science block: red cells, green strip, 16-lab chain, the mall downstream (references/science.md) | red and green both `made_1m` at the size you planned; 8 or more labs; you craft buildings from the mall's chests | Q2, then Q3 |
| 6 | **Steel**: a steel column on the trunk | `steel-axe` researched; steel on a belt or in a buffer chest an inserter fills | |
| 7 | **Oil**: pumpjacks, refineries, plastic and sulfur onto a belt to the base (references/oil.md, references/endgame.md) | `oil-processing` researched; plastic and sulfur `made_1m` above 0 and arriving at the base on the belt | Q4 |
| 8 | **Blue**: engines, advanced circuits, blue assemblers, packs by belt to lab one | blue in the labs' `lab_input`; `fac stats chemical-science-pack` steady over 10 minutes | Q5, then Q6 |
| 9 | **Purple**: electric furnaces, productivity modules, rails, purple assemblers, sized from references/production.md | purple in the labs; 3 or more purple assemblers `working` | Q7, then Q8 |
| 10 | **Yellow**: advanced oil with cracking (references/oil.md), lubricant, acid, batteries, processing units, robot frames, low density structures, yellow assemblers | yellow in the labs; 3 or more yellow assemblers `working` | Q9 |
| 11 | **Rocket inputs**, built while `rocket-silo` researches: 4 productivity module 3, lines for processing units, low density structures and rocket fuel into chests beside the silo site, the silo's own ingredients, 1 raw fish | the three stockpiles grow in `fac stats` | |
| 12 | **Silo and launch** | `fac inspect` on the silo shows `rocket_ready` and the fish as payload; `fac launch` accepted | |

Build ahead of research: start each phase's build while the previous batch still runs. Before every phase, make sure the phase before it passes its exit check and the factory check.

## fac habits

- **One turn, many commands.** A turn of thinking plus one shell call costs 10 to 20 s of game time; a `fac` call well under a second. Put a whole block into one shell call, with its checks at the end.
- **Scripts that fail loudly.** Define `f(){ r=$(fac "$@") || { echo "FAILED: fac $*: $r"; return 1; }; echo "fac $*: $r"; }` and chain a build with `&&`, or `set -e`. It prints every answer, so you still read each `drops_into.lane` and the `hud` warnings, and it stops the chain on the first failure. `fac` exits non-zero for a refused command and for a job that ended `failed`, so `fac walk X,Y --wait && ...` stops when the walk found no path. After a script, print what matters: `fac observe --problems`. The shell has no `bc`; write half-tile coordinates out, since `$((y-1)).5` is a tile off for negative y. Never compute a count that can be 0.
- **Straight lines in one call.** `fac place transport-belt X1,Y1 --to X2,Y2 --wait` lays belts or pipes while you walk beside them, and poles with `--spacing 7`. It stops at a tree, a rock or an empty inventory and says where the next one goes: fix that and rerun, since buildings already standing answer `already_there`.
- **Reach is 10 tiles, and `fac walk` stops within 1 tile.** Stand 9 tiles or less from everything you must reach: pick a standing spot outside the block, place everything from it, move on. A reach rejection names a spot to stand on. Never build a one-tile corridor you might be standing in: `fac place` answers `enclosed` when you have shut yourself in, and names what to mine.
- **Craft while you walk.** Queue the next buildings before every walk; a craft job's `eta_tick` says when it is done. Take gears, circuits, inserters and belts from the mall's chests instead of crafting them from plates. Never `sleep` waiting for a craft or for a line to fix itself.
- **Read `fac place`.** It shows `drops_into` and `picks_from` with the belt `lane`, `warnings` for output that lands on the ground or on a lane that carries something else, a belt's `continues`, `sideloads` or `curves`, and the status the machine will have: `not_plugged_in_electric_network` there means no pole reaches it.
- **Rates.** `fac inspect` gives a machine's `rates` per second and a belt's `capacity_per_s`; `fac observe` gives each belt run its `fill` and `lanes`. One inserter moves about 0.83 to 0.88 items/s, one belt lane 7.5; one ore lane feeds 24 stone furnaces from 15 electric drills, and one lab uses 2 packs a minute of each type on a 30 s technology.
- **Read rejections.** They name the limit and usually the fix: the technology that unlocks a recipe, the nearest spot an offshore pump fits, the obstacle that blocks a walk.
- **See a patch before you build on it.** `fac map iron-ore` gives the nearest patch row by row (each row's `y` and the runs of ore tiles), so you place a drill row along an edge without probing tiles. `fac inspect` on an ore tile shows its amount: edge tiles are thin and run out first.
- **`fac stats` is the production window.** Name the items: a plain `fac stats` leaves out what was never made.
- **HUD warnings.** A warning is said once and repeated every 20 s while it holds; `warnings_still_true` counts the ones that still hold but were not repeated in this answer, so a non-zero count means: read the last warnings you were shown.
- **`ports` on fluid machines.** `fac recipe` and `fac inspect` list each port's `pipe_at`; a joined port has `joined_to`, and `problem` when the pipe holds another fluid (references/oil.md).
- **Pipe-to-ground and swaps.** A joined pipe-to-ground shows `paired_with`; `--to` does not lay them. Placing an assembling machine 2 on an assembling machine 1 swaps it in place and answers `replaced`.
- **`--wait` on every `fac mine`.** Without it the next command replaces the job and only the last building comes down. A walk, mine or line job that takes the body from a running job shows `cut_short` {id, kind} in its answer: the earlier job did not finish.

## Fish, underground belts, modules, the silo

- Fish: `fac mine X,Y --wait` on an entity of type `fish` from `fac observe`, standing within 10 tiles; one gives 5 raw fish. Take one at the first power plant and keep it.
- Underground belt: `fac place underground-belt X,Y --direction D` places the entrance; add `--belt-type output` for the exit. Both face the way items travel, at most 4 tiles between for yellow belts.
- Modules: `fac insert X,Y productivity-module-3 --count 4` puts modules into a machine's module slots.
- Silo: `fac insert SILO_X,SILO_Y processing-unit` (and `low-density-structure`, `rocket-fuel`) works by hand, but the silo holds only 104, 54 and 24 at a time, so feed it from chests through fast inserters (references/endgame.md). Payload: `fac insert SILO_X,SILO_Y raw-fish --count 1`. Launch: `fac launch SILO_X,SILO_Y` within 10 tiles, once `rocket.status` is `rocket_ready`; while the rocket still rises it is refused with "still rising", so retry a few seconds later. The launch counts about 19 s after it is accepted, when the rocket reaches space.

## References

- [references/opening.md](references/opening.md): an empty map to the first assembler-made red pack.
- [references/base-plan.md](references/base-plan.md): choosing the site, the trunks, where each block goes, what to keep free, how the base grows. Read it in phase 1.
- [references/layouts.md](references/layouts.md): fac's direction rules, an index of the tested blocks, the first boiler and first red cell, the burner start, inserter habits.
- [references/power.md](references/power.md): steam power on a coal belt with its coal mine, the breaker pole, blackout recovery.
- [references/smelting.md](references/smelting.md): a 24-furnace column, ore and coal on one belt, 7.5 plates/s onto a trunk; steel and bricks.
- [references/science.md](references/science.md): red, green, 16 labs and the mall between the two plate trunks; the entry for blue, purple and yellow.
- [references/oil.md](references/oil.md): fluid ports, the basic and advanced oil site, long pipe-to-ground lines, the battery block.
- [references/belts.md](references/belts.md): belt lanes, which lane inserters and drills fill, sideloading and the curve trap, undergrounds and splitters.
- [references/production.md](references/production.md): machine stats, recipes, ratios per pack, factory sizes per stage, oil and power numbers.
- [references/research.md](references/research.md): trigger technologies, the queue in batches, what to skip, how many labs.
- [references/troubleshooting.md](references/troubleshooting.md): symptoms mapped to `fac inspect` fields and the fix.
- [references/endgame.md](references/endgame.md): oil, blue, purple, yellow, rocket inputs, silo and launch.
