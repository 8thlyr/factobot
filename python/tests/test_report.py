"""The leaderboard reads playtest summaries and Inspect logs, without a world."""

from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any

import pytest

from factobot.report import (
    UNREACHED_SCORE,
    build,
    collect,
)
from factobot.tasks import TICKS_PER_HOUR


def ticks(hours: float) -> int:
    return round(hours * TICKS_PER_HOUR)


def summary(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "task": "Reach red science",
        "agent": "claude",
        "model": "opus",
        "seed": 1,
        "save": None,
        "skills": [],
        "until": "automation-science-pack",
        "start_tick": 0,
        "milestone_tick": ticks(5),
        "end_tick": ticks(5),
        "timed_out": False,
        "stopped": False,
        "wall_seconds": 90.0,
        "turns": 4,
        "cost_usd": 1.5,
        "exit_code": 0,
    }
    base.update(overrides)
    return base


def write_run(root: Path, name: str, **overrides: Any) -> Path:
    directory = root / name
    directory.mkdir(parents=True)
    path = directory / "summary.json"
    path.write_text(json.dumps(summary(**overrides)) + "\n")
    return directory


def test_a_fresh_run_at_the_reference_scores_one(tmp_path: Path) -> None:
    write_run(tmp_path, "red-1")
    runs, warnings = collect([tmp_path])
    assert warnings == []
    report = build(runs)
    row = report.benchmark[0][1][0]
    assert row.median_score() == pytest.approx(1)


def test_a_save_uses_the_stage_gap(tmp_path: Path) -> None:
    green = ticks(7)
    write_run(
        tmp_path,
        "saved",
        model="from-save",
        until="logistic-science-pack",
        save="/tmp/old/save.zip",
        milestone_tick=green,
        end_tick=green,
    )
    write_run(
        tmp_path,
        "fresh",
        model="fresh-map",
        until="logistic-science-pack",
        milestone_tick=green,
        end_tick=green,
    )
    report = build(*collect([tmp_path]))
    rows = {row.model: row for row in report.benchmark[0][1]}
    assert rows["from-save"].median_score() == pytest.approx(1)
    assert rows["fresh-map"].median_score() == pytest.approx(12 / 7)


def test_a_timeout_scores_the_unreached_floor_and_stays_in_the_median(tmp_path: Path) -> None:
    write_run(tmp_path, "done", seed=1)
    write_run(tmp_path, "late", seed=2, milestone_tick=None, end_tick=ticks(10), timed_out=True)
    report = build(*collect([tmp_path]))
    row = report.benchmark[0][1][0]
    assert len(row.runs) == 2
    assert row.median_score() == pytest.approx(statistics.median([1.0, UNREACHED_SCORE]))
    assert {run.status for run in row.runs} == {"reached", "not reached"}


def test_a_milestone_past_the_cap_scores_the_unreached_floor(tmp_path: Path) -> None:
    write_run(tmp_path, "slow", milestone_tick=ticks(11), end_tick=ticks(11))
    report = build(*collect([tmp_path]))
    (run,) = report.benchmark[0][1][0].runs
    assert run.score == UNREACHED_SCORE
    assert run.status == "not reached"


def test_a_stopped_run_stays_out_of_the_median(tmp_path: Path) -> None:
    write_run(tmp_path, "done", seed=1)
    write_run(tmp_path, "halted", seed=2, milestone_tick=None, stopped=True, end_tick=ticks(1))
    report = build(*collect([tmp_path]))
    row = report.benchmark[0][1][0]
    assert len(row.runs) == 1
    assert row.median_score() == pytest.approx(1)


def test_an_assisted_run_is_not_a_benchmark_score(tmp_path: Path) -> None:
    write_run(tmp_path, "bench", model="bench-model")
    write_run(
        tmp_path,
        "skill",
        model="skill-model",
        agent="omp",
        until="rocket",
        skills=["factorio-rocket"],
        milestone_tick=ticks(25),
        end_tick=ticks(25),
    )
    write_run(
        tmp_path,
        "skill-late",
        model="skill-stop",
        until="automation-science-pack",
        skills=["factorio-rocket"],
        milestone_tick=None,
        timed_out=True,
        end_tick=ticks(10),
    )
    report = build(*collect([tmp_path]))
    models = [row.model for _, group in report.benchmark for row in group]
    assert models == ["bench-model"]
    reached = next(run for run in report.runs if run.model == "skill-model")
    assert reached.score is None
    assert reached.ratio == pytest.approx(2)
    late = next(run for run in report.runs if run.model == "skill-stop")
    assert late.score is None
