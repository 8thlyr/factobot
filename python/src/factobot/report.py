"""Leaderboard for factobot runs.

    python -m factobot.report target/playtests -o target/reports

Reads each playtest `summary.json` and any Inspect `.eval` log and writes
`leaderboard.md` and `leaderboard.html`. A benchmark run scores decision 23:
reference time over the agent's game time, as a median per harness and model
(decision 20). A run with a skill is assisted (decisions 48 and 77) and is
listed apart. The HTML charts are inline SVG.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import textwrap
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any

from inspect_ai.log import read_eval_log

from factobot.tasks import CAP_FACTOR, TICKS_PER_HOUR, TICKS_PER_SECOND

# Half of finishing exactly at the game-time cap (decision 23). With the 2x cap
# this is 0.25, for every tier.
UNREACHED_SCORE = 0.5 / CAP_FACTOR

# Keys that mark a JSON object as a playtest summary. An empty object is not one.
SUMMARY_KEYS = ("agent", "model", "until", "milestone_tick", "fac_calls", "start_tick")

WRAP = 90
BAR_WIDTH = 24

SCORE_NOTE = (
    "Bars are the median score, scaled so 1.00 and the highest median both fit. Longer is better."
)
HOURS_NOTE = "Shorter is faster. The number is the median game time."
SCORE_CAPTION = (
    "Bars are the median. Dots are each run. The dashed line is an average player, score 1.00."
)
HOURS_CAPTION = "Bars are the median game time. Dots are each run."
HOURS_CAPTION_REF = HOURS_CAPTION + " The dashed line is the reference time."


@dataclass(frozen=True)
class Tier:
    """One scored goal. Cumulative hours are from a fresh start (decision 21).

    The gap is that tier's own step, the difference from the previous cumulative
    hour. Decision 22's ladder folds purple and yellow into one 17 h stage, so a
    save that stopped at yellow alone is scored against a 2 h gap and the report
    says so.
    """

    stage: str
    goal: str
    label: str
    short: str
    gap_hours: float
    cumulative_hours: float

    def reference_hours(self, from_save: bool) -> float:
        return self.gap_hours if from_save else self.cumulative_hours


TIERS: tuple[Tier, ...] = (
    Tier("red_science", "automation-science-pack", "Red science", "Red", 5, 5),
    Tier("green_science", "logistic-science-pack", "Green science", "Green", 7, 12),
    Tier("blue_science", "chemical-science-pack", "Blue science", "Blue", 13, 25),
    Tier("purple_science", "production-science-pack", "Purple science", "Purple", 15, 40),
    Tier("yellow_science", "utility-science-pack", "Yellow science", "Yellow", 2, 42),
    Tier("rocket", "rocket", "Rocket", "Rocket", 8, 50),
)
BY_GOAL = {tier.goal: tier for tier in TIERS}
BY_STAGE = {tier.stage: tier for tier in TIERS}


def pair_label(agent: str, model: str, *, from_save: bool, skills: tuple[str, ...] = ()) -> str:
    text = f"{agent} / {model}"
    if skills:
        text += " [" + ", ".join(skills) + "]"
    if from_save:
        text += " (from a save)"
    return text


def median_of(values: Sequence[float]) -> float | None:
    if not values:
        return None
    return float(statistics.median(values))


def sum_of(values: Sequence[float]) -> float | None:
    if not values:
        return None
    return float(sum(values))


@dataclass(frozen=True)
class Run:
    """One sample: a playtest summary, or one seed of an Inspect log."""

    name: str
    source: str
    agent: str
    model: str
    seed: int | None
    epoch: int | None
    assisted: bool
    skills: tuple[str, ...]
    tier: Tier | None
    goal: str | None
    from_save: bool
    game_ticks: int | None
    ratio: float | None
    score: float | None
    wall_seconds: float | None
    cost_usd: float | None
    turns: int | None
    status: str
    task: str


@dataclass(frozen=True)
class ScoreRow:
    """Median benchmark score for one harness, model, tier and map."""

    tier: Tier
    agent: str
    model: str
    from_save: bool
    runs: tuple[Run, ...]

    def label(self) -> str:
        return pair_label(self.agent, self.model, from_save=self.from_save)

    def scores(self) -> list[float]:
        values = [run.score for run in self.runs if run.score is not None]
        if not values:
            raise RuntimeError("a score row needs a score")
        return values

    def median_score(self) -> float:
        return float(statistics.median(self.scores()))

    def stderr(self) -> float | None:
        values = self.scores()
        if len(values) < 2:
            return None
        return statistics.stdev(values) / math.sqrt(len(values))

    def median_ticks(self) -> float | None:
        return median_of([run.game_ticks for run in self.runs if run.game_ticks is not None])

    def median_wall(self) -> float | None:
        return median_of([run.wall_seconds for run in self.runs if run.wall_seconds is not None])

    def cost_sum(self) -> float | None:
        return sum_of([run.cost_usd for run in self.runs if run.cost_usd is not None])


@dataclass(frozen=True)
class TimeRow:
    """Assisted runs that reached the goal. The ratio is not a benchmark score."""

    tier: Tier
    agent: str
    model: str
    from_save: bool
    skills: tuple[str, ...]
    runs: tuple[Run, ...]

    def label(self) -> str:
        return pair_label(self.agent, self.model, from_save=self.from_save, skills=self.skills)

    def median_ticks(self) -> float:
        ticks = median_of([run.game_ticks for run in self.runs if run.game_ticks is not None])
        if ticks is None:
            raise RuntimeError("an assisted row needs a game time")
        return ticks

    def median_ratio(self) -> float:
        ratios = median_of([run.ratio for run in self.runs if run.ratio is not None])
        if ratios is None:
            raise RuntimeError("an assisted row needs a ratio")
        return ratios

    def median_wall(self) -> float | None:
        return median_of([run.wall_seconds for run in self.runs if run.wall_seconds is not None])

    def cost_sum(self) -> float | None:
        return sum_of([run.cost_usd for run in self.runs if run.cost_usd is not None])


@dataclass(frozen=True)
class Headline:
    """Geometric mean of one pair's median on every tier (decision 23)."""

    agent: str
    model: str
    from_save: bool
    score: float
    tiers: tuple[tuple[str, float], ...]

    def label(self) -> str:
        return pair_label(self.agent, self.model, from_save=self.from_save)


