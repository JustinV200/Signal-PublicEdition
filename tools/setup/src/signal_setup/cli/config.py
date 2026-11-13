"""`setup config`: view and change a tool's settings after (or during) setup.

setup config [tool]                       interactive, like the settings step
setup config <tool> --list                every setting as JSON (the agent's view)
setup config <tool> --set id=value ...    set values without prompting (the agent)
"""

import json
from pathlib import Path

from signal_setup import progress, registry, settings
from signal_setup.cli.agent import AgentAsker
from signal_setup.steps import run_step
from signal_setup.steps.settings_step import rerun_steps
from signal_setup.terminal import TerminalAsker


def _schema(tool_id: str) -> settings.Schema:
    """The tool's schema. Raises KeyError when it has no settings."""
    schema = settings.load(registry.by_id(tool_id).id)
    if schema is None:
        raise KeyError(f"{tool_id} has no settings")
    return schema


def list_settings(root: Path, tool_id: str) -> int:
    """Print every setting of the tool, plus unnamed placeholders, as JSON."""
    schema = _schema(tool_id)
    extra = [
        s
        for g in {f.group for f in schema.files}
        for s in settings.leftovers(root, schema, g)
        if s not in schema.settings
    ]
    rows = []
    for s in (*schema.settings, *extra):
        value = settings.current(root, s)
        rows.append(
            {
                "id": s.id,
                "file": s.file,
                "group": s.group,
                "value": value,
                "default": settings.default(root, schema, s),
                "type": s.type,
                "level": s.level,
                "description": s.description,
                "hint": s.hint,
                "min": s.min,
                "max": s.max,
                "is_placeholder": settings.is_placeholder(value),
            }
        )
    print(json.dumps(rows, indent=2))
    return 0


def set_settings(root: Path, tool_id: str, pairs: list[str]) -> int:
    """Set each id=value, re-run steps the changes affect, and re-check the settings steps.

    Exit 0 when every value was set, 1 when any was refused.
    """
    schema, tool = _schema(tool_id), registry.by_id(tool_id)
    data, asker = progress.load(root), AgentAsker(None, None)
    changed, errors = [], {}
    for pair in pairs:
        setting_id, sep, text = pair.partition("=")
        try:
            if not sep:
                raise ValueError("use id=value")
            setting = settings.find(root, schema, setting_id.strip())
            settings.set_value(root, setting, text)
            changed.append(setting)
        except (KeyError, ValueError) as error:
            errors[setting_id] = str(error.args[0])
    reruns = {s.id: run_step(root, tool, s, data, asker) for s in rerun_steps(tool, changed, data)}
    groups = {s.group for s in changed}
    for step in (s for s in tool.steps if s.kind == "settings" and s.group in groups):
        if progress.step_status(data, tool.id, step.id) != progress.SKIPPED:
            run_step(root, tool, step, data, asker)  # done once no placeholder is left
    progress.save(root, data)
    print(
        json.dumps(
            {
                "set": [s.id for s in changed],
                "errors": errors,
                "reruns": reruns,
                "placeholders_left": settings.tool_leftovers(root, tool, data),
                "messages": asker.messages,
            },
            indent=2,
        )
    )
    return 1 if errors else 0


def interactive(root: Path, tool_id: str | None) -> int:
    """Run the settings steps of one tool, or of every chosen tool, at the terminal."""
    data, asker = progress.load(root), TerminalAsker()
    ids = [tool_id] if tool_id else data["chosen"]
    for tool in (registry.by_id(i) for i in ids):
        for step in (s for s in tool.steps if s.kind == "settings"):
            if step.optional and not asker.confirm(f"{tool.name}: {step.title}?", step.default):
                continue
            asker.say(f"\n== {tool.name}: {step.title} ==")
            run_step(root, tool, step, data, asker)
            progress.save(root, data)
    return 0
