"""Reads and writes setting values in the real (gitignored) config files, and finds the
placeholders still left in them. Files keep their line endings and comments.
"""

import shutil
from pathlib import Path
from typing import Any

from signal_setup import progress
from signal_setup.registry import Tool
from signal_setup.settings import schema as schemas
from signal_setup.settings.formats import for_path
from signal_setup.settings.placeholders import is_placeholder
from signal_setup.settings.schema import Schema, Setting
from signal_setup.settings.values import parse


def _read(path: Path) -> tuple[str, bool]:
    """The file's text with '\\n' line ends, and whether it used CRLF."""
    raw = path.read_bytes().decode("utf-8")
    return raw.replace("\r\n", "\n"), "\r\n" in raw


def ensure_files(root: Path, schema: Schema, group: str) -> list[str]:
    """Copy each missing config file of `group` from its example. Returns the ones copied."""
    copied = []
    for config in schema.files_in(group):
        dst = root / config.path
        if config.example and not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / config.example, dst)
            copied.append(config.path)
    return copied


def current(root: Path, setting: Setting) -> Any:
    """The setting's value in its config file, or None (file or key missing)."""
    path = root / setting.file
    return for_path(path).read(_read(path)[0], setting.key) if path.exists() else None


def default(root: Path, schema: Schema, setting: Setting) -> Any:
    """The setting's value in the shipped example, or None for a tracked file."""
    example = next((f.example for f in schema.files if f.path == setting.file), "")
    path = root / example
    return for_path(path).read(_read(path)[0], setting.key) if example else None


def set_value(root: Path, setting: Setting, text: str) -> Any:
    """Parse `text`, write it into the config file, and return the value.

    Raises ValueError for a bad value, a placeholder, or a config file that isn't there yet.
    """
    value = parse(setting.type, text)
    _check_range(setting, value)
    if is_placeholder(value):
        raise ValueError(f"{text!r} is still a placeholder; give your real value")
    path = root / setting.file
    if not path.exists():
        raise ValueError(f"{setting.file} doesn't exist yet; run setup for the tool first")
    fmt = for_path(path)
    body, crlf = _read(path)
    body = fmt.write(body, setting.key, fmt.literal(value))
    path.write_bytes((body.replace("\n", "\r\n") if crlf else body).encode("utf-8"))
    return value


def _check_range(setting: Setting, value: Any) -> None:
    """Raise ValueError when a number is outside the setting's min/max."""
    low, high = setting.min, setting.max
    if (low is not None and value < low) or (high is not None and value > high):
        raise ValueError(f"{value} is out of range (lowest {low}, highest {high})")


def leftovers(root: Path, schema: Schema, group: str) -> list[Setting]:
    """Every value in `group`'s config files that is still a placeholder.

    A placeholder the schema doesn't name comes back as a plain text setting with the
    id "<file>:<key>", so it can be prompted for and set like any other. A config file
    that has an example but doesn't exist yet comes back as "<file>: missing".
    """
    known = {(s.file, s.key): s for s in schema.settings}
    found = []
    for config in schema.files_in(group):
        path = root / config.path
        if not path.exists():
            # A file with an example has to be made and filled in; one without is optional.
            if config.example:
                found.append(Setting(f"{config.path}: missing", "", config.path))
            continue
        try:
            pairs = for_path(path).entries(_read(path)[0])
        except ValueError as error:
            found.append(Setting(f"{config.path}: unreadable ({error})", "", config.path))
            continue
        for key, value in pairs:
            if is_placeholder(value):
                found.append(
                    known.get((config.path, key))
                    or Setting(f"{config.path}:{key}", key, config.path, group=group)
                )
    return found


def find(root: Path, schema: Schema, setting_id: str) -> Setting:
    """A schema setting, or a leftover placeholder, by id. Raises KeyError."""
    for setting in schema.settings:
        if setting.id == setting_id:
            return setting
    groups = {f.group for f in schema.files}
    for setting in (s for g in groups for s in leftovers(root, schema, g)):
        if setting.id == setting_id:
            return setting
    raise KeyError(
        f"{schema.tool} has no setting {setting_id!r}; see setup config {schema.tool} --list"
    )


def tool_leftovers(root: Path, tool: Tool, data: dict[str, Any]) -> list[str]:
    """Ids of placeholders left in the tool's config, for groups whose step isn't skipped."""
    schema = schemas.load(tool.id)
    if schema is None:
        return []
    groups = {
        s.group
        for s in tool.steps
        if s.kind == "settings" and progress.step_status(data, tool.id, s.id) != progress.SKIPPED
    }
    return [s.id for g in sorted(groups) for s in leftovers(root, schema, g)]
