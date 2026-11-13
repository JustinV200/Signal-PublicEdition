"""Apply one model or effort pick from the console: an index into a fixed list, never a string.

Orchestrator picks go into .claude/settings.local.json (settings_writer), so
they reach every new Signal session; each of its lists starts with
USE_USER_SETTINGS, which removes the key. Voice picks go into
brain-choice.json, which the brain reads before each turn.
"""

from dataclasses import replace
from typing import Literal

from signal_jsonstate import state_lock, write_json_atomic
from signal_modelchoice import EFFORT_LEVELS, MODEL_ALIASES, read_brain_choice

from signal_console.models.files import ModelFiles
from signal_console.models.settings_writer import SettingsFiles, write_local_setting

Target = Literal["orchestrator", "voice"]
Field = Literal["model", "effort"]
TARGETS: tuple[Target, ...] = ("orchestrator", "voice")
FIELDS: tuple[Field, ...] = ("model", "effort")

# The orchestrator lists' first entry: unset the key, so the user settings decide.
USE_USER_SETTINGS = None
SETTINGS_KEYS: dict[Field, str] = {"model": "model", "effort": "effortLevel"}


class PickError(ValueError):
    """The request named no known target or field, or an index outside its list."""


def pick_options(target: Target, field: Field) -> tuple[str | None, ...]:
    """The list a pick for `target`'s `field` indexes into (None = use my user settings)."""
    values = MODEL_ALIASES if field == "model" else EFFORT_LEVELS
    # Voice always passes an explicit model and effort, so it has no "unset" entry.
    return (USE_USER_SETTINGS, *values) if target == "orchestrator" else values


def apply_pick(files: ModelFiles, target: object, field: object, index: object) -> None:
    """Write the pick at `index` of pick_options(target, field).

    Args:
        files: Where the settings, backup, voice pick and lock live.
        target: "orchestrator" or "voice" (from the request, unchecked).
        field: "model" or "effort" (unchecked).
        index: The position in that list (unchecked).

    Raises:
        PickError: The target, field or index isn't valid.
        SettingsWriteError: The settings file refused the write (see settings_writer).
        signal_jsonstate.StateFileError: The lock or voice's file couldn't be taken or written.
    """
    checked_target = _member(target, TARGETS, "target")
    checked_field = _member(field, FIELDS, "field")
    options = pick_options(checked_target, checked_field)
    # bool is an int subclass, and True isn't a position.
    if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(options):
        raise PickError(f"index must be 0 to {len(options) - 1}")
    value = options[index]
    with state_lock(files.lock):
        if checked_target == "orchestrator":
            settings = SettingsFiles(files.settings, files.backup)
            write_local_setting(settings, SETTINGS_KEYS[checked_field], value)
        else:
            _write_voice_choice(files, checked_field, value)


def _member[T](value: object, allowed: tuple[T, ...], what: str) -> T:
    # Returns the list's own item, so the result carries its Literal type.
    for item in allowed:
        if item == value:
            return item
    raise PickError(f"{what} must be one of {allowed}")


def _write_voice_choice(files: ModelFiles, field: Field, value: str | None) -> None:
    # Keep the other field's pick; an unlisted value already on disk reads as unset.
    choice = replace(read_brain_choice(files.brain_choice), **{field: value})
    files.brain_choice.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(files.brain_choice, choice.as_json())
