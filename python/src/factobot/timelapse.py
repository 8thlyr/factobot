"""A timelapse of a world: camera frames of the factory at a steady game-time
interval, and a video made from them (decision 89).

Capture asks the dev socket where the player force's buildings stand, moves the
picture's frame toward the box around the densest of them, and renders that
frame with the camera at noon. Each frame goes to `timelapse/frame-NNNNNN.png`
in the run directory with one line in `timelapse/frames.jsonl`: its tick, area,
building counts and the science and rocket milestones so far, which the video
turns into captions.

    python -m factobot.timelapse capture RUN_DIR [--every 30]   # attach to a running world
    python -m factobot.timelapse render RUN_DIR -o out.mp4      # make the video

A playtest started with `--timelapse SECONDS` captures as it runs. The video
has its own camera: it crops and enlarges the frames to follow the factory the
agent built (from the run's `world/calls.jsonl`), eases between aims so it never
jumps, and gives each frame time by how much the factory grew in it (decision 90).
"""

from __future__ import annotations

import argparse
import json
import math
import multiprocessing
import os
import shutil
import subprocess
import sys
import tempfile
import time
from collections import deque
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from PIL import Image

from factobot.client import Client, FactobotError

TICKS_PER_SECOND = 60
# Pixels per tile at zoom 1.
TILE_PX = 32
FRAME_SIZE = (1920, 1080)
# Tiles of ground left around the factory.
MARGIN = 12.0
# The smallest frame, in tiles: zoom 1 on a 1920x1080 picture.
MIN_WIDTH = 60.0
# Share of the way a frame edge moves out toward the factory's edge per frame,
# so a new part of the factory zooms the picture out over a few frames instead
# of in one jump, and the slower share it moves in when the factory's box lies
# inside it, so the picture never pumps in and out.
GROW_RATE = 0.35
SHRINK_RATE = 0.08
# The frame holds the densest map chunks that together hold this share of the
# buildings. The rest are far outposts and the pole, pipe and belt lines to them:
# framing them too left the factory itself in a corner of an empty picture (seed
# 1, 2026-11-14: an oil outpost 250 tiles east held 2% of the buildings).
CORE_SHARE = 0.9
CHUNK_TILES = 32

# Building counts each frame records; types, except the names after them.
COUNTED_TYPES = (
    "mining-drill",
    "furnace",
    "assembling-machine",
    "lab",
    "transport-belt",
    "inserter",
    "boiler",
    "generator",
    "solar-panel",
    "rocket-silo",
)
COUNTED_NAMES = ("pumpjack", "oil-refinery", "chemical-plant")

# One dev `lua` call per frame: per map chunk, the count and box of the player
# force's buildings (not its character), keyed "x,y"; the character's position;
# the building counts. Read only: it changes nothing in the world.
FRAME_LUA = (
    "local s = game.surfaces[1] "
    "local chunks = {} "
    'for _, e in pairs(s.find_entities_filtered{force = "player"}) do '
    'if e.type ~= "character" then '
    "local p = e.position "
    f"local k = math.floor(p.x / {CHUNK_TILES}) .. ',' .. math.floor(p.y / {CHUNK_TILES}) "
    "local c = chunks[k] "
    "if c == nil then chunks[k] = {1, p.x, p.y, p.x, p.y} else c[1] = c[1] + 1 "
    "if p.x < c[2] then c[2] = p.x end if p.y < c[3] then c[3] = p.y end "
    "if p.x > c[4] then c[4] = p.x end if p.y > c[5] then c[5] = p.y end end end end "
    "local counts = {} "
    "for _, k in pairs({"
    + ", ".join(f'"{name}"' for name in COUNTED_TYPES)
    + '}) do counts[k] = s.count_entities_filtered{force = "player", type = k} end '
    "for _, k in pairs({"
    + ", ".join(f'"{name}"' for name in COUNTED_NAMES)
    + '}) do counts[k] = s.count_entities_filtered{force = "player", name = k} end '
    'local body = s.find_entities_filtered{type = "character", limit = 1}[1] '
    "return {tick = game.tick, chunks = chunks, counts = counts, "
    "body = body and {body.position.x, body.position.y} or {0, 0}}"
)


@dataclass(frozen=True)
class Box:
    """A map area in tiles: left, top, right, bottom."""

    left: float
    top: float
    right: float
    bottom: float

    @property
    def width(self) -> float:
        return self.right - self.left

    @property
    def height(self) -> float:
        return self.bottom - self.top

    @property
    def center(self) -> tuple[float, float]:
        return ((self.left + self.right) / 2, (self.top + self.bottom) / 2)


def _fit(box: Box, aspect: float, min_width: float) -> Box:
    """`box` widened or heightened about its centre to `aspect` and at least `min_width`."""
    width = max(box.width, box.height * aspect, min_width)
    height = width / aspect
    x, y = box.center
    return Box(x - width / 2, y - height / 2, x + width / 2, y + height / 2)


def core_box(chunks: dict[str, list[float]] | list[Any], share: float = CORE_SHARE) -> Box | None:
    """The box around the buildings in the fewest, densest chunks that hold `share`
    of them all. `chunks` maps a chunk to `[count, left, top, right, bottom]` of
    its buildings; Lua writes an empty table as a list."""
    if not chunks:
        return None
    assert isinstance(chunks, dict)
    densest = sorted(chunks.items(), key=lambda item: (-item[1][0], item[0]))
    total = sum(stats[0] for _, stats in densest)
    kept: list[list[float]] = []
    for _, stats in densest:
        kept.append(stats)
        if sum(held[0] for held in kept) >= share * total:
            break
    return Box(
        min(stats[1] for stats in kept),
        min(stats[2] for stats in kept),
        max(stats[3] for stats in kept),
        max(stats[4] for stats in kept),
    )


