"""The tool registry: what each Signal tool needs, its setup steps, and how it's wired.

Loads data/tools.json (shared with the setup skill) into frozen dataclasses. The JSON
is the single source of truth; nothing here hard-codes a tool.
"""

import json
from dataclasses import dataclass, field, fields
from functools import cache
from importlib import resources
from typing import Any

# Step kinds the runner knows (see data/tools.json's _comment for what each does).
STEP_KINDS = frozenset({"run", "copy", "manual", "confirm", "email", "env", "samples", "settings"})


@dataclass(frozen=True)
class Step:
    """One setup step of a tool. Optional steps can be skipped without skipping the tool."""

    id: str
    title: str
    kind: str
    optional: bool = False
    default: bool = True
    terminal: bool = False
    argv: tuple[str, ...] = ()
    src: str = ""
    dst: str = ""
    text: str = ""
    doc: str = ""
    key: str = ""
    group: str = ""
    edits: tuple[dict[str, str], ...] = ()
    prereqs: tuple[str, ...] = ()
    mcp: tuple[str, ...] = ()
    permissions: tuple[str, ...] = ()
    statusline: bool = False


@dataclass(frozen=True)
class Hook:
    """A Claude Code hook a tool adds: run `module` with the tool's venv Python on `event`."""

    event: str
    module: str
    matcher: str = ""
    timeout: int = 0
    isolated: bool = False
    is_async: bool = False


@dataclass(frozen=True)
class Tool:
    """One Signal tool and everything setup does for it."""

    id: str
    name: str
    description: str
    platforms: tuple[str, ...]
    steps: tuple[Step, ...]
    verify: tuple[str, ...] = ()
    prereqs: tuple[str, ...] = ()
    needs: tuple[str, ...] = ()
    mcp: tuple[str, ...] = ()
    permissions: tuple[str, ...] = ()
    hooks: tuple[Hook, ...] = field(default=())

    def step(self, step_id: str) -> Step:
        """The step called `step_id`. Raises KeyError if the tool has no such step."""
        for step in self.steps:
            if step.id == step_id:
                return step
        raise KeyError(f"{self.id} has no step {step_id!r}")


def _tuples(raw: dict[str, Any], cls: type) -> dict[str, Any]:
    """Keep only `cls`'s fields from `raw`, turning lists into tuples (frozen dataclasses)."""
    names = {f.name for f in fields(cls)}
    return {k: tuple(v) if isinstance(v, list) else v for k, v in raw.items() if k in names}


def _hook(raw: dict[str, Any]) -> Hook:
    """A Hook from its JSON form ("async" is a Python keyword, so it maps to is_async)."""
    raw = dict(raw)
    raw["is_async"] = raw.pop("async", False)
    return Hook(**_tuples(raw, Hook))


def _tool(raw: dict[str, Any]) -> Tool:
    """A Tool from its JSON form. Raises ValueError on an unknown step kind."""
    steps = tuple(Step(**_tuples(s, Step)) for s in raw["steps"])
    for step in steps:
        if step.kind not in STEP_KINDS:
            raise ValueError(f"{raw['id']}.{step.id}: unknown step kind {step.kind!r}")
    hooks = tuple(_hook(h) for h in raw.get("hooks", ()))
    rest = _tuples({k: v for k, v in raw.items() if k not in ("steps", "hooks")}, Tool)
    return Tool(steps=steps, hooks=hooks, **rest)


@cache
def load() -> tuple[Tool, ...]:
    """Every tool in data/tools.json, in setup order."""
    text = resources.files("signal_setup").joinpath("data/tools.json").read_text("utf-8")
    return tuple(_tool(raw) for raw in json.loads(text)["tools"])


def by_id(tool_id: str) -> Tool:
    """The tool called `tool_id`. Raises KeyError listing the valid ids."""
    for tool in load():
        if tool.id == tool_id:
            return tool
    raise KeyError(f"unknown tool {tool_id!r}; choose from: {', '.join(t.id for t in load())}")
