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

A playtest started with `--timelapse SECONDS` captures as it runs.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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
    """One video made from the frames: its size and how its time is spent."""

    width: int
    height: int
    seconds: float
    intro: float
    outro: float
    fps: int = 30

    @property
    def vertical(self) -> bool:
        return self.height > self.width


LANDSCAPE = Cut(1920, 1080, seconds=90.0, intro=3.5, outro=4.5)
VERTICAL = Cut(1080, 1920, seconds=25.0, intro=2.5, outro=3.5)
# Seconds a milestone caption stays up, and the least it stays when the next
# one is due sooner.
CAPTION_SECONDS = 2.8
MIN_CAPTION_SECONDS = 1.4
# The captions the short vertical cut keeps.
HEADLINE_TITLES = frozenset(PACK_TITLES.values()) | {"Rocket silo built", "Rocket launched"}
ORANGE = "&H001C9FFF"  # #FF9F1C, as ASS writes colours (alpha, blue, green, red)
URL = "github.com/8thlyr/factobot"


def _frame_seconds(cut: Cut, frames: int) -> float:
    """Seconds of video each frame gets: what the title card, the end card and a
    caption's hold on the last frame leave of the cut."""
    return (cut.seconds - cut.intro - cut.outro - CAPTION_SECONDS) / frames


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
    # Sizes scale with the shorter side, so both cuts keep the same proportions.
    unit = min(cut.width, cut.height) / 1080
    pad = round(40 * unit)
    big = round(60 * unit * (1.25 if cut.vertical else 1))
    styles = [
        # name, font, size, colour, box (BorderStyle 3 draws one), alignment, margin v
        (
            "Clock",
            "JetBrains Mono",
            round(34 * unit * (1.3 if cut.vertical else 1)),
            1,
            pad,
        ),
        (
            "Counts",
            "DejaVu Sans",
            round(26 * unit * (1.3 if cut.vertical else 1)),
            3,
            pad,
        ),
        (
            "Caption",
            "DejaVu Sans",
            big,
            8 if not cut.vertical else 2,
            round(70 * unit) if not cut.vertical else round(250 * unit),
        ),
        ("Card", "DejaVu Sans", round(48 * unit), 5, 0),
    ]
    lines = [
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
    ]
    for name, font, size, align, margin in styles:
        boxed = name in ("Clock", "Counts")
        lines.append(
            f"Style: {name},{font},{size},&H00FFFFFF,&H00FFFFFF,"
            f"{'&H58000000' if boxed else '&H00000000'},&H90000000,"
            f"{1 if name != 'Counts' else 0},0,0,0,100,100,0,0,"
            f"{3 if boxed else 1},{round(10 * unit) if boxed else round(3 * unit)},"
            f"{0 if boxed else round(2 * unit)},{align},{pad},{pad},{margin},1"
        )
    return "\n".join(lines)