def next_frame(
    previous: Box | None,
    buildings: Box | None,
    body: tuple[float, float],
    *,
    aspect: float = FRAME_SIZE[0] / FRAME_SIZE[1],
    margin: float = MARGIN,
    min_width: float = MIN_WIDTH,
    grow: float = GROW_RATE,
    shrink: float = SHRINK_RATE,
) -> Box:
    """The map area the next frame shows.

    The goal is the buildings' box with `margin` around it (the area around the
    body before anything is built). The first frame is the goal at `aspect` and
    at least `min_width` tiles across. After that each edge moves `grow` of the
    way out to the goal's edge when the goal lies beyond it, and `shrink` of the
    way in when it lies inside, and the frame then widens or heightens to
    `aspect`: the picture zooms out quickly and smoothly as the factory grows,
    and settles in slowly when it can.
    """
    if buildings is None:
        x, y = body
        goal = Box(x, y, x, y)
    else:
        goal = Box(
            buildings.left - margin,
            buildings.top - margin,
            buildings.right + margin,
            buildings.bottom + margin,
        )
    fitted = _fit(goal, aspect, min_width)
    if previous is None:
        return fitted

    def toward(old: float, out: float, settled: float, outward: float) -> float:
        # Out to the factory's edge; in only as far as the whole goal at `aspect`,
        # so an edge the aspect holds out does not creep in while another grows.
        if (out - old) * outward > 0:
            return old + grow * (out - old)
        if (settled - old) * outward < 0:
            return old + shrink * (settled - old)
        return old

    moved = Box(
        toward(previous.left, goal.left, fitted.left, -1),
        toward(previous.top, goal.top, fitted.top, -1),
        toward(previous.right, goal.right, fitted.right, 1),
        toward(previous.bottom, goal.bottom, fitted.bottom, 1),
    )
    return _fit(moved, aspect, min_width)


def dev_socket(run_dir: Path) -> Path:
    """The dev socket of the world a playtest runs in `run_dir`."""
    return run_dir / "world" / "dev" / "dev.sock"


class Capture:
    """Takes a frame of the factory every `every` seconds of game time.

    `poll` is cheap when no frame is due (one `game.tick` read), so a runner can
    call it every few seconds. A frame that fails is logged and the next poll
    tries again; a timelapse must never end the run it records.
    """

    def __init__(
        self,
        dev: Client,
        out_dir: Path,
        every: float,
        size: tuple[int, int] = FRAME_SIZE,
    ) -> None:
        self.dev = dev
        self.dir = out_dir / "timelapse"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.every_ticks = max(1, round(every * TICKS_PER_SECOND))
        self.size = size
        self.index_path = self.dir / "frames.jsonl"
        # Continue a capture that was stopped: same frame numbering and framing.
        earlier = read_frames(self.dir)
        self.count = len(earlier)
        self.box: Box | None = Box(*earlier[-1]["box"]) if earlier else None
        self.next_tick = earlier[-1]["tick"] + self.every_ticks if earlier else 0

    def poll(self) -> dict[str, Any] | None:
        """Take a frame if one is due; returns its record."""
        try:
            if int(self.dev.call("lua", {"code": "game.tick"})) < self.next_tick:
                return None
            return self._frame()
        except (OSError, FactobotError, ValueError) as err:
            print(f"timelapse frame failed: {err}", file=sys.stderr, flush=True)
            return None

    def _frame(self) -> dict[str, Any]:
        seen = self.dev.call("lua", {"code": FRAME_LUA})
        buildings = core_box(seen["chunks"])
        body = (float(seen["body"][0]), float(seen["body"][1]))
        box = next_frame(self.box, buildings, body, aspect=self.size[0] / self.size[1])
        zoom = self.size[0] / (box.width * TILE_PX)
        name = f"frame-{self.count + 1:06d}.png"
        x, y = box.center
        shot = self.dev.call(
            "screenshot",
            {
                "x": x,
                "y": y,
                "zoom": zoom,
                "width": self.size[0],
                "height": self.size[1],
                "path": os.fspath((self.dir / name).absolute()),
            },
        )
        milestones = self.dev.call("milestones")
        record = {
            "frame": self.count + 1,
            "file": name,
            "tick": shot["tick"],
            "time": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "box": [box.left, box.top, box.right, box.bottom],
            "zoom": zoom,
            "counts": seen["counts"],
            "automated": {
                pack["name"]: pack["first_automated_research"]
                for pack in milestones["packs"]
                if pack.get("first_automated_research") is not None
            },
            "made_by_machine": {
                pack["name"]: pack["made_by_machine"]
                for pack in milestones["packs"]
                if pack["made_by_machine"]
            },
            "rocket_launched_tick": milestones.get("rocket_launched_tick"),
        }
        with self.index_path.open("a") as index:
            index.write(json.dumps(record) + "\n")
        self.count += 1
        self.box = box
        self.next_tick = int(seen["tick"]) + self.every_ticks
        return record


def read_frames(directory: Path) -> list[dict[str, Any]]:
    """The records in `directory/frames.jsonl` whose PNG is on disk, in order."""
    index = directory / "frames.jsonl"
    if not index.exists():
        return []
    records = []
    for line in index.read_text().splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue  # a line cut short when the capture was killed
        if (directory / record["file"]).exists():
            records.append(record)
    return records


def capture(run_dir: Path, every: float, size: tuple[int, int], poll_seconds: float) -> None:
    """Attach to the world a playtest runs in `run_dir` and capture until the run
    has written its summary or the world's dev socket is gone."""
    frames = Capture(Client(dev_socket(run_dir)), run_dir, every, size)
    while dev_socket(run_dir).exists() and not (run_dir / "summary.json").exists():
        record = frames.poll()
        if record is not None:
            print(
                f"frame {record['frame']} at tick {record['tick']} "
                f"({record['box'][2] - record['box'][0]:.0f} tiles across)",
                file=sys.stderr,
                flush=True,
            )
        time.sleep(poll_seconds)
    print("the run ended; capture stops", file=sys.stderr, flush=True)


# Captions for the first machine-made pack of each tier labs research with.
PACK_TITLES = {
    "automation-science-pack": "Red science automated",
    "logistic-science-pack": "Green science automated",
    "military-science-pack": "Military science automated",
    "chemical-science-pack": "Blue science automated",
    "production-science-pack": "Purple science automated",
    "utility-science-pack": "Yellow science automated",
    "space-science-pack": "Space science automated",
}
# Captions for the first building of a kind, by its key in a frame's counts.
FIRST_BUILT = (
    ("generator", "Steam power online"),
    ("assembling-machine", "First assembling machine"),
    ("lab", "First lab"),
    ("pumpjack", "Oil pumping"),
    ("oil-refinery", "First oil refinery"),
    ("rocket-silo", "Rocket silo built"),
)
# A frame's counts on the video, by key and label.
SHOWN_COUNTS = (
    ("mining-drill", "drills"),
    ("furnace", "furnaces"),
    ("assembling-machine", "assemblers"),
    ("transport-belt", "belts"),
)


