"""Inspect AI tasks: the staged ladder (decisions 16 to 23).

Each sample boots a fresh world on its own seed, gives the model one tool,
`fac`, and lets it play in real time until the harness sees the stage's
milestone (decision 43), the game-time cap passes, or Inspect's own limits
stop it. The score comes from the game, never from the agent.

    inspect eval factobot/red_science --model <provider>/<model>
"""

from __future__ import annotations

import os
import shlex
import statistics
import subprocess
import threading
import time
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

import anyio
from inspect_ai import Task, task
from inspect_ai.agent import AgentPrompt, AgentState, as_solver, react
from inspect_ai.dataset import Sample
from inspect_ai.hooks import Hooks, ModelRetry, ModelUsageData, hooks
from inspect_ai.model import CompactionSummary
from inspect_ai.scorer import (
    Metric,
    SampleScore,
    Score,
    Scorer,
    Target,
    metric,
    scorer,
    stderr,
)
from inspect_ai.solver import Generate, Solver, TaskState, solver
from inspect_ai.tool import Tool, tool

from factobot.harness import World, find_fac, start_world

TICKS_PER_SECOND = 60
TICKS_PER_MINUTE = 60 * TICKS_PER_SECOND
TICKS_PER_HOUR = 60 * TICKS_PER_MINUTE
SUSTAIN_MINUTES = 10  # decision 18
CAP_FACTOR = 2  # decision 20: the cap is twice the reference gap
SEEDS = (1, 2, 3, 4, 5)  # decision 20: five seeds per stage
FAC_TIMEOUT = 660.0  # `fac job --wait` waits at most 600 s
# Harness-only commands. Only the Inspect tool path checks these; playtests give
# agents fac-agent instead (decision 64).
FORBIDDEN = ("dev", "daemon", "watch")


@dataclass(frozen=True)
class Stage:
    """One rung of the ladder (decision 22)."""

    name: str
    pack: str
    reference_hours: float  # decision 21's average player, provisional
    goal: str

    @property
    def reference_ticks(self) -> int:
        return round(self.reference_hours * TICKS_PER_HOUR)

    @property
    def cap_ticks(self) -> int:
        return CAP_FACTOR * self.reference_ticks


RED_SCIENCE = Stage(
    name="red_science",
    pack="automation-science-pack",
    reference_hours=5,
    goal=(
        "Starting from nothing, get labs researching with automation science "
        "packs (red science) made by an assembling machine."
    ),
)


def instructions() -> str:
    return (
        "You are playing Factorio through the `fac` command line, and only through it. "
        "Call the `fac` tool with a command such as `fac --help`, `fac observe` or "
        "`fac walk 10,4 --wait`. You are scored on game time, and the game runs in "
        "real time: it keeps going while you think. There is nothing to submit: keep "
        "playing until the run ends."
    )


def goal(stage: Stage, throughput: float | None = None) -> str:
    text = (
        f"{stage.goal} Packs you craft by hand don't count: the clock stops once labs "
        f"have used more {stage.pack} than you have ever crafted by hand. You cannot see "
        "that total. A lab that is `working` may still be using packs you crafted by hand, "
        "so keep the assemblers feeding the labs."
    )
    if throughput is not None:
        text += (
            f" After that, machines must make at least {throughput:g} of those packs a "
            f"minute, on average over {SUSTAIN_MINUTES} game minutes, for the stage to count."
        )
    return text


# Worlds -------------------------------------------------------------------


