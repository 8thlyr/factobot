"""Timelapse framing and captions: the picture keeps the factory in view without
jumping or pumping, and captions name what happened during the run, at the tick
it happened."""

from __future__ import annotations

from typing import Any

from factobot.timelapse import (
    CAPTION_SECONDS,
    MIN_CAPTION_SECONDS,
    Box,
    caption_times,
    core_box,
    milestone_events,
    next_frame,
)


def test_crowded_captions_are_shortened_or_dropped_never_late() -> None:
    # Five firsts within a second of video, then one on its own.
    wanted = [10.0, 10.2, 10.4, 10.6, 10.8, 30.0]
    shown = caption_times(wanted, end=85.0)
    kept = [(at, times) for at, times in zip(wanted, shown, strict=True) if times]
    assert len(kept) < len(wanted)
    for (at, (start, stop)), following in zip(kept, [*kept[1:], None], strict=True):
        assert at <= start <= at + MIN_CAPTION_SECONDS
        assert stop - start >= MIN_CAPTION_SECONDS
        if following is not None:
            assert stop <= following[1][0]
    assert shown[-1] == (30.0, 30.0 + CAPTION_SECONDS)
    assert caption_times([84.0], end=85.0) == [(84.0, 85.0)]


def test_the_frame_zooms_out_to_the_factory_then_settles_in_slowly() -> None:
    frame = next_frame(None, None, (10.0, 5.0))
    assert frame.center == (10.0, 5.0)
    assert round(frame.width / frame.height, 6) == round(16 / 9, 6)

    # The factory spreads east: the frame zooms out over several frames.
    factory = Box(-20, -10, 300, 40)
    widths = []
    for _ in range(30):
        previous = frame
        frame = next_frame(frame, factory, (0.0, 0.0))
        # It only zooms out; its centre may drift toward the factory's.
        assert frame.width >= previous.width
        assert frame.left <= previous.left and frame.right >= previous.right
        assert round(frame.width / frame.height, 6) == round(16 / 9, 6)
        widths.append(frame.width)
    assert widths[0] < widths[-1] / 2, "it moved there in one jump"
    assert frame.left <= factory.left and frame.right >= factory.right - 0.5
    assert frame.top <= factory.top and frame.bottom >= factory.bottom

    # The factory's box gets smaller: the frame closes in a little each frame,
    # never by more than a tenth, and never out again.
    smaller = Box(0, 0, 40, 30)
    for _ in range(80):
        previous = frame
        frame = next_frame(frame, smaller, (0.0, 0.0))
        assert previous.width * 0.9 <= frame.width <= previous.width
    assert frame.left <= smaller.left and frame.right >= smaller.right
    assert frame.width < 100  # the smaller box with its margin, at 16:9


def test_the_core_leaves_out_a_far_outpost_and_the_line_to_it() -> None:
    chunks: dict[str, list[float]] = {
        "0,0": [300, 2, 3, 30, 31],
        "1,0": [250, 33, 1, 60, 29],
        "0,1": [200, 1, 33, 31, 50],
        # A pipe line east and an oil outpost at its end, as in the seed 1 run
        # of 2026-11-14.
        **{f"{x},0": [3, 32 * x + 1, 10, 32 * x + 30, 11] for x in range(2, 10)},
        "10,0": [40, 321, 8, 330, 20],
    }
    assert core_box(chunks) == Box(1, 1, 60, 50)
    assert core_box([]) is None


def _frame(
    tick: int, counts: dict[str, int], automated: dict[str, int], **more: Any
) -> dict[str, Any]:
    return {"tick": tick, "counts": counts, "automated": automated, **more}


def test_captions_name_each_first_at_its_own_tick() -> None:
    frames = [
        _frame(0, {}, {}),
        _frame(1800, {"generator": 1}, {}),
        _frame(3600, {"generator": 2, "assembling-machine": 1}, {"automation-science-pack": 3100}),
        _frame(5400, {"generator": 2, "rocket-silo": 1}, {}, rocket_launched_tick=5300),
    ]
    events = [(event.frame, event.tick, event.title) for event in milestone_events(frames)]
    assert events == [
        (1, 1800, "Steam power online"),
        (2, 3600, "First assembling machine"),
        (2, 3100, "Red science automated"),
        (3, 5400, "Rocket silo built"),
        (3, 5300, "Rocket launched"),
    ]


def test_a_run_from_a_save_gets_no_caption_for_what_it_already_had() -> None:
    frames = [
        _frame(900_000, {"generator": 4, "lab": 10}, {"automation-science-pack": 200_000}),
        _frame(
            901_800,
            {"generator": 4, "lab": 10, "pumpjack": 2},
            {"automation-science-pack": 200_000},
        ),
    ]
    assert [event.title for event in milestone_events(frames)] == ["Oil pumping"]
