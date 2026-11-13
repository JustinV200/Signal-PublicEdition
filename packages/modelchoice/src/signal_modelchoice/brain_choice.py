"""Voice's model and effort pick: the format of tools/audiohub/.cache/brain-choice.json.

The console writes `{model, effort}` there when the owner picks one; the voice
brain reads it at connect and before each turn. Each value is checked against
choices.py, and one that isn't listed reads as unset (and is logged), so a
hand edit can only ever fall back to audiohub.toml, never pass an odd value to
the CLI.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from signal_modelchoice.choices import EFFORT_LEVELS, MODEL_ALIASES

log = logging.getLogger(__name__)

# The file is two short strings; anything much bigger isn't ours.
MAX_FILE_BYTES = 4096


@dataclass(frozen=True)
class BrainChoice:
    """Voice's pick. None means unset: the brain uses audiohub.toml's value.

    Attributes:
        model: One of MODEL_ALIASES, or None.
        effort: One of EFFORT_LEVELS, or None.
    """

    model: str | None = None
    effort: str | None = None

    def as_json(self) -> dict[str, str | None]:
        """The file's JSON object."""
        return {"model": self.model, "effort": self.effort}


def read_brain_choice(path: Path) -> BrainChoice:
    """The validated pick in `path`; a missing, unreadable or malformed file reads as unset.

    Args:
        path: brain-choice.json.

    Returns:
        A BrainChoice with each unlisted or missing value as None.
    """
    try:
        raw = path.read_bytes()[: MAX_FILE_BYTES + 1]
    except FileNotFoundError:
        return BrainChoice()
    except OSError as error:
        log.warning("can't read %s, using the defaults: %s", path.name, error)
        return BrainChoice()
    try:
        payload = json.loads(raw) if len(raw) <= MAX_FILE_BYTES else None
    except (ValueError, RecursionError):  # deep nesting overflows the parser
        payload = None
    if not isinstance(payload, dict):
        log.warning("%s isn't a small JSON object; using the defaults", path.name)
        return BrainChoice()
    return BrainChoice(
        model=_listed(payload, "model", MODEL_ALIASES, path),
        effort=_listed(payload, "effort", EFFORT_LEVELS, path),
    )


def _listed(
    payload: dict[str, object], key: str, allowed: tuple[str, ...], path: Path
) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if isinstance(value, str) and value in allowed:
        return value
    log.warning("ignoring %s %r in %s: not one of %s", key, value, path.name, allowed)
    return None