@dataclass(frozen=True)
class Report:
    runs: tuple[Run, ...]
    warnings: tuple[str, ...]
    benchmark: tuple[tuple[Tier, tuple[ScoreRow, ...]], ...]
    assisted: tuple[tuple[Tier, tuple[TimeRow, ...]], ...]
    headlines: tuple[Headline, ...]


# Loading ------------------------------------------------------------------


def collect(paths: Sequence[Path]) -> tuple[list[Run], list[str]]:
    """Read every summary and eval log under `paths`.

    The second list is warnings for files that were skipped. A directory is
    searched for `summary.json` and `*.eval` only, so a run's other JSON stays
    out of the board.
    """
    warnings: list[str] = []
    files: list[tuple[Path, str]] = []
    for path in paths:
        if not path.exists():
            warnings.append(f"{path}: not found")
            continue
        if path.is_dir():
            summaries = sorted(path.rglob("summary.json"))
            evals = sorted(path.rglob("*.eval"))
            if not summaries and not evals:
                warnings.append(f"{path}: no summary.json or .eval log under it")
            files.extend((item, "summary") for item in summaries)
            files.extend((item, "eval") for item in evals)
            continue
        kind = "eval" if path.suffix == ".eval" else "json"
        files.append((path, kind))

    runs: list[Run] = []
    seen: set[Path] = set()
    for path, kind in files:
        try:
            resolved = path.resolve()
        except OSError as err:
            warnings.append(f"{path}: {err}")
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        try:
            loaded, notes = load_file(path, kind)
        except OSError as err:
            warnings.append(f"{path}: {err}")
            continue
        warnings.extend(notes)
        runs.extend(loaded)
    return runs, warnings


def load_file(path: Path, kind: str) -> tuple[list[Run], list[str]]:
    if kind == "eval":
        return load_eval(path)
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as err:
        return [], [f"{path}: {err.msg} (line {err.lineno})"]
    if isinstance(data, dict):
        return load_summary_dict(data, path, None)
    if isinstance(data, list):
        runs: list[Run] = []
        notes: list[str] = []
        for index, item in enumerate(data, start=1):
            if not isinstance(item, dict):
                notes.append(f"{path}: item {index} is not an object")
                continue
            loaded, item_notes = load_summary_dict(item, path, index)
            notes.extend(item_notes)
            runs.extend(loaded)
        return runs, notes
    return [], [f"{path}: not a run summary"]


def load_summary_dict(
    data: dict[str, Any], path: Path, index: int | None
) -> tuple[list[Run], list[str]]:
    if not any(key in data for key in SUMMARY_KEYS):
        where = f"{path} item {index}" if index is not None else str(path)
        return [], [f"{where}: not a run summary"]
    run = run_from_summary(data, path, index)
    notes: list[str] = []
    if run.goal is not None and run.tier is None:
        notes.append(f"{run.name}: no tier for goal {run.goal!r}")
    return [run], notes


def run_from_summary(data: dict[str, Any], path: Path, index: int | None) -> Run:
    goal = text_or_none(data.get("until"))
    tier = BY_GOAL.get(goal) if goal is not None else None
    skills = as_skills(data.get("skills"))
    assisted = bool(skills)
    save = data.get("save")
    from_save = isinstance(save, str) and bool(save.strip())
    start = as_int(data.get("start_tick"))
    end = as_int(data.get("end_tick"))
    milestone = as_int(data.get("milestone_tick"))
    reached = (
        tier is not None and milestone is not None and start is not None and milestone >= start
    )
    elapsed = end - start if start is not None and end is not None and end >= start else None
    reference = tier.reference_hours(from_save) if tier is not None else None
    ratio: float | None = None
    ticks = elapsed
    if reached and start is not None and milestone is not None and reference is not None:
        ticks = milestone - start
        # Same floor as the ladder scorer: a milestone on the start tick is one tick.
        ratio = reference * TICKS_PER_HOUR / max(ticks, 1)
    score, status = summary_score(
        assisted=assisted,
        tier=tier,
        reached=reached,
        ratio=ratio,
        timed_out=data.get("timed_out") is True,
        stopped=data.get("stopped") is True,
    )
    wall = as_float(data.get("wall_seconds"))
    turns = as_int(data.get("turns"))
    return Run(
        name=summary_name(data, path, index),
        source=str(path) if index is None else f"{path}#{index}",
        agent=text_field(data, "agent", "(no harness)"),
        model=text_field(data, "model", "(no model)"),
        seed=as_int(data.get("seed")),
        epoch=None,
        assisted=assisted,
        skills=skills,
        tier=tier,
        goal=goal,
        from_save=from_save,
        game_ticks=ticks,
        ratio=ratio,
        score=score,
        wall_seconds=wall if wall is not None and wall >= 0 else None,
        cost_usd=as_float(data.get("cost_usd")),
        turns=None if turns is None or turns < 0 else turns,
        status=status,
        task=text_field(data, "task", ""),
    )


def summary_score(
    *,
    assisted: bool,
    tier: Tier | None,
    reached: bool,
    ratio: float | None,
    timed_out: bool,
    stopped: bool,
) -> tuple[float | None, str]:
    """Benchmark score, and a status word. Assisted runs never get a score."""
    if reached and ratio is not None:
        if assisted:
            return None, "reached"
        # A playtest's limit is wall time, so a run can reach the goal after
        # the game-time cap (decision 20). That stage counts as unreached.
        if ratio < 1 / CAP_FACTOR:
            return UNREACHED_SCORE, "not reached"
        return ratio, "reached"
    if timed_out and tier is not None and not assisted:
        return UNREACHED_SCORE, "not reached"
    if stopped:
        return None, "stopped"
    if assisted:
        return None, "not reached"
    if tier is not None:
        return None, "unfinished"
    return None, "no goal"


