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


# The same rows as the page's quoting test (web tests/state/actions/actionLabels.test.ts),
# so the page's label and the server's echo never differ.
@pytest.mark.parametrize(
    ("name", "label"),
    [
        ('lab "2"', 'Send to projector: "lab \\"2\\""'),
        ("café ☕", 'Send to projector: "café ☕"'),  # non-ASCII shows as typed
        ("a\u202eb\u200bc\n", r'Send to projector: "a\u202eb\u200bc\n"'),  # bidi, zero-width
        ("x\U000e0001", r'Send to projector: "x\udb40\udc01"'),  # an astral format char
        ("lab\u3164", r'Send to projector: "lab\u3164"'),  # a Hangul filler
        ("\ud800\x7f", r'Send to projector: "\ud800\u007f"'),  # lone surrogate, DEL
    ],
)
def test_load_label_quotes_the_name_as_typed_but_escapes_hidden_characters(name, label):
    assert plan_action("board.load", {"name": name}, {name: None}).display_text == label


def test_update_label_reads_like_its_button():
    # The page's actionLabel gives the same words (web actionLabels.test.ts).
    plan = plan_action("board.update", {"name": "grid"}, {"grid": "tasks"})
    assert plan.display_text == 'Show live version: "grid"'