class _WorldThread:
    """A world opened, and later closed, by a thread of its own.

    The harness stops a world when the thread that called `start_world` ends
    (PR_SET_PDEATHSIG follows that thread). Inspect runs samples as async
    tasks on the event loop and hands blocking calls to anyio's short-lived
    `to_thread` workers, so each world gets a dedicated thread that lives
    exactly as long as it."""

    def __init__(self, **options: Any) -> None:
        self._options = options
        self._ready = threading.Event()
        self._done = threading.Event()
        self._world: World | None = None
        self._error: BaseException | None = None
        self._thread = threading.Thread(target=self._run, name="factobot-world", daemon=True)

    def _run(self) -> None:
        try:
            with start_world(**self._options) as world:
                self._world = world
                self._ready.set()
                self._done.wait()
        except BaseException as error:
            self._error = error
            self._ready.set()

    async def open(self) -> World:
        self._thread.start()
        try:
            await anyio.to_thread.run_sync(self._ready.wait)
        except BaseException:
            await self.close()
            raise
        if self._world is None:
            raise RuntimeError("the world did not start") from self._error
        return self._world

    async def close(self) -> None:
        """Stop the world and wait for it, even when the sample was cancelled."""
        self._done.set()
        with anyio.CancelScope(shield=True):
            await anyio.to_thread.run_sync(self._thread.join)


@asynccontextmanager
async def running_world(**options: Any) -> AsyncIterator[World]:
    holder = _WorldThread(**options)
    world = await holder.open()
    try:
        yield world
    finally:
        await holder.close()


# Outages ------------------------------------------------------------------


class Outage:
    """Pauses a sample's world while its model call is being retried
    (decision 19), and keeps the total.

    Inspect retries a failed call itself and tells hooks before each retry.
    The world resumes when the retried call succeeds, which Inspect also
    tells hooks, or else when the harness next runs (the agent's tool or the
    turn's end). The call that ends an outage runs paused; every other call,
    however slow, runs in game time: that is the model's speed. Provider SDKs
    retry some failures inside one call where no hook sees them, so benchmark
    runs turn those off (`-M max_retries=0` for Anthropic and OpenAI,
    `-M disable_retry=true` for xAI; Google's client has no such switch)."""

    def __init__(self, world: World) -> None:
        self._world = world
        self._since: float | None = None
        self.seconds = 0.0
        self.count = 0

    async def begin(self) -> None:
        if self._since is None:
            await anyio.to_thread.run_sync(self._world.pause)
            self._since = time.monotonic()
            self.count += 1

    async def end(self) -> None:
        # Taken before the await, so parallel tool calls resume only once.
        since, self._since = self._since, None
        if since is None:
            return
        try:
            await anyio.to_thread.run_sync(self._world.lua, "game.tick_paused = false")
        except BaseException:
            # Still paused: the harness's next end() tries again, and the
            # seconds until then count as paused.
            self._since = since
            raise
        self.seconds += time.monotonic() - since

    def total(self) -> float:
        """Paused seconds so far, including an outage still going on."""
        ongoing = time.monotonic() - self._since if self._since is not None else 0.0
        return self.seconds + ongoing


# The outage of the sample running in this context, if it plays a world.
_outage: ContextVar[Outage | None] = ContextVar("factobot_outage", default=None)


@hooks(
    name="factobot_outages",
    description="Pause a factobot world while its model call is retried (decision 19).",
)
class PauseDuringOutages(Hooks):
    async def on_model_retry(self, data: ModelRetry) -> None:
        outage = _outage.get()
        if outage is not None:
            await outage.begin()

    async def on_model_usage(self, data: ModelUsageData) -> None:
        outage = _outage.get()
        if outage is not None:
            await outage.end()


# The agent's tool -----------------------------------------------------------


def fac_argv(command: str) -> list[str]:
    """The arguments of one `fac` command line, refusing harness-only ones and
    other sockets (another world's, or the dev socket)."""
    args = shlex.split(command)
    if args and args[0] == "fac":
        args = args[1:]
    for arg in args:
        name = arg.split("=", 1)[0]
        if arg in FORBIDDEN or name in ("--socket", "--dev-socket"):
            raise ValueError(f"`fac {name}` is not available to agents")
    return args


