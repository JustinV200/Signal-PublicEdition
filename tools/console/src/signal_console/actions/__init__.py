"""Public API of signal_console.actions: check a console button and run it directly.

The console server runs every button itself (no orchestrator turn): the voice
hub through signal_console.hub, the whiteboard through its CLI.
"""

from signal_console.actions.plans import (
    BOARD_LOCK,
    SAVE_ACTIONS,
    ActionError,
    ActionPlan,
    HubStep,
    WhiteboardStep,
    plan_action,
)
from signal_console.actions.steps import ActionTools, run_step
from signal_console.actions.whiteboard_cli import StepFailed, run_whiteboard

__all__ = [
    "BOARD_LOCK",
    "SAVE_ACTIONS",
    "ActionError",
    "ActionPlan",
    "ActionTools",
    "HubStep",
    "StepFailed",
    "WhiteboardStep",
    "plan_action",
    "run_step",
    "run_whiteboard",
]
