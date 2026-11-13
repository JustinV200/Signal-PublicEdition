"""`PresenceFiles`: is the owner asleep or away? Read from other tools' state files, by path.

Notifications from other agents are dropped while the owner is asleep (sleepmode's
`.state/state.json` has `"is_asleep": true`) or away (the brief tool's
`.state/away.json` has `"on": true` and an ISO `"until"` still ahead). The
files are read, never imported, so the tools stay independent. A missing or
unreadable file counts as awake and here: failing open means a broken file
never silences the hub.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ASLEEP_REASON = "the owner is asleep"
AWAY_REASON = "the owner is away"


@dataclass(frozen=True)
class PresenceFiles:
    """Where sleepmode and the brief tool keep their state.

    Attributes:
        sleep_state: sleepmode's state.json.
        away_state: the brief tool's away.json.
    """

    sleep_state: Path
    away_state: Path

    def quiet_reason(self, now: datetime | None = None) -> str | None:
        """Why a notification shouldn't be spoken now, or None to speak it.

        Args:
            now: The current time (default: now, local and aware); tests pass their own.

        Returns:
            ASLEEP_REASON, AWAY_REASON or None.
        """
        if _read_object(self.sleep_state).get("is_asleep") is True:
            return ASLEEP_REASON
        if _is_away(_read_object(self.away_state), now or datetime.now().astimezone()):
            return AWAY_REASON
        return None


def _is_away(record: dict[str, Any], now: datetime) -> bool:
    """Away mode is on and its end is still ahead (the brief tool ends it once passed)."""
    if record.get("on") is not True or not isinstance(record.get("until"), str):
        return False
    try:
        until = datetime.fromisoformat(record["until"])
    except ValueError:
        return False
    # The brief writes aware times; a naive one is local, as the brief reads it.
    return (until if until.tzinfo else until.astimezone()) > now


def _read_object(path: Path) -> dict[str, Any]:
    """The JSON object in `path`, or {} if it's missing, unreadable or not an object."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as error:
        logger.warning("can't read %s, treating it as unset: %s", path, error)
        return {}
    return payload if isinstance(payload, dict) else {}