def fac_tool(world: World, outage: Outage) -> Tool:
    socket = os.fspath(world.agent_socket)
    binary = os.fspath(find_fac())

    @tool(name="fac")
    def fac() -> Tool:
        async def execute(command: str) -> str:
            """Run one `fac` command and return what it prints (one JSON object).

            Args:
                command: The command line, for example `fac observe`,
                    `fac walk 10,4 --wait` or `fac craft iron-gear-wheel --count 5`.
                    `fac --help` and `fac <command> --help` explain every command.
            """
            await outage.end()
            try:
                args = fac_argv(command)
            except ValueError as refused:
                return str(refused)
            env = {"PATH": "/usr/bin:/bin", "FACTOBOT_SOCKET": socket}
            with anyio.fail_after(FAC_TIMEOUT):
                done = await anyio.run_process(
                    [binary, *args], env=env, check=False, stderr=subprocess.STDOUT
                )
            return done.stdout.decode(errors="replace").strip()

        return execute

    return fac()


# Playing ------------------------------------------------------------------


def stage_report(world: World, stage: Stage, start_tick: int) -> dict[str, Any]:
    """What the harness has seen of the stage so far."""
    packs = world.milestones()["packs"]
    pack = next(p for p in packs if p["name"] == stage.pack)
    return {
        "start_tick": start_tick,
        "tick": world.tick(),
        "milestone_tick": pack.get("first_automated_research"),
        "machine_made_by_minute": pack["machine_made_by_minute"],
    }


