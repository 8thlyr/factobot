# Research plan

Read this when you queue research. Source: `research/tech-tree.md` (Factorio 2.1.24 data).

## How `fac research` behaves

- `fac research TECH` queues TECH and, before it, every prerequisite that is neither researched nor queued, in dependency order, as the game's tech screen does. The queue holds 7: when TECH and its missing prerequisites don't fit, nothing is queued and the message says how many slots it takes.
- Queue the next pack's technology directly (for example `fac research chemical-science-pack` once oil is unlocked) rather than listing every step; check the resulting order with `fac research`.
- Trigger technologies can't be queued. They finish by themselves when their condition is met; queueing anything that needs an unfinished one queues nothing and names the trigger (make 10 copper-plate in a machine (smelting), extract crude-oil with a pumpjack, and so on).
- `fac research TECH --cancel` removes a technology and every queued technology behind it that depends on it. Progress on a cancelled technology is kept.
- `fac research` with no argument shows the current research, its progress and the queue. Use it as the research check at every phase exit.

## Trigger technologies

| Technology | Fires when | Unlocks |
|---|---|---|
| `steam-power` | 50 iron plates smelted | pipe, pipe-to-ground, offshore pump, boiler, steam engine |
| `electronics` | 10 copper plates smelted | copper cable, electronic circuit, inserter, lab, small pole |
| `automation-science-pack` | 1 lab crafted | red pack recipe |
| `steel-axe` | 50 steel plates smelted | hand mining twice as fast |
| `oil-processing` | a powered pumpjack extracts crude | refinery, chemical plant, basic oil processing, solid fuel |

## Queue in batches

Issue each batch as one burst of calls when its condition holds: issue as many as fit (the queue holds 7, the current one included), then top up with the rest as the queue drains. (opt) marks optional technologies that pay for themselves.

| Batch | Issue when | Technologies, in issue order |
|---|---|---|
| Q1 | First lab powered and holding 10 hand-crafted red packs | `automation`, `electric-mining-drill`, `logistic-science-pack`, `steel-processing`, `logistics` |
| Q2 | Q1 down to 1 or 2 technologies | `automation-2`, `research-speed-1` (opt), `engine`, `fluid-handling`, `oil-gathering`, `advanced-material-processing`, `electric-energy-distribution-1` |
| Q3 | Q2 down to 1 or 2 technologies; go place a pumpjack meanwhile | `radar`, `research-speed-2` (opt), `toolbelt` (opt), `logistics-2`, `railway`, `concrete`, `solar-energy` |
| Q4 | `fac research oil-processing --show` says researched (a pumpjack `fac inspect` shows `working` with `crude-oil` in `fluids`; endgame.md) | `plastics`, `advanced-circuit`, `sulfur-processing`, `chemical-science-pack`, `battery`, `modules`, `productivity-module` |
| Q5 | Q4 down to 1 or 2, while building refinery, red circuits and blue | `speed-module`, `flammables`, `electric-energy-accumulators`, `mining-productivity-1` (opt, skip if blue is nearly ready) |
| Q6 | First blue packs reach the labs | `advanced-material-processing-2`, `production-science-pack`, `processing-unit`, `productivity-module-2`, `speed-module-2`, `advanced-oil-processing`, `lubricant` |
| Q7 | Q6 down to 1 or 2; build purple now | `electric-engine`, `robotics`, `low-density-structure`, `utility-science-pack`, `rocket-fuel` |
| Q8 | First purple packs reach the labs; yellow still being built | `productivity-module-3`, `speed-module-3` |
| Q9 | Yellow packs flowing (accepted as soon as its prerequisites are queued) | `rocket-silo` |

The queue is first in, first out, and labs work only on its head. A red-only technology at the head holds back every green technology behind it, and labs starved of red stall the whole queue. So `logistic-science-pack` comes right after `electric-mining-drill`: its recipe gates every green assembler you place. `radar` is needed only by `rocket-silo`, so it waits for Q3. `fast-inserter` (opt) goes in whenever a slot is free and one inserter has to move more than about 0.85 items/s; the science block needs it for the fast inserters between labs 1 to 4 once all five packs flow (science.md). In a test run with the older order (`logistics` and `steel-processing` ahead of `logistic-science-pack`, then `radar` and `fast-inserter` ahead of `automation-2`), the two red techs took 13 minutes on a starved red supply before `logistic-science-pack` started, and the labs then spent 5 more minutes on radar and fast inserter while green packs waited. A second run with the same order repeated it: `logistic-science-pack` started only at 23:32, and 52 green packs sat in chests from 31:16 to 35:41 behind `radar` and `fast-inserter`.

Keep Q2's order: `electric-energy-distribution-1` (3,600 lab-s) goes after `oil-gathering`. In a test run `fluid-handling` and `oil-gathering` were rejected because `engine` wasn't queued yet; re-added a minute later, they landed behind `electric-energy-distribution-1`, which took 10 minutes on six labs, and `oil-gathering` was still at 95% at 60:00. After any rejection, `fac research` shows the order; `--cancel` the technology that jumped ahead and queue it again at the end.

