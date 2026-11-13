"""Buttons become fixed plans: save names must be current, Update never loads the old save."""

import pytest

from signal_console.actions import ActionError, HubStep, plan_action

SAVES = {"lecture": None, 'lab "2"': None, "agent-task-grid": "tasks", "week": "todo"}


@pytest.mark.parametrize(
    ("action", "args", "expected"),
    [
        ("voice.start", {}, HubStep(start=True)),
        ("board.load", {"name": 'lab "2"'}, ("load", "--no-ink", "--", 'lab "2"')),
        ("board.load", {"name": "deleted yesterday"}, ActionError),
        ("board.update", {"name": "agent-task-grid"}, ("tasks", "show")),
        ("board.update", {"name": "week"}, ("todo", "show")),
        ("board.update", {"view": "todo"}, ("todo", "show")),
        ("board.update", {"name": "lecture"}, ActionError),  # a save with no refresher
        ("board.idle", {}, ("idle", "show")),
        ("board.calibrate", {}, ("calibrate",)),
        ("shell.run", {}, ActionError),
        (["board.load"], {}, ActionError),
    ],
)
def test_plan_action(action, args, expected):
    if expected is ActionError:
        with pytest.raises(ActionError):
            plan_action(action, args, SAVES)
        return
    step = plan_action(action, args, SAVES).step
    assert step == expected if isinstance(expected, HubStep) else step.args == expected