def sustained_at(report: dict[str, Any], throughput: float) -> int | None:
    """The tick by which machines had made `throughput` packs a minute, on
    average over SUSTAIN_MINUTES whole game minutes counted from the milestone
    on (decision 18), or None."""
    milestone = report["milestone_tick"]
    if milestone is None:
        return None
    made = [0, *report["machine_made_by_minute"]]  # made[k]: by the end of minute k
    first = -(-milestone // TICKS_PER_MINUTE)  # first minute boundary at or after it
    for start in range(first, len(made) - SUSTAIN_MINUTES):
        end = start + SUSTAIN_MINUTES
        if made[end] - made[start] >= throughput * SUSTAIN_MINUTES:
            return end * TICKS_PER_MINUTE
    return None


def finished(report: dict[str, Any], throughput: float | None) -> bool:
    if report["milestone_tick"] is None:
        return False
    return throughput is None or sustained_at(report, throughput) is not None


@solver
def play(
    stage: Stage,
    throughput: float | None = None,
    cap_ticks: int | None = None,
    setup: str | None = None,
    speed: float | None = None,
) -> Solver:
    """Boot the sample's world and run the agent in it until the stage ends.

    `setup` (Lua) and `speed` are for tests only."""
    cap = cap_ticks if cap_ticks is not None else stage.cap_ticks

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        seed = int(state.metadata["seed"])
        async with running_world(seed=seed, setup=setup, speed=speed) as world:
            # Calls to the world go through a thread, so one sample's game
            # never holds up another's agent.
            async def report() -> dict[str, Any]:
                return await anyio.to_thread.run_sync(stage_report, world, stage, start_tick)

            # The world runs while it boots. Pause it while the agent is set
            # up; the clock starts here and the world runs again just before
            # the agent's first turn.
            await anyio.to_thread.run_sync(world.pause)
            start_tick = await anyio.to_thread.run_sync(world.tick)
            outage = Outage(world)
            _outage.set(outage)

            async def on_continue(agent_state: AgentState) -> bool | str:
                await outage.end()
                now = await report()
                if finished(now, throughput) or now["tick"] - start_tick >= cap:
                    return False
                if agent_state.output.message.tool_calls:
                    return True
                return "The game is still running. Keep playing with the `fac` tool."

            agent = react(
                prompt=AgentPrompt(
                    instructions=instructions(),
                    assistant_prompt=None,
                    handoff_prompt=None,
                    submit_prompt=None,
                ),
                tools=[fac_tool(world, outage)],
                submit=False,
                on_continue=on_continue,
                compaction=CompactionSummary(),
            )
            await anyio.to_thread.run_sync(world.lua, "game.tick_paused = false")
            try:
                state = await as_solver(agent)(state, generate)
            finally:
                # A time limit cancels the sample; record what it reached anyway.
                with anyio.CancelScope(shield=True):
                    await anyio.to_thread.run_sync(world.pause)
                    final = await report()
                    final["paused_seconds"] = outage.total()
                    final["outages"] = outage.count
                    state.store.set("factobot", final)
                    _outage.set(None)
        return state

    return solve


# Scoring ------------------------------------------------------------------


@metric
def median() -> Metric:
    """Decision 20 reports medians over seeds."""

    def compute(scores: list[SampleScore]) -> float:
        return statistics.median(score.score.as_float() for score in scores)

    return compute


@scorer(metrics=[median(), stderr()])
def stage_score(
    stage: Stage,
    throughput: float | None = None,
    cap_ticks: int | None = None,
    pause_cap: float | None = None,
) -> Scorer:
    """Decision 23: reference time over the agent's time, in game ticks.

    A stage reached past the cap, or not at all, scores half of what finishing
    exactly at the cap would. With `throughput` set, the stage counts only once
    machines sustain that many packs a minute (decision 18). A run paused for
    model outages longer than `pause_cap` seconds is void (decision 19)."""
    cap = cap_ticks if cap_ticks is not None else stage.cap_ticks
    unreached = 0.5 * stage.reference_ticks / cap

    async def score(state: TaskState, target: Target) -> Score:
        report: dict[str, Any] | None = state.store.get("factobot")
        if report is None:
            # Not the agent's failure: Inspect marks the sample as an error.
            raise RuntimeError("the sample's world never started")
        paused = report["paused_seconds"]
        if pause_cap is not None and paused > pause_cap:
            raise RuntimeError(
                f"void: paused {paused:.0f} s for model outages, over the {pause_cap:g} s cap"
            )
        start, milestone = report["start_tick"], report["milestone_tick"]
        gate: dict[str, Any] = {"throughput": throughput}
        counts = milestone is not None and milestone - start <= cap
        if counts and throughput is not None:
            sustained = sustained_at(report, throughput)
            gate["sustained_at_tick"] = sustained
            counts = sustained is not None and sustained - start <= cap
        elif throughput is None:
            gate["note"] = "not applied: N for decision 18 is not set yet"
        ticks = milestone - start if milestone is not None else None
        value = stage.reference_ticks / max(ticks, 1) if counts and ticks is not None else unreached
        return Score(
            value=value,
            answer=str(ticks) if ticks is not None else None,
            explanation=(
                f"milestone after {ticks} ticks" if counts else f"not reached within {cap} ticks"
            ),
            metadata={
                "stage": stage.name,
                "reached": counts,
                "stage_ticks": ticks,
                "reference_ticks": stage.reference_ticks,
                "cap_ticks": cap,
                "start_tick": start,
                "end_tick": report["tick"],
                "gate": gate,
                "paused_seconds": paused,
                "outages": report["outages"],
            },
        )

    return score


# Tasks --------------------------------------------------------------------


def stage_task(
    stage: Stage,
    seeds: Sequence[int] = SEEDS,
    throughput: float | None = None,
    pause_cap: float | None = None,
    cap_ticks: int | None = None,
    setup: str | None = None,
    speed: float | None = None,
) -> Task:
    return Task(
        dataset=[
            Sample(input=goal(stage, throughput), id=f"seed-{seed}", metadata={"seed": seed})
            for seed in seeds
        ],
        solver=play(stage, throughput, cap_ticks, setup, speed),
        scorer=stage_score(stage, throughput, cap_ticks, pause_cap),
        # A void or broken seed is an error in the log, not the end of the
        # other seeds' runs; the metrics cover the seeds that scored.
        fail_on_error=False,
    )


@task
def red_science(
    seeds: Sequence[int] = SEEDS,
    throughput: float | None = None,
    pause_cap: float | None = None,
) -> Task:
    """Ladder stage 1: a fresh map to automated red science.

    `throughput` is decision 18's N in packs a minute, and `pause_cap` decision
    19's cap on seconds paused for model outages. Both are still to be set:
    without N the stage counts at the milestone alone, and without a cap no
    run is void."""
    return stage_task(RED_SCIENCE, seeds, throughput, pause_cap)