def overlay_ass(
    frames: Sequence[dict[str, Any]],
    events: Sequence[Event],
    cut: Cut,
    *,
    started: datetime,
    title: str,
    outcome: str,
) -> str:
    """The video's text as an ASS subtitle script: title card, clock, building
    counts, milestone captions and end card, timed to `cut`."""
    step = _frame_seconds(cut, len(frames))
    end = cut.seconds
    unit = min(cut.width, cut.height) / 1080
    dim = (
        f"{{\\an7\\pos(0,0)\\bord0\\shad0\\1c&H000000&\\1a&H50&\\p1}}"
        f"m 0 0 l {cut.width} 0 {cut.width} {cut.height} 0 {cut.height}{{\\p0}}"
    )
    logo = f"{{\\fs{round(130 * unit)}\\c{ORANGE}\\b1}}factobot"
    rows = []

    def add(layer: int, start: float, stop: float, style: str, text: str) -> None:
        rows.append(
            f"Dialogue: {layer},{_ass_time(start)},{_ass_time(stop)},{style},,0,0,0,,{text}"
        )

    small = round(34 * unit)
    add(0, 0, cut.intro, "Card", f"{{\\fad(0,500)}}{dim}")
    add(
        1,
        0,
        cut.intro,
        "Card",
        f"{{\\fad(300,500)}}{logo}\\N{{\\fs{round(52 * unit)}\\c&HFFFFFF&\\b1}}{title}"
        f"\\N{{\\fs{small}\\b0\\c&HDDDDDD&}}Factorio from a fresh map, played in real time "
        "through a command-line tool",
    )
    add(0, end - cut.outro, end, "Card", f"{{\\fad(500,0)}}{dim}")
    add(
        1,
        end - cut.outro,
        end,
        "Card",
        f"{{\\fad(500,0)}}{logo}\\N{{\\fs{round(48 * unit)}\\b1\\c&HFFFFFF&}}{outcome}"
        f"\\N{{\\fs{small}\\b0\\c&HDDDDDD&}}{URL}",
    )
    body_end = end - cut.outro
    if cut.vertical:
        # The space above the picture holds what the video is about.
        add(
            1,
            cut.intro,
            body_end,
            "Card",
            f"{{\\an8\\pos({cut.width // 2},{round(110 * unit)})\\fs{round(64 * unit)}\\b1}}"
            f"{title}\\N{{\\fs{round(40 * unit)}\\b0\\c&HDDDDDD&}}Factorio from a fresh map,"
            "\\Nin real time",
        )
    # The clock and counts change when the text does, not on every frame.
    shown: list[tuple[float, str, str]] = []
    for index, record in enumerate(frames):
        at = cut.intro + index * step
        wall = (_parse_time(record["time"]) - started).total_seconds()
        sep = "\\N" if cut.vertical else "   "
        clock = f"game {_clock(record['tick'] / TICKS_PER_SECOND)}{sep}real {_clock(wall)}"
        parts = []
        for key, label in SHOWN_COUNTS:
            count = record["counts"].get(key, 0)
            parts.append(f"{count:,} {label if count != 1 else label.removesuffix('s')}")
        if cut.vertical:
            counts = "\\N".join("  ".join(parts[i : i + 2]) for i in range(0, len(parts), 2))
        else:
            counts = sep.join(parts)
        if not shown or shown[-1][1:] != (clock, counts):
            shown.append((at, clock, counts))
    for (at, clock, counts), following in zip(shown, [*shown[1:], None], strict=True):
        stop = following[0] if following else body_end
        add(2, at, stop, "Clock", clock)
        add(2, at, stop, "Counts", counts)
    detail = round(30 * unit * (1.3 if cut.vertical else 1))
    if cut.vertical:
        # 25 seconds hold only the science tiers and the rocket.
        events = [event for event in events if event.title in HEADLINE_TITLES]
    wanted = [cut.intro + event.frame * step for event in events]
    for event, times in zip(events, caption_times(wanted, body_end), strict=True):
        if times is None:
            continue
        add(
            3,
            *times,
            "Caption",
            f"{{\\fad(200,350)}}{event.title}\\N{{\\fs{detail}\\b0}}"
            f"after {_clock(event.tick / TICKS_PER_SECOND)} of game time",
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
    """The end card's sentence: the rocket's game time, else the last milestone's."""
    last = frames[-1]
    launched = last.get("rocket_launched_tick")
    if launched is not None:
        return f"Rocket launched after {_clock(launched / TICKS_PER_SECOND)} of game time"
    hours = _clock(last["tick"] / TICKS_PER_SECOND)
    if events:
        return f"{events[-1].title} · {hours} of game time"
    return f"{hours} of game time"


def _video_filter(cut: Cut, ass: Path) -> str:
    """The ffmpeg filter graph from the concatenated frames to the finished picture.

    `framerate` blends neighbouring frames, so frames shorter than the output's
    frame time fade into each other instead of jumping."""
    subtitles = f"ass='{ass}'"
    smooth = f"framerate=fps={cut.fps}:interp_start=0:interp_end=255:scene=100"
    if not cut.vertical:
        return (
            f"[0:v]{smooth},scale={cut.width}:{cut.height}:flags=lanczos,"
            f"setsar=1,format=yuv420p,{subtitles}[v]"
        )
    # Vertical: a square from the middle of the frame, where the factory is,
    # over a blurred, darkened copy of the frame that fills the rest of the screen.
    return (
        f"[0:v]{smooth},split[a][b];"
        f"[a]scale=-2:{cut.height},crop={cut.width}:{cut.height},gblur=sigma=40,"
        "eq=brightness=-0.22:saturation=0.8[bg];"
        f"[b]crop=ih:ih,scale={cut.width}:{cut.width}:flags=lanczos[fg];"
        f"[bg][fg]overlay=0:(H-h)/2,setsar=1,format=yuv420p,{subtitles}[v]"
    )


def render(
    run_dir: Path,
    out: Path,
    cut: Cut,
    *,
    title: str | None = None,
    ffmpeg: str = "ffmpeg",
) -> Path:
    """Make the video of the frames captured in `run_dir` and write it to `out`."""
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
    if title is None:
        model = summary.get("model")
        title = f"{model} builds a factory" if model else "An AI agent builds a factory"
    step = _frame_seconds(cut, len(frames))
    with tempfile.TemporaryDirectory(prefix="factobot-timelapse-") as scratch:
        work = Path(scratch)
        # The first and last frames are listed twice, so the title card, the
        # last caption and the end card sit on a still picture.
        first, last = directory / frames[0]["file"], directory / frames[-1]["file"]
        entries = [(first, cut.intro)]
        entries += [(directory / record["file"], step) for record in frames]
        entries += [(last, CAPTION_SECONDS + cut.outro), (last, cut.outro)]
        (work / "frames.txt").write_text(
            "ffconcat version 1.0\n"
            + "".join(
                f"file '{path.absolute()}'\nduration {seconds:.6f}\n" for path, seconds in entries
            )
        )
        ass = work / "overlay.ass"
        ass.write_text(
            overlay_ass(
                frames,
                events,
                cut,
                started=_run_start(run_dir, frames),
                title=title,
                outcome=outcome_line(frames, events),
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
            "concat",
            "-safe",
            "0",
            "-i",
            os.fspath(work / "frames.txt"),
            "-filter_complex",
            _video_filter(cut, ass),
            "-map",
            "[v]",
            "-t",
            f"{cut.seconds:.3f}",
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-crf",
            "18",
            # Under the upload limits of the common video sites (X takes 512 MB):
            # blended frames of grass and ore are noisy and need many bits.
            "-maxrate",
            "16M",
            "-bufsize",
            "32M",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            os.fspath(out),
        ]
        subprocess.run(command, check=True)
    return out


def _size(text: str) -> tuple[int, int]:
    width, _, height = text.partition("x")
    return int(width), int(height)


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
        f"{LANDSCAPE.width}x{LANDSCAPE.height}",
    )
    make.add_argument("--seconds", type=float, help="length of the video")
    make.add_argument("--title", help="the title card's headline [default: from the model]")
    args = parser.parse_args(argv)
    if args.command == "capture":
        capture(args.run_dir, args.every, args.size, poll_seconds=2.0)
    else:
        cut = VERTICAL if args.vertical else LANDSCAPE
        if args.seconds is not None:
            shortest = cut.intro + cut.outro + CAPTION_SECONDS
            if args.seconds <= shortest:
                parser.error(f"--seconds must be more than {shortest:g}")
            cut = Cut(cut.width, cut.height, args.seconds, cut.intro, cut.outro, cut.fps)
        if shutil.which("ffmpeg") is None:
            parser.error("render needs ffmpeg on PATH")
        print(render(args.run_dir, args.out, cut, title=args.title))
    return 0


if __name__ == "__main__":
    sys.exit(main())
