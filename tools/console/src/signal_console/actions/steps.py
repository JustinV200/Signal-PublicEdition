"""Run one action step (voice hub start/stop or a whiteboard command) and say what happened.

The hub calls are the same functions `console hub start|stop` runs, with the
same safety: start refuses while a hub runs, stop asks the hub to exit
cleanly and kills only the hub's own processes if it doesn't. They block
(stop waits up to 10 s for the hub to exit), so they run in a thread.
A start is done only once the hub listens: it fails with the log's last line
if the hub exits first, and says it's still starting after READY_TIMEOUT_S.
It frees its lock once the hub is spawned, so Stop works while the hub loads.
"""

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from signal_console.actions.plans import HubStep, Step, WhiteboardStep
from signal_console.actions.whiteboard_cli import StepFailed, run_whiteboard
from signal_console.hub import HubError, HubRecord, start_hub, stop_hub, wait_for_hub


@dataclass(frozen=True)
class ActionTools:
    """What the steps call; tests pass fakes.

    Attributes:
        start_hub: signal_console.hub.start_hub.
        stop_hub: signal_console.hub.stop_hub.
        run_whiteboard: Runs `whiteboard <args>` and returns its stdout, or raises StepFailed.
        wait_for_hub: signal_console.hub.wait_for_hub.
    """

    start_hub: Callable[[Path], HubRecord] = start_hub
    stop_hub: Callable[[Path], bool] = stop_hub
    run_whiteboard: Callable[[Sequence[str]], Awaitable[str]] = run_whiteboard
    wait_for_hub: Callable[[Path, HubRecord], bool] = wait_for_hub


async def run_step(
    step: Step, state_dir: Path, tools: ActionTools, unlock: Callable[[], None] = lambda: None
) -> str:
    """Run the step and return what the console shows when it worked.

    Args:
        step: From the action's plan.
        state_dir: The console's .state folder (the hub's record and log).
        tools: The functions to call.
        unlock: Frees the action's lock early (a voice start calls it once the hub is spawned).

    Raises:
        StepFailed: It didn't work; the message says why.
    """
    if isinstance(step, HubStep):
        return await _run_hub(step, state_dir, tools, unlock)
    return await _run_whiteboard(step, tools)


async def _run_hub(
    step: HubStep, state_dir: Path, tools: ActionTools, unlock: Callable[[], None]
) -> str:
    try:
        if step.start:
            record = await asyncio.to_thread(tools.start_hub, state_dir)
            # The wait only polls, so a Stop click may run during it.
            unlock()
            if await asyncio.to_thread(tools.wait_for_hub, state_dir, record):
                return f"Voice hub ready (pid {record.pid})."
            return f"Voice hub still starting after a minute (pid {record.pid}); see hub.log."
        stopped = await asyncio.to_thread(tools.stop_hub, state_dir)
    except (HubError, OSError) as error:
        raise StepFailed(str(error)) from error
    return "Voice hub stopped." if stopped else "No voice hub the console can stop is running."


async def _run_whiteboard(step: WhiteboardStep, tools: ActionTools) -> str:
    output = await tools.run_whiteboard(step.args)
    first_line = output.splitlines()[0] if output else ""
    return f"{step.done_text} {first_line}".strip() if step.shows_output else step.done_text
