"""The base error whose message we wrote ourselves and is safe to show the model.

It lives here, below every subpackage, so the session (which actions build on) can
raise one without importing browser_tool.actions. browser_tool.actions re-exports it,
and the tool runner turns any of them into plain result text.
"""


class ActionError(Exception):
    """A refusal or failure whose message is written by us and safe to show the model."""
