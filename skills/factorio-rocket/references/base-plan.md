# Planning the base

Read this in phase 1, before the first assembler goes down, and again before each new block. A factory that reaches a rocket is about ten times the size of the one that makes red and green science, and it grows for hours. Where the first blocks stand decides whether the later ones fit beside a belt or end up across the map with you carrying between them. Every map is different, so this file gives no coordinates: it gives the shape, and you fit it to what `fac map` and your screenshots show.

## Survey

Before you choose, write into `notes.md`:

- from `fac map`: every patch of iron, copper, coal and stone with its center, nearest tile, bounding box and amount; every body of water; crude oil once you have seen it (it is often 200 tiles or more away, so one long `fac walk` in a direction `fac map` shows nothing in is a normal part of the survey, done once power and red science run). `fac map iron-ore` adds the nearest patch's shape, row by row;
- from a walk and `fac screenshot --zoom 0.5`: where the ground between the patches is open, and where trees, rocks, cliffs or water are in the way.

Amounts matter. The run uses about 250k iron ore, 190k copper ore, 100k coal and 20k stone. A patch much smaller than that will run out, and your plan has to say where the next one's belt comes in.

## The site

Choose one site for everything that is not mining or oil. Good sites:

- open ground at least 150 tiles long and 60 wide, with the long side pointing away from the ore so the trunks can keep growing (the direction they run is called downstream below);
- its upstream end 10 to 30 tiles from the iron patch, and no farther from the copper than it must be: iron is used most, and every tile between patch and base is a belt tile you craft;
- not on ore, and not between a patch and the side of it you will mine;
- water within a pole line's reach (power comes over poles, so the boilers stay at the shore and only wire comes to the base).

## The shape

Two plate trunks run side by side from the smelters, downstream, 6 tiles apart: the iron trunk and the copper trunk. The strip between them takes 3x3 machines, each with an inserter from the iron trunk on one side and an inserter from the copper trunk on the other, so a machine there never needs a belt of its own for plates. Labs stand in a chain on the outer side of the iron trunk and take red packs over it through long-handed inserters. This is the science block (science.md): its anchor is an iron trunk tile, the copper trunk runs at dy 6, the strip at dy 1 to 5, the labs north of the iron trunk to dy -17, and the mall east of the science. references/layouts.md lists every tested block with its anchor and orientation; the blocks were tested with trunks running east, so turn the whole base to suit your site and keep it that way.

```
 upstream (ore side)                                             downstream: keep free
                                                                 for the next blocks
              [lab][lab][lab][lab] ...   lab chain, entry at lab one for belts of packs
 iron    ====================================================>   iron trunk
 column     red   red   green block   mall   steel   blue ...    the strip
 copper  ====================================================>   copper trunk
 column
            corridor: keep 8 tiles free along the outside of each trunk and of the
            lab chain for feeder belts (coal, steel, plastic and sulfur, packs)

 ore belts come in upstream from the patches; the coal belt passes the boilers at the
 shore first and then the furnace columns; the oil site sends plastic and sulfur in
 on one belt; power comes in on poles.
```

What goes where, in the order you build it:

1. **Smelting, upstream.** One smelting column per plate (smelting.md): ore on one lane, coal on the other, 7.5 plates/s onto its trunk at A + (x, 5.5). That trunk is the science block's trunk: lay it on east to the science anchor (iron) or to the line 6 tiles south of it (copper). Two columns cannot stand 6 tiles apart, so put the copper column farther upstream or beside, and turn its trunk onto the copper line before the science block. The ore belt can run any length from the drill row, so the furnaces stay at the base end when you move the drills to the next patch. Coal: the power block's coal belt runs east from the boilers (power.md, P + (x, +2)) and ends at the smelting column's feeder, arriving from the south at A + (-1.5, 2.5). It feeds one column; how to split it for the second column and the oil site is untested, so give those their own coal drills onto a belt or try a splitter and check both lanes.
2. **Red and green, first on the trunks**, with the lab chain beside them (science.md).
3. **The mall**, downstream (east) of the science, inside the science block: an upstream mall takes the science's iron first.
4. **Steel**, then **blue**, **purple** and **yellow**, each farther downstream, each taking plates from the trunks and its other inputs from a feeder belt in the corridor, each sending its packs back on a belt to lab 1, arriving from the north at the science block's west end (belt A: blue and purple, belt B: yellow; science.md, "10. Pack entry at lab 1").
5. **The silo** at the downstream end or beside the corridor, with its three ingredients arriving on belts.

Oil is processed at the oil field or at water near it, because fluids need pipes and refineries need water. What leaves the oil site is solid and rides a belt: plastic and sulfur first, later solid fuel or rocket fuel. Machines that need a fluid as an ingredient (sulfuric acid for batteries and processing units, lubricant for electric engines) go where that fluid is, at the oil site, or get the fluid by pipe; decide which when you plan the block, and write it down.

## Keeping it buildable

- **Never build across the trunks' line downstream.** No pole, chest, lab or pipe within the strip's width ahead of the trunks' ends. Extending a trunk is one `fac place ... --to` call when the way is clear.
- **Keep the corridors free** of everything but the belts they are for. Put poles in the gaps beside inserters, not in a lane a belt will need.
- **Leave walking room.** You build from outside a block, 2 or more tiles clear along its edge, and a finished block can't be walked through. Plan where you stand before you place.
- **Cross belts with underground belts** (4 tiles between the pieces) and pipes with pipe-to-ground. Plan crossings at the block edges, not through the middle.
- **Write each block into `notes.md` when it runs**: anchor, extent, what each belt lane carries, standing spots. The next block is placed against those numbers, not against your memory.

## Supply and demand

A transport belt carries 15 items/s, 7.5 on each lane. One ore lane feeds 24 stone furnaces or 12 steel furnaces (7.5 plates/s), from 15 electric drills (smelting.md). Rough plate needs, from references/production.md:

| Stage running | Iron plates/s | Copper plates/s |
|---|---|---|
| Science block, AM2: red 0.3/s, green 0.5/s (science.md) | 3.4 (plan 5.1 with the mall) | 1.1 |
| plus blue at 0.25/s | 5.3 | 2.6 |
| plus purple at 0.25/s | 18 | 7.4 |
| plus yellow at 0.25/s | 27 | 20 |

So one iron trunk and one copper trunk carry the factory through blue. Purple and yellow need more than a trunk holds: give them their own smelting and their own pair of trunks beside the first (a second copy of the same shape), or run them at half the rate. Decide before you build purple, and check the patch amounts.

Upstream takes first. A machine near the smelters gets its plates before one far downstream, so when supply is short the far end starves: its belt `fill` is near 0 while the upstream end is full. The fix is more smelting or a second trunk, never a detour. When everything is `working` and the trunk is packed to its end, supply is ahead: build the next consumer.

## When a patch runs out

`fac inspect` on an ore tile shows its amount, and a mined-out drill shows `no_minable_resources` and a red triangle in a screenshot. Before a patch is half gone, find the next one in `fac map` and plan its belt to the same furnace columns. Move the drills there; leave the furnaces and the trunk where they are.