Hard check, as soon as the Q2 calls return. `fac research` prints `queue` as names, the current technology first. `oil-gathering` must be in it, ahead of `electric-energy-distribution-1` if the poles are in it too. With Q1 still holding 1 or 2, the 7 slots take only the first 5 or 6 of Q2, so the last calls (`electric-energy-distribution-1`, and `advanced-material-processing` too when Q1 holds 2) reject with `has 0 free; nothing was queued`. That is expected: once `fac research` shows fewer than 7 in `queue`, issue them again in Q2's order, the poles last. `fac research oil-gathering` queues any of `automation-2`, `engine` and `fluid-handling` it still needs ahead of itself, so it rejects only when it is already queued or researched, or when the queue has no room for it and those. Run the cancel only when the poles sit earlier than `oil-gathering`, or when `oil-gathering` is missing and the poles are already in `queue`:

```
fac research electric-energy-distribution-1 --cancel
fac research oil-gathering
fac research electric-energy-distribution-1
```

Skip a call that rejects because that technology is already researched or already in the queue. A call that rejects with `nothing was queued` for slots waits until the queue drains, then runs again in the same order. Then run `fac research` again. The pass is `oil-gathering` in `queue`, ahead of the poles once they are in it. Cancelling the poles drops technologies behind them that depend on them. Q2 has none.

If `oil-processing` fires while the tail of Q3 (`railway`, `concrete`, `solar-energy`) still has more than about 10 minutes left and green packs are short, cancel those three, queue Q4, and re-queue them in Q5.

## Keeping the labs busy

Labs work only on the head of the queue, and a lab needs every pack its technology uses. So the order of the queue decides whether labs run:

- A technology that needs a pack you don't make yet goes to the head only once that pack sits in a lab's `lab_input`. Until then keep a technology whose packs already flow at the head: in a test run, blue technologies queued ahead of red and green ones left every lab idle for 5 minutes while the blue line was still broken.
- While the next pack's block is being built, queue the cheap technologies of the packs you have (the ones marked opt, `toolbelt`, `logistics-2`, `railway`, `concrete`, `solar-energy`), so the labs never wait for a build.
- Queue `lubricant` together with `advanced-oil-processing`: a refinery on advanced processing stops when its heavy oil has nowhere to go.
- Queue a purple technology the moment the first purple pack is in a lab, and the same for yellow. A test run made 78 purple packs and never queued anything that used them.
- Research running does not prove every pack line runs. Labs live for a long time on buffered packs, and a technology that needs only red and green hides a dead blue line: check each pack's `made_1m` in `fac stats` in every factory check.

Required total: 44 technologies, 224,425 lab-seconds at lab speed 1. Packs: red 5,960, green 5,785, blue 3,350, purple 1,600, yellow 1,000. `rocket-silo` alone is 1,000 units of 60 s with all five packs.

## Skip

Military of every kind, gun turret, stone wall, heavy armor, car, construction and logistic robotics, worker robot speed, beacons, circuit network, research speed 3 and above, assembler 3. Peaceful mode and fac's lack of blueprints, ghosts and driving make them worthless here. Accumulators, solar panels and radars are silo prerequisites to research, never to build.

## How many labs

Labs needed to keep up with a pack supply of R units per second: `L = R × T / S`, with T the seconds per unit of the current technology and S the lab speed (1, 1.2 after `research-speed-1`, 1.5 after `research-speed-2`). Measured in the science block: one lab at speed 1 uses 2 packs a minute of each type on a 30 s technology, and the block's AM2 red (18 a minute) keeps 9 labs busy.

| Stage | Unit time T | Labs for 0.25 / 0.5 / 1 unit per second (S = 1.5) |
|---|---|---|
| Red (S = 1) | 5 to 15 s | 4 / 8 / 15 |
| Green before research speed (S = 1) | 15 to 30 s | 8 / 15 / 30 |
| Green after research speed 2 | 30 s | 5 / 10 / 20 |
| Blue | 30 to 45 s | 8 / 15 / 30 |
| Purple, yellow, silo | 60 s | 10 / 20 / 40 |

Build toward the largest T in the stage. A lab costs a lab plus one inserter; chain labs lab to inserter to lab so one feed point serves the row. Labs past `L` sit idle, so raise pack supply before adding labs. Plan 16 to 24 labs for the silo technology.

Labs, not packs, limit research once 30 s technologies start, unless you build them ahead. A test run with two AM2 red cells (0.3/s) and six labs ran `electric-energy-distribution-1` and `oil-gathering` at 12 units/min (0.2/s) while its green assemblers sat at `full_output`. It read that as a red shortage ("red is the bottleneck", 45:52) and spent the next 12 minutes on a second red and green row.