@dataclass(frozen=True)
class Event:
    """A milestone first seen in frame `frame` (an index into the frames), at `tick`."""

    frame: int
    tick: int
    title: str


def milestone_events(frames: Sequence[dict[str, Any]]) -> list[Event]:
    """The milestones the frames show happening, in order.

    What the first frame already holds (a run continued from a save) happened
    before the timelapse and gets no caption.
    """
    if not frames:
        return []

    def reached(record: dict[str, Any]) -> dict[str, int]:
        found = {key: record["tick"] for key, _ in FIRST_BUILT if record["counts"].get(key, 0) > 0}
        found.update(record["automated"])
        if record.get("rocket_launched_tick") is not None:
            found["rocket"] = record["rocket_launched_tick"]
        return found

    titles = {**dict(FIRST_BUILT), **PACK_TITLES, "rocket": "Rocket launched"}
    seen = set(reached(frames[0]))
    events = []
    for index, record in enumerate(frames[1:], start=1):
        for key, tick in reached(record).items():
            if key not in seen:
                seen.add(key)
                events.append(Event(index, tick, titles.get(key, key)))
    return events


@dataclass(frozen=True)
class Cut:
    """One video made from the frames: its size, where the factory's picture sits
    in it, and how its time is spent: title card, the frames, the closing push-in
    and the end card."""

    width: int
    height: int
    seconds: float
    intro: float
    finale: float
    outro: float
    # The factory's picture in the video: left, top, width and height in pixels.
    picture: tuple[int, int, int, int]
    fps: int = 30

    @property
    def vertical(self) -> bool:
        return self.height > self.width

    @property
    def aspect(self) -> float:
        return self.picture[2] / self.picture[3]

    @property
    def body(self) -> float:
        """Seconds the frames get."""
        return self.seconds - self.intro - self.finale - self.outro


LANDSCAPE = Cut(1920, 1080, 70.0, intro=3.5, finale=6.5, outro=4.0, picture=(0, 0, 1920, 1080))
# A square picture between the headline above and the clock and counts below,
# with captions over its foot, all big enough to read on a phone.
VERTICAL = Cut(1080, 1920, 23.0, intro=2.0, finale=4.5, outro=2.5, picture=(0, 400, 1080, 1080))
BACKGROUND = (14, 14, 16)
# Seconds a milestone caption stays up, and the least it stays when the next
# one is due sooner.
CAPTION_SECONDS = 2.8
MIN_CAPTION_SECONDS = 1.4
# The captions the short vertical cut keeps.
HEADLINE_TITLES = frozenset(PACK_TITLES.values()) | {"Rocket silo built"}
ORANGE = "&H001C9FFF"  # #FF9F1C, as ASS writes colours (alpha, blue, green, red)
# The backing behind all text on the picture: black, 13% transparent.
BACKING = "&H20000000"
URL = "github.com/8thlyr/factobot"

# The video's own camera (decision 90). The frames are cropped and enlarged to
# follow the factory, from the buildings the agent placed (`world/calls.jsonl`).
# Items laid in long lines to outposts; they count toward how fast the factory
# grows, but not toward its box.
LINE_ITEMS = frozenset(
    {
        "transport-belt",
        "fast-transport-belt",
        "express-transport-belt",
        "underground-belt",
        "fast-underground-belt",
        "express-underground-belt",
        "splitter",
        "fast-splitter",
        "express-splitter",
        "pipe",
        "pipe-to-ground",
        "small-electric-pole",
        "medium-electric-pole",
        "big-electric-pole",
        "substation",
        "burner-inserter",
        "inserter",
        "long-handed-inserter",
        "fast-inserter",
        "bulk-inserter",
        "wooden-chest",
        "iron-chest",
        "steel-chest",
    }
)
# What one machine counts for against one placed tile of line, in growth.
MACHINE_WEIGHT = 4.0
# The factory is the largest group of machines in touching chunks; what is
# being built is the densest chunks holding this share of recent building in it.
FOCUS_SHARE = 0.85
# Building in this many game ticks before a frame counts as recent.
FOCUS_WINDOW = 45 * 60 * TICKS_PER_SECOND
# How far the picture leans from the whole factory toward what is being built
# (0 to 1), in position and in log size.
FOCUS_PULL = 0.6
# Tiles of ground around what the picture shows.
VIDEO_MARGIN = 6.0
# The most a frame's pixels are enlarged, and the fewest tiles the picture is tall.
MAX_ZOOM = 2.5
MIN_TILES = 24.0
# Seconds of video the camera's path is smoothed over (a Gaussian's sigma), and
# how many times it is smoothed and kept inside the frames.
CAMERA_SIGMA = 2.0
CAMERA_PASSES = 4
CAMERA_ZOOM = 1.25
CAMERA_PAN = 0.12
# Pacing: a frame's share of the video is this share of the mean growth plus its
# own growth, smoothed over a Gaussian of PACE_SIGMA frames.
CALM_SHARE = 0.25
PACE_SIGMA = 4.0
# Seconds one frame takes to dissolve into the next when it is held longer.
FADE_SECONDS = 0.35
# Tiles tall the closing push-in ends at, and its shares: the move to where the
# last frame and the still meet ends at the first, the dissolve at the second.
FINALE_TILES = 30.0
FINALE_MEET = 0.45
FINALE_PUSH = 0.6


@dataclass(frozen=True)
class Placed:
    """A building the agent placed (`count` > 0), or anything it mined (< 0)."""

    tick: int
    x: float
    y: float
    item: str
    count: float

    @property
    def machine(self) -> bool:
        return self.item not in LINE_ITEMS