def summary_name(data: dict[str, Any], path: Path, index: int | None) -> str:
    out = data.get("out_dir")
    if isinstance(out, str) and out.strip():
        name = Path(out).name
    elif path.name == "summary.json":
        name = path.parent.name
    else:
        name = path.stem
    if index is not None:
        name = f"{name}#{index}"
    return name or path.stem


def load_eval(path: Path) -> tuple[list[Run], list[str]]:
    """One Inspect log. The recorded `stage_score` is used as it stands.

    A void or broken seed is an error in the log (decision 45), so it stays out
    of the median. Recomputing the score here would hide that.
    """
    try:
        log: Any = read_eval_log(str(path))
    except Exception as err:
        return [], [f"{path}: {type(err).__name__}: {err}"]
    samples = list(log.samples or [])
    if not samples:
        return [], [f"{path}: no samples"]
    task = eval_task(log)
    hint = tier_from_task(task)
    if hint is None and not any(sample_score(sample) is not None for sample in samples):
        return [], [f"{path}: no factobot stage score"]
    model = eval_model(log)
    runs = [run_from_sample(sample, path, model, task, hint) for sample in samples]
    return runs, []


def run_from_sample(sample: Any, path: Path, model: str, task: str, hint: Tier | None) -> Run:
    found = sample_score(sample)
    meta = found[1] if found is not None else {}
    stage = meta.get("stage")
    tier = BY_STAGE[stage] if isinstance(stage, str) and stage in BY_STAGE else hint
    error = getattr(sample, "error", None)
    if error is not None:
        message = getattr(error, "message", "") or ""
        status = "void" if "void:" in message else "error"
        return sample_run(sample, path, model, task, tier, None, None, None, status)
    if found is None or tier is None:
        return sample_run(sample, path, model, task, tier, None, None, None, "unfinished")
    value, meta = found
    reached = meta.get("reached") is True
    ticks = as_int(meta.get("stage_ticks"))
    if ticks is not None and ticks < 0:
        ticks = None
    status = "reached" if reached else "not reached"
    ratio = value if reached else None
    return sample_run(sample, path, model, task, tier, ticks, ratio, value, status)


def sample_run(
    sample: Any,
    path: Path,
    model: str,
    task: str,
    tier: Tier | None,
    game_ticks: int | None,
    ratio: float | None,
    score: float | None,
    status: str,
) -> Run:
    metadata = getattr(sample, "metadata", None) or {}
    seed = as_int(metadata.get("seed")) if isinstance(metadata, dict) else None
    wall = as_float(getattr(sample, "total_time", None))
    return Run(
        name=f"{path.stem}:{getattr(sample, 'id', '?')}",
        source=str(path),
        agent="inspect",
        model=model,
        seed=seed,
        epoch=as_int(getattr(sample, "epoch", None)),
        assisted=False,
        skills=(),
        tier=tier,
        goal=None if tier is None else tier.goal,
        from_save=False,
        game_ticks=game_ticks,
        ratio=ratio,
        score=score,
        wall_seconds=wall if wall is not None and wall >= 0 else None,
        cost_usd=None,
        turns=None,
        status=status,
        task=task,
    )


def sample_score(sample: Any) -> tuple[float, dict[str, Any]] | None:
    scores = getattr(sample, "scores", None) or {}
    if not isinstance(scores, dict):
        return None
    chosen = scores.get("stage_score")
    if chosen is None:
        for score in scores.values():
            meta = getattr(score, "metadata", None) or {}
            stage = meta.get("stage") if isinstance(meta, dict) else None
            if isinstance(stage, str) and stage in BY_STAGE:
                chosen = score
                break
    if chosen is None:
        return None
    value = as_float(getattr(chosen, "value", None))
    if value is None or value <= 0:
        return None
    meta = getattr(chosen, "metadata", None) or {}
    if not isinstance(meta, dict):
        meta = {}
    return value, dict(meta)


def eval_model(log: Any) -> str:
    model = getattr(getattr(log, "eval", None), "model", None)
    if isinstance(model, str) and model.strip():
        return model.strip()
    name = getattr(model, "name", None)
    if isinstance(name, str) and name.strip():
        return name.strip()
    return "(no model)"


def eval_task(log: Any) -> str:
    task = getattr(getattr(log, "eval", None), "task", "")
    return task if isinstance(task, str) else ""


def tier_from_task(task: str) -> Tier | None:
    return BY_STAGE.get(task.rsplit("/", 1)[-1])


def as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and math.isfinite(value) and value.is_integer():
        return int(value)
    return None


