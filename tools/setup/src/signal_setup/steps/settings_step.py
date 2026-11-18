"""The `settings` step: copy a tool's config files, then fill in its settings.

At the terminal it asks every basic setting (Enter keeps the current value), then every
placeholder still left, then offers the advanced ones. The agent's asker has no answers,
so it only reports the placeholders left and the `setup config ... --set` command. The
step is done only when no placeholder is left in the group's files.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from signal_setup import progress, settings
from signal_setup.registry import Step, Tool
from signal_setup.settings import Setting

NEEDS_INPUT = "needs_input"


def _ask(root: Path, setting: Setting, asker: Any) -> bool:
    """Ask one setting until it's valid or kept. Returns True if it changed."""
    now = settings.current(root, setting)
    hint = f" ({setting.hint})" if setting.hint else ""
    asker.say(f"\n{setting.id}: {setting.description or 'placeholder value'}{hint}")
    while True:
        text = asker.text(f"New value, Enter keeps [{settings.display(now)}]")
        if text is None:
            if settings.is_placeholder(now, settings.is_prose_file(setting.file)):
                asker.say("That's still a placeholder; the tool won't count as set up.")
            return False
        try:
            settings.set_value(root, setting, text)
            return True
        except ValueError as error:
            asker.say(str(error))


def _prompt(root: Path, schema: settings.Schema, group: str, asker: Any) -> list[Setting]:
    """Basic settings, then leftover placeholders, then (if wanted) advanced. Returns changed."""
    basic = [s for s in schema.in_group(group) if s.level == "basic"]
    changed = [s for s in basic if _ask(root, s, asker)]
    extra = [s for s in settings.leftovers(root, schema, group) if s not in basic]
    changed += [s for s in extra if _ask(root, s, asker)]
    advanced = [s for s in schema.in_group(group) if s.level == "advanced" and s not in extra]
    if advanced and asker.confirm("Customise advanced settings?", False):
        changed += [s for s in advanced if _ask(root, s, asker)]
    return changed


def rerun_steps(tool: Tool, changed: list[Setting], data: dict[str, Any]) -> list[Step]:
    """Already-done steps that must run again because a changed setting names them."""
    ids = dict.fromkeys(s.rerun for s in changed if s.rerun)
    return [tool.step(i) for i in ids if progress.step_status(data, tool.id, i) == progress.DONE]


def run(
    root: Path,
    tool: Tool,
    step: Step,
    data: dict[str, Any],
    asker: Any,
    rerun: Callable[[Step], str],
) -> str:
    """Run the settings step. Returns 'done', 'failed' or NEEDS_INPUT."""
    schema = settings.load(tool.id)
    if schema is None:
        return progress.DONE
    for path in settings.ensure_files(root, schema, step.group):
        asker.say(f"Created {path} from its example.")
    if asker.interactive:
        for again in rerun_steps(tool, _prompt(root, schema, step.group, asker), data):
            asker.say(f"Settings changed, so running '{again.title}' again.")
            rerun(again)
    left = [s.id for s in settings.leftovers(root, schema, step.group)]
    if not left:
        return progress.DONE
    asker.say("Placeholders left: " + ", ".join(left))
    if asker.interactive:
        return progress.FAILED
    asker.say(f"Ask the user for each value, then run: setup config {tool.id} --set id=value")
    return NEEDS_INPUT