def read_placements(calls: Path) -> list[Placed]:
    """What the agent built and mined, in order, from a run's `calls.jsonl`. A
    line counts half its buildings at each end."""
    if not calls.exists():
        return []
    placed = []
    with calls.open() as lines:
        for line in lines:
            try:
                call = json.loads(line)
            except json.JSONDecodeError:
                continue
            response = call.get("response") or {}
            if not response.get("ok"):
                continue
            params = call.get("params") or {}
            result = response.get("result") or {}
            tick = call["tick"]
            if call["method"] == "place":
                placed.append(Placed(tick, params["x"], params["y"], params["item"], 1))
            elif call["method"] == "place_line":
                half = max(1, result.get("tiles", 1) // (params.get("spacing") or 1)) / 2
                placed.append(Placed(tick, params["x"], params["y"], params["item"], half))
                placed.append(Placed(tick, params["to_x"], params["to_y"], params["item"], half))
            elif call["method"] == "mine" and "target" in result:
                target = result["target"]
                at = target["position"]
                placed.append(Placed(tick, at["x"], at["y"], target["name"], -1))
    placed.sort(key=lambda p: p.tick)
    return placed


def _dense_box(points: Iterable[tuple[float, float, float]], share: float) -> Box | None:
    """`core_box` of weighted points."""
    chunks: dict[str, list[float]] = {}
    for x, y, weight in points:
        key = f"{math.floor(x / CHUNK_TILES)},{math.floor(y / CHUNK_TILES)}"
        chunk = chunks.get(key)
        if chunk is None:
            chunks[key] = [weight, x, y, x, y]
        else:
            chunk[0] += weight
            chunk[1], chunk[2] = min(chunk[1], x), min(chunk[2], y)
            chunk[3], chunk[4] = max(chunk[3], x), max(chunk[4], y)
    return core_box(chunks, share)


def _cluster_box(points: Iterable[tuple[int, int]]) -> Box | None:
    """The box around the largest group of `points` in touching map chunks:
    the factory, without the outposts that empty chunks part from it."""
    chunks: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for x, y in points:
        chunks.setdefault((x // CHUNK_TILES, y // CHUNK_TILES), []).append((x, y))
    best: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for start in chunks:
        if start in seen:
            continue
        seen.add(start)
        group, todo = [], [start]
        while todo:
            cx, cy = todo.pop()
            group += chunks[(cx, cy)]
            for near in ((cx + dx, cy + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
                if near in chunks and near not in seen:
                    seen.add(near)
                    todo.append(near)
        if len(group) > len(best):
            best = group
    if not best:
        return None
    xs, ys = [x for x, _ in best], [y for _, y in best]
    return Box(min(xs), min(ys), max(xs), max(ys))


def _at(center: tuple[float, float], width: float, aspect: float) -> Box:
    x, y = center
    height = width / aspect
    return Box(x - width / 2, y - height / 2, x + width / 2, y + height / 2)


def _grow(box: Box, margin: float) -> Box:
    return Box(box.left - margin, box.top - margin, box.right + margin, box.bottom + margin)


def _inside(box: Box, area: Box) -> Box:
    """`box` shrunk about its centre if it must be, then moved, to lie in `area`."""
    scale = min(1.0, area.width / box.width, area.height / box.height)
    width, height = box.width * scale, box.height * scale
    x = min(max(box.center[0], area.left + width / 2), area.right - width / 2)
    y = min(max(box.center[1], area.top + height / 2), area.bottom - height / 2)
    return Box(x - width / 2, y - height / 2, x + width / 2, y + height / 2)


def _overlap(a: Box, b: Box) -> Box:
    """Where `a` and `b` overlap, or `a` when they do not."""
    box = Box(
        max(a.left, b.left), max(a.top, b.top), min(a.right, b.right), min(a.bottom, b.bottom)
    )
    return box if box.width > 0 and box.height > 0 else a


def _between(a: Box, b: Box, u: float) -> Box:
    """`u` of the way from `a` to `b`: centre in a line, size by ratio, so a zoom
    moves at an even pace."""
    width = a.width * (b.width / a.width) ** u
    center = (
        a.center[0] + (b.center[0] - a.center[0]) * u,
        a.center[1] + (b.center[1] - a.center[1]) * u,
    )
    return _at(center, width, a.width / a.height)


def _ease(u: float) -> float:
    u = min(1.0, max(0.0, u))
    return u * u * (3 - 2 * u)


def _least(record: dict[str, Any], cut: Cut) -> float:
    """The fewest tiles across the picture may show of a frame: no more than
    MAX_ZOOM of its pixels to one of the video's, and MIN_TILES tall."""
    return max(cut.picture[2] / (TILE_PX * record["zoom"] * MAX_ZOOM), MIN_TILES * cut.aspect)


def camera_targets(
    frames: Sequence[dict[str, Any]], placements: Sequence[Placed], cut: Cut
) -> tuple[list[Box], list[float]]:
    """For each frame, the map area the picture aims at, and how much the agent
    built since the frame before.

    The aim leans FOCUS_PULL of the way from the whole factory (its machines,
    not the lines out to outposts) toward what was built in the last
    FOCUS_WINDOW ticks, no closer than the frame's pixels allow (MAX_ZOOM) and
    no less than MIN_TILES tall, and inside the area the frame shows."""
    aspect = cut.aspect
    machines: dict[tuple[int, int], None] = {}
    recent: deque[tuple[int, float, float, float]] = deque()
    targets, growth = [], []
    pending = iter(placements)
    upcoming = next(pending, None)
    for record in frames:
        tick = record["tick"]
        grown = 0.0
        while upcoming is not None and upcoming.tick <= tick:
            key = (round(upcoming.x), round(upcoming.y))
            if upcoming.count < 0:
                machines.pop(key, None)
            else:
                weight = upcoming.count * (MACHINE_WEIGHT if upcoming.machine else 1)
                grown += weight
                recent.append((upcoming.tick, upcoming.x, upcoming.y, weight))
                if upcoming.machine:
                    machines[key] = None
            upcoming = next(pending, None)
        while recent and recent[0][0] < tick - FOCUS_WINDOW:
            recent.popleft()
        growth.append(grown)
        shown = Box(*record["box"])
        least = _least(record, cut)
        factory = _cluster_box(machines)
        if factory is None:
            targets.append(_inside(_at(shown.center, max(least, shown.width), aspect), shown))
            continue
        whole = _fit(_grow(factory, VIDEO_MARGIN), aspect, 0)
        here = _grow(factory, CHUNK_TILES)
        building = (
            _dense_box(
                (
                    (x, y, w)
                    for _, x, y, w in recent
                    if here.left <= x <= here.right and here.top <= y <= here.bottom
                ),
                FOCUS_SHARE,
            )
            or factory
        )
        near = _fit(_grow(building, VIDEO_MARGIN), aspect, 0)
        aim = _between(whole, near, FOCUS_PULL)
        if aim.width < least:
            aim = _at(aim.center, least, aspect)
        aim = (
            _inside(aim, whole)
            if aim.width <= whole.width
            else _at(whole.center, aim.width, aspect)
        )
        targets.append(_inside(aim, shown))
    return targets, growth


def _smooth(values: Sequence[float], sigma: float) -> list[float]:
    """`values` averaged over a Gaussian of `sigma` places."""
    reach = int(3 * sigma) + 1
    kernel = [math.exp(-(d * d) / (2 * sigma * sigma)) for d in range(-reach, reach + 1)]
    out = []
    for i in range(len(values)):
        total = weights = 0.0
        for d, k in zip(range(-reach, reach + 1), kernel, strict=True):
            if 0 <= i + d < len(values):
                total += k * values[i + d]
                weights += k
        out.append(total / weights)
    return out


def frame_durations(growth: Sequence[float], seconds: float) -> list[float]:
    """Seconds of video for each frame, `seconds` in all: frames where the
    factory grows fast get more time than ones where it stands still."""
    smoothed = _smooth(growth, PACE_SIGMA)
    calm = CALM_SHARE * sum(smoothed) / len(smoothed)
    if calm <= 0:
        return [seconds / len(growth)] * len(growth)
    weights = [calm + value for value in smoothed]
    total = sum(weights)
    return [seconds * weight / total for weight in weights]


def smooth_camera(aims: Sequence[Box], areas: Sequence[Box], fps: int) -> list[Box]:
    """The picture's map area in each video frame, given where it aims and the
    area its pictures cover there.

    The aims are averaged over a Gaussian of CAMERA_SIGMA seconds, so the camera
    eases from one aim to the next, then kept inside the pictures; doing both
    CAMERA_PASSES times lets it ease into a narrower picture ahead of time. The
    camera then zooms no faster than CAMERA_ZOOM a second, narrowing early
    rather than late, and pans no faster than CAMERA_PAN of its width a second,
    so a frame that covers more than the one before (the capture zoomed out)
    opens the picture gradually instead of in one jump."""
    aspect = aims[0].width / aims[0].height
    path = list(aims)
    sigma = CAMERA_SIGMA * fps
    for _ in range(CAMERA_PASSES):
        xs = _smooth([box.center[0] for box in path], sigma)
        ys = _smooth([box.center[1] for box in path], sigma)
        sizes = _smooth([math.log(box.width) for box in path], sigma)
        path = [
            _inside(_at((x, y), math.exp(size), aspect), area)
            for x, y, size, area in zip(xs, ys, sizes, areas, strict=True)
        ]
    step = math.log(CAMERA_ZOOM) / fps
    sizes = [math.log(box.width) for box in path]
    for n in range(1, len(sizes)):
        sizes[n] = min(sizes[n], sizes[n - 1] + step)
    for n in range(len(sizes) - 2, -1, -1):
        sizes[n] = min(sizes[n], sizes[n + 1] + step)
    path = [
        _inside(_at(box.center, math.exp(size), aspect), area)
        for box, size, area in zip(path, sizes, areas, strict=True)
    ]

    def toward(box: Box, previous: Box, area: Box) -> Box:
        reach = CAMERA_PAN * box.width / fps
        (x, y), (px, py) = box.center, previous.center
        x = min(max(x, px - reach), px + reach)
        y = min(max(y, py - reach), py + reach)
        return _inside(_at((x, y), box.width, aspect), area)

    # Forward, back (to set off early toward an area that will pin the camera),
    # and forward again, since a pinned frame cannot follow the backward pass.
    for n in range(1, len(path)):
        path[n] = toward(path[n], path[n - 1], areas[n])
    for n in range(len(path) - 2, -1, -1):
        path[n] = toward(path[n], path[n + 1], areas[n])
    for n in range(1, len(path)):
        path[n] = toward(path[n], path[n - 1], areas[n])
    return path


@dataclass(frozen=True)
class Layer:
    """A picture of the map `area` covers, blended in at `weight`."""

    path: str
    area: Box
    weight: float


@dataclass(frozen=True)
class Shot:
    """One video frame: the layers, and the map area the picture shows."""

    layers: tuple[Layer, ...]
    camera: Box


def _still(path: Path, area: Box, camera: Box) -> Shot:
    return Shot((Layer(os.fspath(path), area, 1.0),), _inside(camera, area))


def body_layers(
    files: Sequence[Path],
    areas: Sequence[Box],
    starts: Sequence[float],
    durations: Sequence[float],
    count: int,
    fps: int,
) -> list[tuple[tuple[Layer, ...], Box, int]]:
    """For each of `count` video frames at `fps`: the frames blended there, the
    map area they all cover, and the frame on screen. Each frame is held for its
    duration, then dissolves into the next over FADE_SECONDS or its whole
    duration, whichever is shorter."""
    shown = []
    index = 0
    for n in range(count):
        t = n / fps
        while index + 1 < len(files) and starts[index + 1] <= t:
            index += 1
        following = min(index + 1, len(files) - 1)
        fade = min(durations[index], FADE_SECONDS)
        weight = 0.0
        if following != index:
            weight = _ease((t - starts[index] - durations[index] + fade) / fade)
        layers = [Layer(os.fspath(files[index]), areas[index], 1 - weight)]
        area = areas[index]
        if weight > 0:
            layers.append(Layer(os.fspath(files[following]), areas[following], weight))
            area = _overlap(area, areas[following])
        shown.append((tuple(layers), area, index))
    return shown


def finale_shots(
    last: Path,
    last_area: Box,
    least: float,
    camera: Box,
    focus: tuple[float, float],
    still: tuple[Path, Box] | None,
    cut: Cut,
) -> list[Shot]:
    """A slow push-in on `focus` (the rocket silo) from where the frames end.

    With `still`, a sharper picture of the map area its box covers, the camera
    first moves to the largest view that both pictures cover, dissolves into the
    still there, then pushes in on it. Without one it pushes in on the last frame
    as far as MAX_ZOOM allows (`least` tiles across)."""
    count = round(cut.finale * cut.fps)
    aspect = cut.aspect
    end_width = FINALE_TILES * aspect
    if still is None:
        end = _inside(_at(focus, max(end_width, least), aspect), last_area)
        return [
            _still(last, last_area, _between(camera, end, _ease(n / max(1, count - 1))))
            for n in range(count)
        ]
    still_path, still_area = still
    meet = _inside(_at(focus, camera.width, aspect), _overlap(last_area, still_area))
    end = _inside(_at(focus, end_width, aspect), still_area)
    shots = []
    for n in range(count):
        u = n / max(1, count - 1)
        if u < FINALE_MEET:
            shots.append(_still(last, last_area, _between(camera, meet, _ease(u / FINALE_MEET))))
        elif u < FINALE_PUSH:
            weight = _ease((u - FINALE_MEET) / (FINALE_PUSH - FINALE_MEET))
            layers = (
                Layer(os.fspath(last), last_area, 1 - weight),
                Layer(os.fspath(still_path), still_area, weight),
            )
            shots.append(Shot(layers, meet))
        else:
            push = _between(meet, end, _ease((u - FINALE_PUSH) / (1 - FINALE_PUSH)))
            shots.append(_still(still_path, still_area, push))
    return shots


def caption_times(wanted: Sequence[float], end: float) -> list[tuple[float, float] | None]:
    """When each caption shows, given the video time its milestone happens at.

    A caption starts on time, or when the one before it ends, and stays up
    CAPTION_SECONDS, cut short to no less than MIN_CAPTION_SECONDS when the next
    one is due. One that would start more than MIN_CAPTION_SECONDS late, or
    after `end`, is left out (None): a caption long after the picture shows it
    no longer says what is happening.
    """
    shown: list[tuple[float, float] | None] = []
    free = float("-inf")
    for index, at in enumerate(wanted):
        start = max(at, free)
        if start - at > MIN_CAPTION_SECONDS or start >= end:
            shown.append(None)
            continue
        stop = start + CAPTION_SECONDS
        if index + 1 < len(wanted) and wanted[index + 1] < stop:
            stop = max(start + MIN_CAPTION_SECONDS, wanted[index + 1])
        stop = min(stop, end)
        shown.append((start, stop))
        free = stop
    return shown


def _clock(seconds: float) -> str:
    minutes = int(seconds // 60)
    return f"{minutes // 60}:{minutes % 60:02d}"


def _ass_time(seconds: float) -> str:
    centis = max(0, round(seconds * 100))
    return (
        f"{centis // 360000}:{centis // 6000 % 60:02d}:{centis // 100 % 60:02d}.{centis % 100:02d}"
    )


def _ass_styles(cut: Cut) -> str:
    # name, font, size, bold, boxed, alignment, margin v. The clock and counts
    # sit in the corners of the landscape cut and under the picture in the
    # vertical one; captions sit at the bottom of either.
    pad = 36
    # Vertical captions sit over the foot of the picture, above the clock.
    caption_margin = cut.height - cut.picture[1] - cut.picture[3] + 30 if cut.vertical else 60
    styles = [
        ("Clock", "JetBrains Mono", 64 if cut.vertical else 68, 1, True, 7, pad),
        ("Counts", "DejaVu Sans", 46 if cut.vertical else 50, 0, True, 9, pad),
        ("Caption", "DejaVu Sans", 84 if cut.vertical else 104, 1, True, 2, caption_margin),
        ("Card", "DejaVu Sans", 52, 1, False, 5, 0),
    ]
    lines = [
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
    ]
    for name, font, size, bold, boxed, align, margin in styles:
        # BorderStyle 3 draws a box in the outline colour, Outline pixels round the text.
        lines.append(
            f"Style: {name},{font},{size},&H00FFFFFF,&H00FFFFFF,"
            f"{BACKING if boxed else '&H00000000'},&H90000000,{bold},0,0,0,100,100,0,0,"
            f"{3 if boxed else 1},{14 if boxed else 3},{0 if boxed else 2},"
            f"{align},{pad},{pad},{margin},1"
        )
    return "\n".join(lines)


def overlay_ass(
    frames: Sequence[dict[str, Any]],
    events: Sequence[Event],
    cut: Cut,
    *,
    starts: Sequence[float],
    started: datetime,
    title: str,
    subline: str,
    band: str,
    outcome: str,
) -> str:
    """The video's text as an ASS subtitle script: title card, clock, building
    counts, milestone captions, the outcome over the push-in and the end card.
    `starts` is the video time each frame comes on; `band` is the line under the
    vertical cut's headline."""
    end = cut.seconds
    body_end = cut.intro + cut.body
    finale_end = body_end + cut.finale
    dim = (
        f"{{\\an7\\pos(0,0)\\bord0\\shad0\\1c&H000000&\\1a&H40&\\p1}}"
        f"m 0 0 l {cut.width} 0 {cut.width} {cut.height} 0 {cut.height}{{\\p0}}"
    )
    logo = f"{{\\fs{160 if cut.vertical else 170}\\c{ORANGE}\\b1}}factobot"
    rows = []

    def add(layer: int, start: float, stop: float, style: str, text: str) -> None:
        rows.append(
            f"Dialogue: {layer},{_ass_time(start)},{_ass_time(stop)},{style},,0,0,0,,{text}"
        )

    small = 50 if cut.vertical else 56
    add(0, 0, cut.intro, "Card", f"{{\\fad(0,500)}}{dim}")
    add(
        1,
        0,
        cut.intro,
        "Card",
        f"{{\\fad(300,500)}}{logo}\\N{{\\fs{72 if cut.vertical else 76}\\c&HFFFFFF&\\b1}}{title}"
        f"\\N{{\\fs{small}\\b0\\c&HE6E6E6&}}{subline}",
    )
    add(0, end - cut.outro, end, "Card", f"{{\\fad(500,0)}}{dim}")
    add(
        1,
        end - cut.outro,
        end,
        "Card",
        f"{{\\fad(500,0)}}{logo}\\N{{\\fs{small + 8}\\b0\\c&HFFFFFF&}}{URL}",
    )
    below = cut.picture[1] + cut.picture[3]
    if cut.vertical:
        # The band above the picture holds what the video is about.
        add(
            1,
            cut.intro,
            end - cut.outro,
            "Card",
            f"{{\\an8\\pos({cut.width // 2},40)\\fs68\\b1}}{title}"
            f"\\N{{\\fs46\\b0\\c&HE6E6E6&}}{band}",
        )
    # The clock and counts change when the text does, not on every frame.
    shown: list[tuple[float, str, str]] = []
    for record, at in zip(frames, starts, strict=True):
        wall = (_parse_time(record["time"]) - started).total_seconds()
        clock = f"game {_clock(record['tick'] / TICKS_PER_SECOND)}  real {_clock(wall)}"
        parts = []
        for key, label in SHOWN_COUNTS:
            count = record["counts"].get(key, 0)
            parts.append(f"{count:,} {label if count != 1 else label.removesuffix('s')}")
        counts = f"{parts[0]} · {parts[1]}\\N{parts[2]} · {parts[3]}"
        if not shown or shown[-1][1:] != (clock, counts):
            shown.append((at, clock, counts))
    clock_at = f"{{\\an8\\pos({cut.width // 2},{below + 30})}}" if cut.vertical else ""
    counts_at = f"{{\\an8\\pos({cut.width // 2},{below + 140})}}" if cut.vertical else ""
    for (at, clock, counts), following in zip(shown, [*shown[1:], None], strict=True):
        stop = following[0] if following else body_end
        add(2, at, stop, "Clock", clock_at + clock)
        add(2, at, stop, "Counts", counts_at + counts)
    if cut.vertical:
        # 23 seconds hold only the science tiers and the silo.
        events = [event for event in events if event.title in HEADLINE_TITLES]
    wanted = [starts[event.frame] for event in events]
    for event, times in zip(events, caption_times(wanted, body_end), strict=True):
        if times is None:
            continue
        add(
            3,
            *times,
            "Caption",
            f"{{\\fad(200,350)}}{event.title}\\N{{\\fs{small + 6}\\b0}}"
            f"after {_clock(event.tick / TICKS_PER_SECOND)} of game time",
        )
    # The outcome over the push-in, once the camera has closed in.
    said, _, rest = outcome.partition(" after ")
    if rest:
        outcome = f"{said}\\N{{\\fs{small + 6}\\b0}}after {rest}"
    add(
        3,
        body_end + cut.finale * FINALE_MEET,
        finale_end,
        "Caption",
        f"{{\\fad(500,300)}}{outcome}",
    )
    header = (
        f"[Script Info]\nScriptType: v4.00+\nPlayResX: {cut.width}\nPlayResY: {cut.height}\n"
        "WrapStyle: 0\nScaledBorderAndShadow: yes\n\n"
    )
    events_head = (
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    return header + _ass_styles(cut) + "\n\n" + events_head + "\n".join(rows) + "\n"


def _parse_time(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)


def _run_start(run_dir: Path, frames: Sequence[dict[str, Any]]) -> datetime:
    """When the run began: the summary's `started_at`, else the `started` file's
    time, else the first frame's."""
    summary = run_dir / "summary.json"
    if summary.exists():
        return _parse_time(json.loads(summary.read_text())["started_at"])
    if (run_dir / "started").exists():
        return datetime.fromtimestamp((run_dir / "started").stat().st_mtime, UTC)
    return _parse_time(frames[0]["time"])


def outcome_line(frames: Sequence[dict[str, Any]], events: Sequence[Event]) -> str:
    """The closing sentence: the rocket's game time, else the last milestone's."""
    last = frames[-1]
    launched = last.get("rocket_launched_tick")
    if launched is not None:
        return f"Rocket launched after {_clock(launched / TICKS_PER_SECOND)} of game time"
    hours = _clock(last["tick"] / TICKS_PER_SECOND)
    if events:
        return f"{events[-1].title} · {hours} of game time"
    return f"{hours} of game time"


# Each drawing process keeps the last few pictures it decoded: neighbouring
# video frames share them.
_pictures: dict[str, Image.Image] = {}
_cut: Cut = LANDSCAPE


def _start_drawing(cut: Cut) -> None:
    global _cut
    _cut = cut


def _picture(path: str) -> Image.Image:
    picture = _pictures.get(path)
    if picture is None:
        if len(_pictures) >= 4:
            del _pictures[next(iter(_pictures))]
        with Image.open(path) as opened:
            picture = opened.convert("RGB")
        _pictures[path] = picture
    return picture


def _draw(shot: Shot) -> bytes:
    """A video frame as raw RGB."""
    x, y, width, height = _cut.picture
    camera = shot.camera
    out: Image.Image | None = None
    held = 0.0
    for layer in shot.layers:
        if layer.weight <= 0:
            continue
        picture = _picture(layer.path)
        area = layer.area
        sx, sy = picture.width / area.width, picture.height / area.height
        box = (
            max(0.0, (camera.left - area.left) * sx),
            max(0.0, (camera.top - area.top) * sy),
            min(float(picture.width), (camera.right - area.left) * sx),
            min(float(picture.height), (camera.bottom - area.top) * sy),
        )
        part = picture.resize((width, height), Image.Resampling.LANCZOS, box=box)
        held += layer.weight
        out = part if out is None else Image.blend(out, part, layer.weight / held)
    assert out is not None
    if (x, y, width, height) == (0, 0, _cut.width, _cut.height):
        return out.tobytes()
    canvas = Image.new("RGB", (_cut.width, _cut.height), BACKGROUND)
    canvas.paste(out, (x, y))
    return canvas.tobytes()


def _silo(placements: Sequence[Placed]) -> tuple[float, float] | None:
    silos = [p for p in placements if p.item == "rocket-silo" and p.count > 0]
    return (silos[-1].x, silos[-1].y) if silos else None


def _sublines(summary: dict[str, Any]) -> tuple[str, str]:
    """The title card's line and the vertical cut's band: where the run started,
    and whether a skill helped (decision 77). A run still going has no summary."""
    game = "Factorio in real time"
    if summary:
        where = "a fresh map" if summary.get("save") is None else "a saved game"
        game = f"Factorio from {where}, in real time"
    subline = f"{game},\\Nthrough a command-line tool."
    band = game
    if summary.get("skills") or summary.get("skill_sha256"):
        subline += "\\NAssisted run with a Factorio skill."
        band += "\\Nassisted run with a Factorio skill"
    return subline, band


def render(
    run_dir: Path,
    out: Path,
    cut: Cut,
    *,
    title: str | None = None,
    end_still: tuple[Path, Box] | None = None,
    ffmpeg: str = "ffmpeg",
) -> Path:
    """Make the video of the frames captured in `run_dir` and write it to `out`.
    `end_still` is a sharper picture of the map area its box covers, for the
    closing push-in."""
    directory = run_dir / "timelapse"
    frames = read_frames(directory)
    if len(frames) < 2:
        raise SystemExit(f"{directory} has {len(frames)} frames; a video needs 2 or more")
    summary_path = run_dir / "summary.json"
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
    # A run that stops at the launch stops its world before the next frame, so
    # the launch is in the summary and not in the frames.
    launched = summary.get("milestone_tick") if summary.get("until") == "rocket" else None
    if launched is not None and frames[-1].get("rocket_launched_tick") is None:
        frames = [*frames[:-1], {**frames[-1], "rocket_launched_tick": launched}]
    events = milestone_events(frames)
    outcome = outcome_line(frames, events)
    # The launch closes the video over the push-in, not as a caption.
    events = [event for event in events if event.title != "Rocket launched"]
    if title is None:
        model = summary.get("model")
        title = f"{model} builds a factory" if model else "An AI agent builds a factory"
    subline, band = _sublines(summary)

    placements = read_placements(run_dir / "world" / "calls.jsonl")
    targets, growth = camera_targets(frames, placements, cut)
    durations = frame_durations(growth, cut.body)
    starts = [sum(durations[:i]) for i in range(len(durations))]
    files = [directory / record["file"] for record in frames]
    areas = [Box(*record["box"]) for record in frames]
    shown = body_layers(files, areas, starts, durations, round(cut.body * cut.fps), cut.fps)
    cameras = smooth_camera(
        [targets[index] for _, _, index in shown], [area for _, area, _ in shown], cut.fps
    )
    body = [Shot(layers, camera) for (layers, _, _), camera in zip(shown, cameras, strict=True)]
    opening = _still(files[0], areas[0], cameras[0])
    focus = _silo(placements) or body[-1].camera.center
    least = _least(frames[-1], cut)
    finale = finale_shots(files[-1], areas[-1], least, body[-1].camera, focus, end_still, cut)
    shots = [opening] * round(cut.intro * cut.fps) + body + finale
    shots += [shots[-1]] * (round(cut.seconds * cut.fps) - len(shots))

    with tempfile.TemporaryDirectory(prefix="factobot-timelapse-") as scratch:
        ass = Path(scratch) / "overlay.ass"
        ass.write_text(
            overlay_ass(
                frames,
                events,
                cut,
                starts=[cut.intro + start for start in starts],
                started=_run_start(run_dir, frames),
                title=title,
                subline=subline,
                band=band,
                outcome=outcome,
            )
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        command = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            f"{cut.width}x{cut.height}",
            "-r",
            str(cut.fps),
            "-i",
            "-",
            "-vf",
            f"ass='{ass}',format=yuv420p",
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-crf",
            "18",
            # Under the upload limits of the common video sites (X takes 512 MB):
            # grass and ore are noisy and need many bits.
            "-maxrate",
            "16M",
            "-bufsize",
            "32M",
            "-movflags",
            "+faststart",
            os.fspath(out),
        ]
        encoder = subprocess.Popen(command, stdin=subprocess.PIPE)
        assert encoder.stdin is not None
        with multiprocessing.Pool(initializer=_start_drawing, initargs=(cut,)) as pool:
            for picture in pool.imap(_draw, shots, chunksize=8):
                encoder.stdin.write(picture)
        encoder.stdin.close()
        if encoder.wait() != 0:
            raise SystemExit(f"ffmpeg failed with exit code {encoder.returncode}")
    return out


def _size(text: str) -> tuple[int, int]:
    width, _, height = text.partition("x")
    return int(width), int(height)


def _area(text: str) -> tuple[float, float, float]:
    x, y, across = (float(part) for part in text.split(","))
    return x, y, across


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m factobot.timelapse",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    commands = parser.add_subparsers(dest="command", required=True)
    take = commands.add_parser("capture", help="capture frames of a running playtest's world")
    take.add_argument("run_dir", type=Path)
    take.add_argument("--every", type=float, default=30.0, help="game seconds between frames")
    take.add_argument("--size", type=_size, default=FRAME_SIZE, help="WIDTHxHEIGHT pixels")
    make = commands.add_parser("render", help="make the video from a run's frames")
    make.add_argument("run_dir", type=Path)
    make.add_argument("-o", "--out", type=Path, required=True, help="the .mp4 to write")
    make.add_argument(
        "--vertical",
        action="store_true",
        help=f"a {VERTICAL.width}x{VERTICAL.height} cut of {VERTICAL.seconds:.0f} s instead of "
        f"{LANDSCAPE.width}x{LANDSCAPE.height} of {LANDSCAPE.seconds:.0f} s",
    )
    make.add_argument("--seconds", type=float, help="length of the video")
    make.add_argument("--title", help="the title card's headline [default: from the model]")
    make.add_argument(
        "--end-still",
        type=Path,
        help="a sharper picture to push in on at the end, such as a 4K screenshot of the "
        "rocket silo from the run's last save; needs --end-still-area",
    )
    make.add_argument(
        "--end-still-area",
        type=_area,
        metavar="X,Y,TILES",
        help="the map point at the centre of --end-still and how many tiles across it shows",
    )
    args = parser.parse_args(argv)
    if args.command == "capture":
        capture(args.run_dir, args.every, args.size, poll_seconds=2.0)
    else:
        cut = VERTICAL if args.vertical else LANDSCAPE
        if args.seconds is not None:
            shortest = cut.intro + cut.finale + cut.outro + CAPTION_SECONDS
            if args.seconds <= shortest:
                parser.error(f"--seconds must be more than {shortest:g}")
            cut = replace(cut, seconds=args.seconds)
        if (args.end_still is None) != (args.end_still_area is None):
            parser.error("--end-still and --end-still-area go together")
        if shutil.which("ffmpeg") is None:
            parser.error("render needs ffmpeg on PATH")
        still = None
        if args.end_still is not None:
            x, y, across = args.end_still_area
            with Image.open(args.end_still) as picture:
                aspect = picture.width / picture.height
            still = (args.end_still, _at((x, y), across, aspect))
        print(render(args.run_dir, args.out, cut, title=args.title, end_still=still))
    return 0


if __name__ == "__main__":
    sys.exit(main())
