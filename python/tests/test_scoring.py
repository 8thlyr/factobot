"""Decision 18's throughput gate and decision 23's score, on synthetic reports:
no test world runs the ten game minutes a passing gate needs."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from inspect_ai import eval as inspect_eval
from inspect_ai import task_with
from inspect_ai.model import ModelName
from inspect_ai.scorer import Score, Target
from inspect_ai.solver import Generate, Solver, TaskState, solver

from factobot.tasks import RED_SCIENCE, TICKS_PER_MINUTE, stage_score, stage_task, sustained_at

START = 5
MILESTONE = 2 * TICKS_PER_MINUTE + START
# Ten packs by the end of minute 3, then ten more each minute: 100 packs over
# minutes 4 to 13, the first ten whole minutes after the milestone. Counting
# from the minute the milestone falls in (minutes 3 to 12) would also reach
# 100, a minute early, so the data tells the ceiling from a floor.
MADE_BY_MINUTE = [0, 0, *range(10, 121, 10)]
SUSTAINED = 13 * TICKS_PER_MINUTE


def report() -> dict[str, Any]:
    return {
        "start_tick": START,
        "tick": SUSTAINED + 100,
        "milestone_tick": MILESTONE,
        "machine_made_by_minute": MADE_BY_MINUTE,
        "paused_seconds": 0.0,
        "outages": 0,
    }


def score(throughput: float | None, cap_ticks: int) -> Score:
    state = TaskState(ModelName("mockllm/model"), sample_id=1, epoch=1, input="", messages=[])
    state.store.set("factobot", report())
    scorer = stage_score(RED_SCIENCE, throughput=throughput, cap_ticks=cap_ticks)
    result = asyncio.run(scorer(state, Target("")))
    assert result is not None
    return result


def test_the_gate_holds_at_the_end_of_the_first_ten_minutes_that_meet_it() -> None:
    assert sustained_at(report(), 10) == SUSTAINED


def test_the_gate_never_holds_when_no_ten_minutes_meet_it() -> None:
    assert sustained_at(report(), 10.01) is None


def test_without_a_gate_a_milestone_exactly_at_the_cap_counts() -> None:
    result = score(throughput=None, cap_ticks=MILESTONE - START)
    assert (result.metadata or {})["reached"] is True
    assert result.value == pytest.approx(RED_SCIENCE.reference_ticks / (MILESTONE - START))


def test_without_a_gate_a_milestone_one_tick_after_the_cap_scores_as_unreached() -> None:
    cap = MILESTONE - START - 1
    result = score(throughput=None, cap_ticks=cap)
    assert (result.metadata or {})["reached"] is False
    assert result.value == pytest.approx(0.5 * RED_SCIENCE.reference_ticks / cap)


def test_a_gate_sustained_exactly_at_the_cap_scores_from_the_milestone_tick() -> None:
    result = score(throughput=10, cap_ticks=SUSTAINED - START)
    meta = result.metadata or {}
    assert meta["reached"] is True
    assert meta["gate"] == {"throughput": 10, "sustained_at_tick": SUSTAINED}
    assert result.value == pytest.approx(RED_SCIENCE.reference_ticks / (MILESTONE - START))


def test_a_gate_sustained_one_tick_after_the_cap_scores_as_unreached() -> None:
    cap = SUSTAINED - START - 1
    result = score(throughput=10, cap_ticks=cap)
    assert (result.metadata or {})["reached"] is False
    assert result.value == pytest.approx(0.5 * RED_SCIENCE.reference_ticks / cap)


@solver
def outage_of(seconds: dict[int, float]) -> Solver:
    """Stands in for `play`: a report with the given seconds paused, per seed."""

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        state.store.set("factobot", {**report(), "paused_seconds": seconds[state.metadata["seed"]]})
        return state

    return solve


def test_a_void_seed_is_an_error_while_the_other_seeds_still_score(tmp_path: Path) -> None:
    task = stage_task(RED_SCIENCE, seeds=[1, 2, 3], pause_cap=60, cap_ticks=SUSTAINED)
    task = task_with(task, solver=outage_of({1: 61.0, 2: 0.0, 3: 59.0}))
    log = inspect_eval(task, model="mockllm/model", log_dir=str(tmp_path), display="none")[0]

    assert log.status == "success", log.error
    assert log.samples is not None
    samples = {sample.id: sample for sample in log.samples}
    assert samples["seed-1"].error is not None
    assert "void: paused 61 s" in samples["seed-1"].error.message
    for seed in ("seed-2", "seed-3"):
        assert samples[seed].error is None
        assert samples[seed].scores is not None
    assert log.results is not None
    assert log.results.completed_samples == 2
