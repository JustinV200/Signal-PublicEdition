"""Outages: log a failing idle-view source once when it fails, and once when it's back.

The idle view refreshes its sources every few seconds to minutes; a feed or a file
that stays broken must not fill the daemon log, so each outage logs at INFO once.
"""

import logging

logger = logging.getLogger(__name__)


class Outages:
    """Which sources are failing now."""

    def __init__(self) -> None:
        self._down: set[str] = set()

    def failed(self, source: str, error: object) -> None:
        """Note a failure; logged only if the source was fine before."""
        if source not in self._down:
            self._down.add(source)
            logger.info("idle view: %s unavailable (%s); keeping what it showed", source, error)

    def ok(self, source: str) -> None:
        """Note a success; logged only if the source was failing."""
        if source in self._down:
            self._down.discard(source)
            logger.info("idle view: %s is back", source)
