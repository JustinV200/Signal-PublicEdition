"""Public API of signal_console.away: the Devices page's Away/Here toggle (brief away mode)."""

from signal_console.away.control import away_payload, set_away

__all__ = ["away_payload", "set_away"]