def as_float(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return number


def as_skills(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    names = []
    for item in value:
        text = text_or_none(item)
        if text is not None:
            names.append(text)
    return tuple(names)


def text_or_none(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return " ".join(value.split())
    return None


def text_field(data: dict[str, Any], key: str, fallback: str) -> str:
    return text_or_none(data.get(key)) or fallback


# Grouping -----------------------------------------------------------------


def build(runs: Sequence[Run], warnings: Sequence[str] = ()) -> Report:
    """Group runs into benchmark rows, assisted rows and a headline."""
    ordered = tuple(sorted(runs, key=run_sort))
    benchmark = benchmark_sections(ordered)
    return Report(
        runs=ordered,
        warnings=(*warnings, *duplicate_notes(ordered)),
        benchmark=benchmark,
        assisted=assisted_sections(ordered),
        headlines=headline_rows(benchmark),
    )


def run_sort(run: Run) -> tuple[object, ...]:
    index = TIERS.index(run.tier) if run.tier is not None else len(TIERS)
    return (
        run.assisted,
        index,
        run.agent,
        run.model,
        run.seed is None,
        0 if run.seed is None else run.seed,
        run.name,
    )


def run_order(run: Run) -> tuple[bool, int, str]:
    return (run.seed is None, 0 if run.seed is None else run.seed, run.name)


def benchmark_sections(runs: Sequence[Run]) -> tuple[tuple[Tier, tuple[ScoreRow, ...]], ...]:
    groups: dict[tuple[str, str, str, bool], list[Run]] = {}
    for run in runs:
        if run.assisted or run.tier is None or run.score is None:
            continue
        key = (run.agent, run.model, run.tier.goal, run.from_save)
        groups.setdefault(key, []).append(run)
    by_goal: dict[str, list[ScoreRow]] = {}
    for (agent, model, goal, from_save), members in groups.items():
        members.sort(key=run_order)
        row = ScoreRow(BY_GOAL[goal], agent, model, from_save, tuple(members))
        by_goal.setdefault(goal, []).append(row)
    sections: list[tuple[Tier, tuple[ScoreRow, ...]]] = []
    for tier in TIERS:
        rows = by_goal.get(tier.goal)
        if not rows:
            continue
        rows.sort(key=lambda row: (-row.median_score(), row.agent, row.model, row.from_save))
        sections.append((tier, tuple(rows)))
    return tuple(sections)


def assisted_sections(runs: Sequence[Run]) -> tuple[tuple[Tier, tuple[TimeRow, ...]], ...]:
    groups: dict[tuple[str, str, str, bool, tuple[str, ...]], list[Run]] = {}
    for run in runs:
        if not run.assisted or run.tier is None or run.ratio is None or run.game_ticks is None:
            continue
        key = (run.agent, run.model, run.tier.goal, run.from_save, run.skills)
        groups.setdefault(key, []).append(run)
    by_goal: dict[str, list[TimeRow]] = {}
    for (agent, model, goal, from_save, skills), members in groups.items():
        members.sort(key=run_order)
        row = TimeRow(BY_GOAL[goal], agent, model, from_save, skills, tuple(members))
        by_goal.setdefault(goal, []).append(row)
    sections: list[tuple[Tier, tuple[TimeRow, ...]]] = []
    for tier in TIERS:
        rows = by_goal.get(tier.goal)
        if not rows:
            continue
        rows.sort(key=lambda row: (row.median_ticks(), row.agent, row.model, row.from_save))
        sections.append((tier, tuple(rows)))
    return tuple(sections)


def headline_rows(sections: Sequence[tuple[Tier, tuple[ScoreRow, ...]]]) -> tuple[Headline, ...]:
    grouped: dict[tuple[str, str, bool], dict[str, ScoreRow]] = {}
    for _tier, rows in sections:
        for row in rows:
            key = (row.agent, row.model, row.from_save)
            grouped.setdefault(key, {})[row.tier.goal] = row
    found: list[Headline] = []
    for (agent, model, from_save), by_goal in grouped.items():
        if any(tier.goal not in by_goal for tier in TIERS):
            continue
        parts = tuple((tier.short, by_goal[tier.goal].median_score()) for tier in TIERS)
        found.append(
            Headline(
                agent=agent,
                model=model,
                from_save=from_save,
                score=float(statistics.geometric_mean([score for _, score in parts])),
                tiers=parts,
            )
        )
    found.sort(key=lambda item: (-item.score, item.agent, item.model, item.from_save))
    return tuple(found)


def duplicate_notes(runs: Sequence[Run]) -> list[str]:
    seen: dict[tuple[object, ...], str] = {}
    notes: list[str] = []
    for run in runs:
        if run.tier is None or run.seed is None:
            continue
        key: tuple[object, ...] = (
            run.assisted,
            run.agent,
            run.model,
            run.tier.goal,
            run.from_save,
            run.skills,
            run.seed,
            run.epoch,
        )
        if key not in seen:
            seen[key] = run.name
            continue
        label = pair_label(run.agent, run.model, from_save=run.from_save, skills=run.skills)
        notes.append(
            f"{label} has two {run.tier.label} runs on seed {run.seed} "
            f"({seen[key]} and {run.name}); both are included"
        )
    return notes


# Rendering ----------------------------------------------------------------


def intro() -> str:
    floor = f"{UNREACHED_SCORE:.2f}"
    return (
        "Score is reference time divided by game time (decision 23). "
        "1.00 matches an average player (decision 21), and above 1.00 is faster. "
        "A fresh map uses the cumulative hours for that tier. "
        "A run from a save uses that tier's gap (decision 22). "
        f"A benchmark run that times out with no milestone scores {floor}. "
        "A run stopped early stays out of the median. "
        "Each row is one harness and one model, and the number is the median "
        "over its runs (decision 20). "
        "A run that installed a skill is under Assisted and is not a score "
        "(decisions 48 and 77)."
    )


def headline_intro() -> str:
    return (
        "The headline is the geometric mean of the six tier medians (decision 23). "
        "It is shown when the pair has a scored benchmark run on every tier. "
        "Decision 22 scores purple and yellow as one ladder stage of 17 h. "
        "The mean uses each tier's own ratio, because a run file records the goal "
        "it stopped on."
    )


def render_markdown(report: Report) -> str:
    parts = ["# factobot leaderboard", "", filled(intro()), ""]
    if report.headlines:
        parts.extend(headline_markdown(report))
    parts.extend(benchmark_markdown(report))
    parts.extend(assisted_markdown(report))
    parts.extend(runs_markdown(report))
    if report.warnings:
        parts.extend(["## Notes", ""])
        parts.extend(f"- {clean(note)}" for note in report.warnings)
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def render_html(report: Report) -> str:
    body = ["<h1>factobot leaderboard</h1>", f"<p>{escape(intro())}</p>"]
    if report.headlines:
        body.extend(headline_html(report))
    body.extend(benchmark_html(report))
    body.extend(assisted_html(report))
    body.extend(runs_html(report))
    if report.warnings:
        items = "".join(f"<li>{escape(clean(note))}</li>" for note in report.warnings)
        body.append(f"<h2>Notes</h2><ul>{items}</ul>")
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        "<title>factobot leaderboard</title>\n"
        f"<style>\n{CSS}\n</style>\n"
        "</head>\n"
        "<body>\n" + "\n".join(body) + "\n</body>\n</html>\n"
    )


def headline_markdown(report: Report) -> list[str]:
    headers = ["Harness", "Model", "Map", *[tier.short for tier in TIERS], "Headline"]
    rows = [headline_cells(item) for item in report.headlines]
    lines = ["## Headline", "", filled(headline_intro()), "", md_table(headers, rows), ""]
    scale = max(1.0, *(item.score for item in report.headlines))
    chart = [(item.label(), item.score, f"{item.score:.2f}") for item in report.headlines]
    lines.extend(text_chart(chart, scale=scale, note=SCORE_NOTE))
    lines.append("")
    return lines


def benchmark_markdown(report: Report) -> list[str]:
    lines = [
        "## Benchmark",
        "",
        filled(
            "SE is the standard error of the mean. It is blank when a row has one run. "
            "Game time is the milestone minus the start, or the end of the run when "
            "it timed out first. Cost is the sum of the runs that reported one."
        ),
        "",
    ]
    if not report.benchmark:
        lines.extend(["No benchmark runs.", ""])
        return lines
    for tier, rows in report.benchmark:
        lines.extend(benchmark_tier_markdown(report, tier, rows))
    return lines


def benchmark_tier_markdown(report: Report, tier: Tier, rows: Sequence[ScoreRow]) -> list[str]:
    lines = [f"### {tier.label}", ""]
    lines.append(filled(reference_sentence(tier, {row.from_save for row in rows})))
    lines.append("")
    note = yellow_note(rows)
    if note is not None:
        lines.extend([filled(note), ""])
    lines.extend(
        [
            md_table(BENCHMARK_HEADERS, [benchmark_cells(row) for row in rows]),
            "",
        ]
    )
    left = leftover_line(report.runs, tier, assisted=False)
    if left is not None:
        lines.extend([left, ""])
    scale = max(1.0, *(row.median_score() for row in rows))
    chart = [(row.label(), row.median_score(), f"{row.median_score():.2f}") for row in rows]
    lines.extend(text_chart(chart, scale=scale, note=SCORE_NOTE))
    lines.append("")
    return lines


def assisted_markdown(report: Report) -> list[str]:
    lines = [
        "## Assisted",
        "",
        filled(
            "These runs installed a skill. The ratio is reference time over game "
            "time, for comparison. It is not a benchmark score."
        ),
        "",
    ]
    assisted = [run for run in report.runs if run.assisted]
    if not assisted:
        lines.extend(["No assisted runs.", ""])
        return lines
    if not report.assisted:
        lines.extend(["No assisted run reached its milestone.", ""])
    for tier, rows in report.assisted:
        lines.extend(assisted_tier_markdown(report, tier, rows))
    missed = missed_assisted(report)
    if missed is not None:
        lines.extend([filled(missed), ""])
    return lines


def assisted_tier_markdown(report: Report, tier: Tier, rows: Sequence[TimeRow]) -> list[str]:
    lines = [f"### {tier.label}", ""]
    lines.append(filled(reference_sentence(tier, {row.from_save for row in rows})))
    lines.append("")
    lines.extend([md_table(ASSISTED_HEADERS, [assisted_cells(row) for row in rows]), ""])
    left = leftover_line(report.runs, tier, assisted=True)
    if left is not None:
        lines.extend([left, ""])
    scale = max(row.median_ticks() / TICKS_PER_HOUR for row in rows)
    chart = [
        (row.label(), row.median_ticks() / TICKS_PER_HOUR, fmt_ticks(row.median_ticks()))
        for row in rows
    ]
    lines.extend(text_chart(chart, scale=scale, note=HOURS_NOTE))
    lines.append("")
    return lines


def runs_markdown(report: Report) -> list[str]:
    lines = ["## All runs", ""]
    if not report.runs:
        lines.extend(["No runs.", ""])
        return lines
    lines.extend([md_table(RUN_HEADERS, [run_cells(run) for run in report.runs]), ""])
    return lines


def headline_html(report: Report) -> list[str]:
    headers = ["Harness", "Model", "Map", *[tier.short for tier in TIERS], "Headline"]
    rows = [headline_cells(item) for item in report.headlines]
    points = [
        (item.label(), item.score, [item.score], f"{item.score:.2f}") for item in report.headlines
    ]
    return [
        "<h2>Headline</h2>",
        f"<p>{escape(headline_intro())}</p>",
        html_table(headers, rows),
        f'<p class="caption">{escape(SCORE_CAPTION)}</p>',
        svg_bars(
            "Headline",
            points,
            reference=1.0,
            reference_label="average player",
            format_axis=lambda number: f"{number:.2f}",
        ),
    ]


def benchmark_html(report: Report) -> list[str]:
    lines = [
        "<h2>Benchmark</h2>",
        "<p>SE is the standard error of the mean. It is blank when a row has one run. "
        "Game time is the milestone minus the start, or the end of the run when it "
        "timed out first. Cost is the sum of the runs that reported one.</p>",
    ]
    if not report.benchmark:
        lines.append("<p>No benchmark runs.</p>")
        return lines
    for tier, rows in report.benchmark:
        lines.append(f"<h3>{escape(tier.label)}</h3>")
        lines.append(f"<p>{escape(reference_sentence(tier, {row.from_save for row in rows}))}</p>")
        note = yellow_note(rows)
        if note is not None:
            lines.append(f"<p>{escape(note)}</p>")
        lines.append(html_table(BENCHMARK_HEADERS, [benchmark_cells(row) for row in rows]))
        left = leftover_line(report.runs, tier, assisted=False)
        if left is not None:
            lines.append(f'<p class="note">{escape(left)}</p>')
        lines.append(f'<p class="caption">{escape(SCORE_CAPTION)}</p>')
        lines.append(score_svg(tier, rows))
        hours = score_hours_svg(tier, rows)
        if hours is not None:
            if hours_reference(tier, rows) is not None:
                caption = HOURS_CAPTION_REF
            else:
                caption = HOURS_CAPTION
            lines.append(f'<p class="caption">{escape(caption)}</p>')
            lines.append(hours)
    return lines


def assisted_html(report: Report) -> list[str]:
    lines = [
        "<h2>Assisted</h2>",
        "<p>These runs installed a skill. The ratio is reference time over game "
        "time, for comparison. It is not a benchmark score.</p>",
    ]
    assisted = [run for run in report.runs if run.assisted]
    if not assisted:
        lines.append("<p>No assisted runs.</p>")
        return lines
    if not report.assisted:
        lines.append("<p>No assisted run reached its milestone.</p>")
    for tier, rows in report.assisted:
        lines.append(f"<h3>{escape(tier.label)}</h3>")
        lines.append(f"<p>{escape(reference_sentence(tier, {row.from_save for row in rows}))}</p>")
        lines.append(html_table(ASSISTED_HEADERS, [assisted_cells(row) for row in rows]))
        left = leftover_line(report.runs, tier, assisted=True)
        if left is not None:
            lines.append(f'<p class="note">{escape(left)}</p>')
        saves = {row.from_save for row in rows}
        caption = HOURS_CAPTION_REF if len(saves) == 1 else HOURS_CAPTION
        lines.append(f'<p class="caption">{escape(caption)}</p>')
        lines.append(assisted_hours_svg(tier, rows))
    missed = missed_assisted(report)
    if missed is not None:
        lines.append(f'<p class="note">{escape(missed)}</p>')
    return lines


def runs_html(report: Report) -> list[str]:
    lines = ["<h2>All runs</h2>"]
    if not report.runs:
        lines.append("<p>No runs.</p>")
        return lines
    lines.append(html_table(RUN_HEADERS, [run_cells(run) for run in report.runs]))
    return lines


BENCHMARK_HEADERS = [
    "Harness",
    "Model",
    "Map",
    "Runs",
    "Median",
    "SE",
    "Game time",
    "Wall",
    "Cost",
]
ASSISTED_HEADERS = [
    "Harness",
    "Model",
    "Skills",
    "Map",
    "Runs",
    "Game time",
    "Ratio",
    "Wall",
    "Cost",
]
RUN_HEADERS = [
    "Run",
    "Kind",
    "Harness",
    "Model",
    "Seed",
    "Tier",
    "Map",
    "Game time",
    "Score",
    "Wall",
    "Cost",
    "Turns",
    "Status",
]


def headline_cells(item: Headline) -> list[str]:
    scores = dict(item.tiers)
    return [
        item.agent,
        item.model,
        "save" if item.from_save else "fresh",
        *[f"{scores[tier.short]:.2f}" for tier in TIERS],
        f"{item.score:.2f}",
    ]


def benchmark_cells(row: ScoreRow) -> list[str]:
    err = row.stderr()
    ticks = row.median_ticks()
    wall = row.median_wall()
    cost = row.cost_sum()
    return [
        row.agent,
        row.model,
        map_label(row.tier, row.from_save),
        str(len(row.runs)),
        f"{row.median_score():.2f}",
        "" if err is None else f"{err:.2f}",
        "" if ticks is None else fmt_ticks(ticks),
        "" if wall is None else fmt_wall(wall),
        "" if cost is None else fmt_cost(cost),
    ]


def assisted_cells(row: TimeRow) -> list[str]:
    wall = row.median_wall()
    cost = row.cost_sum()
    return [
        row.agent,
        row.model,
        ", ".join(row.skills),
        map_label(row.tier, row.from_save),
        str(len(row.runs)),
        fmt_ticks(row.median_ticks()),
        f"{row.median_ratio():.2f}",
        "" if wall is None else fmt_wall(wall),
        "" if cost is None else fmt_cost(cost),
    ]


def run_cells(run: Run) -> list[str]:
    if run.tier is None:
        tier = run.goal or ""
        mapped = "save" if run.from_save else ""
    else:
        tier = run.tier.label
        mapped = map_label(run.tier, run.from_save)
    return [
        run.name,
        "assisted" if run.assisted else "benchmark",
        run.agent,
        run.model,
        seed_cell(run),
        tier,
        mapped,
        "" if run.game_ticks is None else fmt_ticks(run.game_ticks),
        "" if run.score is None else f"{run.score:.2f}",
        "" if run.wall_seconds is None else fmt_wall(run.wall_seconds),
        "" if run.cost_usd is None else fmt_cost(run.cost_usd),
        "" if run.turns is None else str(run.turns),
        run.status,
    ]


def seed_cell(run: Run) -> str:
    if run.seed is None:
        return ""
    if run.epoch not in (None, 1):
        return f"{run.seed} epoch {run.epoch}"
    return str(run.seed)


def map_label(tier: Tier, from_save: bool) -> str:
    kind = "save" if from_save else "fresh"
    return f"{kind}, {fmt_hours(tier.reference_hours(from_save))}"


def reference_sentence(tier: Tier, from_saves: set[bool]) -> str:
    parts: list[str] = []
    if False in from_saves:
        parts.append(f"A fresh map is scored against {fmt_hours(tier.cumulative_hours)}.")
    if True in from_saves:
        parts.append(f"A run from a save is scored against the {fmt_hours(tier.gap_hours)} gap.")
    return " ".join(parts)


def yellow_note(rows: Sequence[ScoreRow]) -> str | None:
    if any(row.tier.goal == "utility-science-pack" and row.from_save for row in rows):
        return (
            "Yellow's 2 h gap is the split decision 22 rolls into one 17 h purple and "
            "yellow stage. This row stopped at yellow alone."
        )
    return None


def leftover_line(runs: Sequence[Run], tier: Tier, *, assisted: bool) -> str | None:
    if assisted:
        skipped = [run for run in runs if run.tier == tier and run.assisted and run.ratio is None]
    else:
        skipped = [
            run for run in runs if run.tier == tier and not run.assisted and run.score is None
        ]
    if not skipped:
        return None
    counts: dict[str, int] = {}
    for run in skipped:
        counts[run.status] = counts.get(run.status, 0) + 1
    parts = [f"{count} {status}" for status, count in sorted(counts.items())]
    return "Left out: " + ", ".join(parts) + "."


def missed_assisted(report: Report) -> str | None:
    missed = [run for run in report.runs if run.assisted and run.ratio is None]
    if not missed:
        return None
    counts: dict[str, int] = {}
    for run in missed:
        tier = run.tier.label if run.tier is not None else "no goal"
        label = f"{run.agent} / {run.model} on {tier}"
        counts[label] = counts.get(label, 0) + 1
    parts = [f"{label} ({count})" for label, count in sorted(counts.items())]
    return "Not reached, so not in the table: " + ", ".join(parts) + "."


def score_svg(tier: Tier, rows: Sequence[ScoreRow]) -> str:
    points = [
        (row.label(), row.median_score(), list(row.scores()), f"{row.median_score():.2f}")
        for row in rows
    ]
    return svg_bars(
        f"{tier.label} scores",
        points,
        reference=1.0,
        reference_label="average player",
        format_axis=lambda number: f"{number:.2f}",
    )


def hours_reference(tier: Tier, rows: Sequence[ScoreRow]) -> float | None:
    saves = {row.from_save for row in rows}
    if len(saves) != 1:
        return None
    return tier.reference_hours(next(iter(saves)))


def score_hours_svg(tier: Tier, rows: Sequence[ScoreRow]) -> str | None:
    points: list[tuple[str, float, Sequence[float], str]] = []
    for row in rows:
        ticks = row.median_ticks()
        if ticks is None:
            return None
        dots = [run.game_ticks / TICKS_PER_HOUR for run in row.runs if run.game_ticks is not None]
        points.append((row.label(), ticks / TICKS_PER_HOUR, dots, fmt_ticks(ticks)))
    return svg_bars(
        f"{tier.label} game time",
        points,
        reference=hours_reference(tier, rows),
        reference_label="reference",
        format_axis=lambda number: f"{number:.1f} h",
    )


def assisted_hours_svg(tier: Tier, rows: Sequence[TimeRow]) -> str:
    saves = {row.from_save for row in rows}
    reference = tier.reference_hours(next(iter(saves))) if len(saves) == 1 else None
    points: list[tuple[str, float, Sequence[float], str]] = []
    for row in rows:
        ticks = row.median_ticks()
        dots = [run.game_ticks / TICKS_PER_HOUR for run in row.runs if run.game_ticks is not None]
        points.append((row.label(), ticks / TICKS_PER_HOUR, dots, fmt_ticks(ticks)))
    return svg_bars(
        f"{tier.label} assisted game time",
        points,
        reference=reference,
        reference_label="reference",
        format_axis=lambda number: f"{number:.1f} h",
    )


def text_chart(rows: Sequence[tuple[str, float, str]], *, scale: float, note: str) -> list[str]:
    labels = [clean(label) for label, _, _ in rows]
    width = max((len(label) for label in labels), default=0)
    lines = [filled(note), "", "```"]
    for label, (_, value, caption) in zip(labels, rows, strict=True):
        amount = 0.0 if scale <= 0 else min(value, scale) / scale
        cells = round(BAR_WIDTH * amount)
        bar = "#" * cells + "-" * (BAR_WIDTH - cells)
        lines.append(f"{label.ljust(width)}  {bar}  {caption}")
    lines.append("```")
    return lines


def svg_bars(
    title: str,
    rows: Sequence[tuple[str, float, Sequence[float], str]],
    *,
    reference: float | None,
    reference_label: str,
    format_axis: Callable[[float], str],
) -> str:
    """Horizontal bars. `rows` are (label, bar value, dot values, caption)."""
    if not rows:
        return ""
    width = 760
    left = 250
    right = 88
    top = 28
    row_h = 34
    bar_h = 14
    height = top + row_h * len(rows) + 22
    plot_right = width - right
    plot_w = plot_right - left
    peak = max(value for _, value, _, _ in rows)
    peak = max(peak, *(dot for _, _, dots, _ in rows for dot in dots))
    if reference is not None and reference > 0:
        peak = max(peak, reference)
    axis = max(peak * 1.08, 0.01)

    def x_of(value: float) -> float:
        return left + plot_w * max(value, 0.0) / axis

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="{escape(title)}" class="chart">',
        f"<title>{escape(title)}</title>",
        f'<rect width="{width}" height="{height}" class="panel"/>',
    ]
    axis_y = height - 18
    lines.append(f'<line x1="{left}" y1="{axis_y}" x2="{plot_right}" y2="{axis_y}" class="axis"/>')
    lines.append(f'<text x="{left}" y="{height - 4}" class="num">0</text>')
    lines.append(
        f'<text x="{plot_right}" y="{height - 4}" text-anchor="end" class="num">'
        f"{escape(format_axis(axis))}</text>"
    )
    if reference is not None and reference > 0:
        ref_x = x_of(reference)
        lines.append(
            f'<line x1="{ref_x:.1f}" y1="18" x2="{ref_x:.1f}" y2="{axis_y}" class="reference"/>'
        )
        anchor = "end" if ref_x > width - 150 else "start"
        ref_text_x = ref_x - 4 if anchor == "end" else ref_x + 4
        lines.append(
            f'<text x="{ref_text_x:.1f}" y="14" text-anchor="{anchor}" class="ref">'
            f"{escape(reference_label)}</text>"
        )
    for index, (label, value, dots, caption) in enumerate(rows):
        center = top + index * row_h + row_h / 2
        bar_y = center - bar_h / 2
        bar_w = max(x_of(value) - left, 0.0)
        shown = clip(label, 32)
        lines.append(
            f'<rect x="{left:.1f}" y="{bar_y:.1f}" width="{bar_w:.1f}" '
            f'height="{bar_h}" class="bar"><title>{escape(label)}</title></rect>'
        )
        lines.append(
            f'<text x="{left - 10:.1f}" y="{center + 4:.1f}" text-anchor="end" class="label">'
            f"{escape(shown)}</text>"
        )
        for dot in dots:
            lines.append(f'<circle cx="{x_of(dot):.1f}" cy="{center:.1f}" r="3.5" class="dot"/>')
        lines.append(
            f'<text x="{plot_right + 8:.1f}" y="{center + 4:.1f}" class="num">'
            f"{escape(caption)}</text>"
        )
    lines.append("</svg>")
    return "\n".join(lines)


def md_table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    def cell(value: str) -> str:
        return clean(value).replace("|", "\\|")

    head = "| " + " | ".join(cell(header) for header in headers) + " |"
    rule = "| " + " | ".join("---" for _ in headers) + " |"
    body = ["| " + " | ".join(cell(value) for value in row) + " |" for row in rows]
    return "\n".join([head, rule, *body])


def html_table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    head = "".join(f"<th>{escape(clean(header))}</th>" for header in headers)
    body = []
    for row in rows:
        cells = "".join(f"<td>{escape(clean(value))}</td>" for value in row)
        body.append(f"<tr>{cells}</tr>")
    return "<table><thead><tr>" + head + "</tr></thead><tbody>" + "".join(body) + "</tbody></table>"


def filled(text: str) -> str:
    return textwrap.fill(text, width=WRAP)


def clean(value: str) -> str:
    return " ".join(value.replace("```", "'''").split())


def clip(text: str, limit: int) -> str:
    text = clean(text)
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def fmt_hours(hours: float) -> str:
    if hours == int(hours):
        return f"{int(hours)} h"
    return f"{hours:g} h"


def fmt_ticks(ticks: float) -> str:
    total = max(0, round(ticks / TICKS_PER_SECOND))
    hours, rem = divmod(total, 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}"


def fmt_wall(seconds: float) -> str:
    return fmt_ticks(seconds * TICKS_PER_SECOND)


def fmt_cost(cost: float) -> str:
    return f"${cost:.2f}"


CSS = "\n".join(
    [
        ":root { color-scheme: light; }",
        "body {",
        "  margin: 0 auto;",
        "  max-width: 62rem;",
        "  padding: 2.5rem 1.25rem 4rem;",
        "  font: 16px/1.5 system-ui, sans-serif;",
        "  color: #1c2430;",
        "  background: #f4f1ea;",
        "}",
        "h1 { font-size: 1.8rem; font-weight: 650; margin: 0 0 0.6rem; }",
        "h2 { margin: 2.2rem 0 0.6rem; font-size: 1.25rem; font-weight: 650; }",
        "h3 { margin: 1.4rem 0 0.3rem; font-size: 1.05rem; font-weight: 650; }",
        "p { margin: 0.4rem 0 0.8rem; }",
        ".note, .caption { color: #5c6b7a; }",
        ".caption { font-size: 0.92rem; }",
        "table {",
        "  width: 100%;",
        "  border-collapse: collapse;",
        "  background: #fff;",
        "  margin: 0.4rem 0 0.8rem;",
        "}",
        "th, td {",
        "  text-align: left;",
        "  padding: 0.35rem 0.55rem;",
        "  border-bottom: 1px solid #e1e6ec;",
        "  font-variant-numeric: tabular-nums;",
        "  vertical-align: top;",
        "}",
        "th {",
        "  font-size: 0.72rem;",
        "  letter-spacing: 0.04em;",
        "  text-transform: uppercase;",
        "  color: #5c6b7a;",
        "}",
        "svg.chart {",
        "  width: 100%;",
        "  height: auto;",
        "  display: block;",
        "  margin: 0.2rem 0 1.2rem;",
        "}",
        "svg .panel { fill: #fff; }",
        "svg text { font-family: system-ui, sans-serif; fill: #1c2430; }",
        "svg .label { font-size: 13px; }",
        "svg .num { font-size: 12px; }",
        "svg .ref { fill: #8a5a12; font-size: 12px; }",
        "svg .bar { fill: #2f5d7c; }",
        "svg .dot { fill: #14202b; }",
        "svg .reference {",
        "  stroke: #8a5a12;",
        "  stroke-width: 1.5;",
        "  stroke-dasharray: 4 3;",
        "}",
        "svg .axis { stroke: #d5dde6; stroke-width: 1; }",
    ]
)


# Command ------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m factobot.report",
        description=(
            "Turn playtest summary.json files and Inspect eval logs into a markdown "
            "and HTML leaderboard with per-model scores and charts."
        ),
        epilog=(
            "Examples:\n"
            "  python -m factobot.report target/playtests -o target/reports\n"
            "  python -m factobot.report run/summary.json -o target/reports\n"
            "  python -m factobot.report logs/\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="run directories, summary.json files, or Inspect .eval logs "
        "[default: target/playtests]",
    )
    parser.add_argument(
        "-o",
        "--out",
        type=Path,
        default=Path("target/reports"),
        help="directory for leaderboard.md and leaderboard.html [default: target/reports]",
    )
    args = parser.parse_args(argv)
    paths: list[Path] = args.paths or [Path("target/playtests")]
    runs, warnings = collect(paths)
    report = build(runs, warnings)
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    markdown = out / "leaderboard.md"
    html = out / "leaderboard.html"
    markdown.write_text(render_markdown(report))
    html.write_text(render_html(report))
    print(
        json.dumps(
            {
                "ok": bool(report.runs),
                "runs": len(report.runs),
                "scored": sum(run.score is not None for run in report.runs),
                "assisted": sum(run.assisted for run in report.runs),
                "markdown": str(markdown),
                "html": str(html),
                "warnings": list(report.warnings),
            },
            indent=2,
        )
    )
    return 0 if report.runs else 1


if __name__ == "__main__":
    sys.exit(main())
