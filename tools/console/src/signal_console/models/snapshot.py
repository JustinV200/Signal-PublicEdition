"""The `models` block of /api/state: what the model strip shows.

- orchestrator.now: the claimed session's model (session-models.json, by the
  id its turn hooks report) and the effort its last Stop carried. Null with no
  claim; either value is null while unknown.
- orchestrator.next: the `model` and `effortLevel` in settings.local.json,
  which every new Signal session starts with (null = the user settings decide).
  The whole block is null when the file can't be read as a JSON object.
- voice: brain-choice.json's validated pick (null = audiohub.toml decides).
- choices: the lists a pick's index points into (signal_console.models.picks).
"""

import json
from pathlib import Path
from typing import Any

from signal_jsonstate import read_bytes_retrying
from signal_modelchoice import read_brain_choice

from signal_console.models.files import ModelFiles
from signal_console.models.picks import FIELDS, TARGETS, pick_options
from signal_console.models.session_models import is_model_id, read_session_model

# Shown for a settings value the strip can't vouch for (not a short model id or effort).
UNRECOGNISED = "unrecognised"


def models_state(
    files: ModelFiles, session_id: str | None, effort: str | None, *, is_claimed: bool
) -> dict[str, Any]:
    """The `models` block.

    Args:
        files: Where the settings, session models and voice pick live.
        session_id: The claimed session's id from its turn hooks, or None before any.
        effort: The effort level from that session's last Stop, or None.
        is_claimed: Whether a session has claimed the console.
    """
    now = None
    if is_claimed:
        model = read_session_model(files.session_models, session_id) if session_id else None
        now = {"model": model, "effort": effort}
    return {
        "orchestrator": {"now": now, "next": _next_session(files.settings)},
        "voice": read_brain_choice(files.brain_choice).as_json(),
        "choices": {
            target: {field: list(pick_options(target, field)) for field in FIELDS}
            for target in TARGETS
        },
    }


def _next_session(path: Path) -> dict[str, str | None] | None:
    try:
        settings = json.loads(read_bytes_retrying(path))
    except (OSError, ValueError, RecursionError):  # deep nesting overflows the parser
        return None
    if not isinstance(settings, dict):
        return None
    return {"model": _shown(settings.get("model")), "effort": _shown(settings.get("effortLevel"))}


def _shown(value: object) -> str | None:
    if value is None:
        return None
    # The same short-id check fits effort words, and keeps odd text off the page.
    return value if is_model_id(value) else UNRECOGNISED
