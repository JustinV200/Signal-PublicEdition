"""A tool's settings schema: data/settings/<tool>.json.

{"files": [{"path", "example", "group"}], "settings": [{"key", "file", "type", "level",
"description", "hint", "rerun", "id", "min", "max"}]}. A file with an example is copied from it when
missing; one without is a tracked file edited in place. A setting's group is its file's
group ("" for the tool's main settings step, e.g. "checker" for an optional one). `id`
defaults to `key` and must be unique in the tool. Defaults come from the example files.
"""

import json
from dataclasses import dataclass, fields
from functools import cache
from importlib import resources

from signal_setup.settings.values import TYPES

LEVELS = ("basic", "advanced")


@dataclass(frozen=True)
class ConfigFile:
    """One config file a tool's settings live in (paths relative to the repo root)."""

    path: str
    example: str = ""
    group: str = ""


@dataclass(frozen=True)
class Setting:
    """One editable value: `key` in `file`, of `type`, shown with its description and hint."""

    id: str
    key: str
    file: str
    type: str = "str"
    level: str = "basic"
    description: str = ""
    hint: str = ""
    rerun: str = ""
    group: str = ""
    # Inclusive bounds for int and float settings (None: unbounded).
    min: float | None = None
    max: float | None = None


@dataclass(frozen=True)
class Schema:
    """A tool's config files and settings."""

    tool: str
    files: tuple[ConfigFile, ...]
    settings: tuple[Setting, ...]

    def files_in(self, group: str) -> tuple[ConfigFile, ...]:
        """The files of one group."""
        return tuple(f for f in self.files if f.group == group)

    def in_group(self, group: str) -> tuple[Setting, ...]:
        """The settings of one group."""
        return tuple(s for s in self.settings if s.group == group)


def _setting(raw: dict, groups: dict[str, str]) -> Setting:
    """A Setting from JSON; raises ValueError on a bad type, level, file or field."""
    names = {f.name for f in fields(Setting)}
    if set(raw) - names:
        raise ValueError(f"unknown setting fields {sorted(set(raw) - names)}")
    setting = Setting(**{"id": raw["key"], **raw, "group": groups.get(raw["file"], "")})
    if setting.type not in TYPES or setting.level not in LEVELS or setting.file not in groups:
        raise ValueError(f"bad type, level or file in setting {setting.id!r}")
    return setting


@cache
def load(tool_id: str) -> Schema | None:
    """The tool's schema, or None when the tool has no settings."""
    path = resources.files("signal_setup").joinpath(f"data/settings/{tool_id}.json")
    if not path.is_file():
        return None
    raw = json.loads(path.read_text("utf-8"))
    files = tuple(ConfigFile(**f) for f in raw["files"])
    groups = {f.path: f.group for f in files}
    settings = tuple(_setting(s, groups) for s in raw["settings"])
    ids = [s.id for s in settings]
    if len(ids) != len(set(ids)):
        raise ValueError(f"{tool_id}: duplicate setting ids")
    return Schema(tool_id, files, settings)
