"""Poll the orchestrator claim, the voice hub and the whiteboard; publish `state` on change.

A claim that differs from the last one seen (another session or label, or
the one found at startup) also gets a `note` event in the feed. The state
carries the owner's `away` block too (signal_console.away: here, away or
asleep; null while the brief's state can't be read), for the title row. Each poll
also checks the claimed session is still open (its inbox pipe is listed),
published as `orchestrator.alive`. The
orchestrator's turn state comes from its turn hooks (record_turn) plus the
session's subagents in usage.json, read each poll. So do the model strip's
files (signal_console.models): the settings' next-session pick, the claimed
session's model and voice's pick. The state also carries `openCommand`
(open_hint), which the page shows while the server is down.

Also tails the hub's log every POLL_S for its phase and the voice feed (see
hub_feed). With no page listening, the rest is re-read only every IDLE_POLL_S
(a page that connects gets a fresh snapshot anyway). A hub process that is
alive but not listening yet reads as running in phase "starting", so Stop
works while it loads (or if it hangs). The whiteboard daemon
logs every request, so it's only polled while a page is listening, every
BOARD_POLL_S, and when /api/state or a board action needs fresh saves.
"""

import asyncio
import logging
import math
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiohttp
from signal_brief import BriefLogError, BriefPaths

from signal_console.away import away_payload
from signal_console.hub import find_console_hub, find_hub
from signal_console.models import ModelFiles, models_state
from signal_console.open_hint import open_command
from signal_console.orchestrator import Claim, claimed_ago, is_claim_alive, read_claim
from signal_console.paths import USAGE_FILE_PATH
from signal_console.server.events import EventHub, new_event_id, now_iso
from signal_console.server.hub_feed import HubFeed
from signal_console.status import BoardStatus, is_hub_listening, read_board_status
from signal_console.turns import TurnReport, TurnTracker, UsageAgents

POLL_S = 1.0
IDLE_POLL_S = 5.0
STARTING_PHASE = "starting"
BOARD_POLL_S = 10.0

log = logging.getLogger(__name__)


class StatusWatcher:
    """Keeps the console's /api/state current and feeds hub output into the event feed."""

    # Six parameters, over the usual limit: the keyword-only three are file locations.
    def __init__(
        self,
        events: EventHub,
        state_dir: Path,
        session: aiohttp.ClientSession,
        *,
        model_files: ModelFiles,
        brief_paths: BriefPaths,
        usage_path: Path = USAGE_FILE_PATH,
    ) -> None:
        """Set up; nothing is read until refresh() or run(). Tests pass their own file paths."""
        self._events = events
        self._model_files = model_files
        self._brief_paths = brief_paths
        # The owner's away block, re-read each refresh; None until then or while unreadable.
        self._away: dict[str, Any] | None = None
        self._state_dir = state_dir
        self._session = session
        self._feed = HubFeed(events, state_dir)
        self._refreshed_at = -math.inf
        self._voice: dict[str, Any] = {"running": False, "phase": "off", "startedBy": None}
        self._boards = BoardStatus()
        self._boards_read_at = -math.inf
        self._turns = TurnTracker()
        self._usage = UsageAgents(usage_path)
        # (socket, label) of the claim last seen; None until one is seen.
        self._claim_identity: tuple[str, str | None] | None = None
        self._last_state: dict[str, Any] | None = None

    async def run(self) -> None:
        """Poll forever (until cancelled), logging and riding out any failed round."""
        while True:
            try:
                is_watched = self._events.listener_count > 0
                if is_watched or time.monotonic() - self._refreshed_at >= IDLE_POLL_S:
                    await self.refresh(read_boards=is_watched)
                else:
                    self._feed.read()  # The voice history stays complete with no page open.
            except Exception:
                log.exception("console status poll failed")
            await asyncio.sleep(POLL_S)

    async def refresh(self, *, read_boards: bool) -> None:
        """Re-read everything (the boards only if asked and due) and publish any change."""
        self._refreshed_at = time.monotonic()
        self._feed.read()
        self._voice = await self._read_voice()
        # In a thread: an expired away mode is ended under the brief's lock (up to 2 s).
        self._away = await asyncio.to_thread(self._read_away)
        if read_boards and time.monotonic() - self._boards_read_at >= BOARD_POLL_S:
            await self._read_boards()
        self._publish_if_changed()

    async def snapshot(self) -> dict[str, Any]:
        """The current state, freshly read (the /api/state body)."""
        await self.refresh(read_boards=True)
        return self._build_state()

    async def saves(self) -> dict[str, str | None]:
        """The whiteboard saves that exist now (read fresh), each name mapped to its refresher."""
        await self._read_boards()
        self._publish_if_changed()
        return {str(save["name"]): save.get("refresher") for save in self._boards.saves}

    def voice_status(self) -> dict[str, Any]:
        """The voice hub's state (IDLE_POLL_S old at most, POLL_S if watched)."""
        return dict(self._voice)

    def record_turn(self, report: TurnReport) -> None:
        """Apply a turn hook report from the claimed session and publish any change."""
        # Notice a new claim first: its reset must not wipe the new session's first report.
        self._track_claim(read_claim(self._state_dir))
        self._turns.record(report)
        self._publish_if_changed()

    def _build_state(self) -> dict[str, Any]:
        claim = read_claim(self._state_dir)
        self._track_claim(claim)
        orchestrator = {
            "claimed": claim is not None,
            # A boolean only: the socket name and token never leave the server.
            "alive": is_claim_alive(claim),
            "label": claim.label if claim else None,
            # The page words it as an age in the tooltip ("linked 3d ago").
            "claimedAt": claim.claimed_at if claim else None,
            "turn": self._turn_state() if claim else None,
        }
        board = {
            "saves": self._boards.saves,
            "view": self._boards.view,
            "itemCount": self._boards.item_count,
            "online": self._boards.online,
        }
        models = models_state(
            self._model_files,
            self._turns.session_id,
            self._turns.effort,
            is_claimed=claim is not None,
        )
        return {
            "orchestrator": orchestrator,
            "voice": self._voice,
            "board": board,
            "models": models,
            "away": self._away,
            # The page caches it to show while the server is down (no secret in it).
            "openCommand": open_command(),
        }

    def _track_claim(self, claim: Claim | None) -> None:
        # Any process that can run `console claim` can repoint the console, so every
        # change of session or label (and the claim found at startup) shows in the feed.
        identity = (claim.socket, claim.label) if claim else None
        if identity == self._claim_identity:
            return
        old_socket = self._claim_identity[0] if self._claim_identity else None
        if identity is None or identity[0] != old_socket:
            # Another session: what the old one's hooks said doesn't apply to it.
            self._turns.reset()
        self._claim_identity = identity
        note = {"id": new_event_id(), "text": _claim_note(claim), "at": now_iso()}
        self._events.publish("note", note)

    def _turn_state(self) -> dict[str, Any]:
        now = time.time()
        usage = self._usage.read(self._turns.session_id, now)
        if usage.updated_at is not None:
            # A usage hook from the session (an agent starting or stopping) is activity too.
            self._turns.note_activity(usage.updated_at)
        return self._turns.status(now, usage.count)

    def _publish_if_changed(self) -> None:
        state = self._build_state()
        if state != self._last_state:
            self._last_state = state
            self._events.publish("state", state)

    async def _read_voice(self) -> dict[str, Any]:
        is_listening = await is_hub_listening()
        if find_console_hub(self._state_dir) is not None:
            phase = self._feed.phase if is_listening else STARTING_PHASE
            return {"running": True, "phase": phase, "startedBy": "console"}
        if is_listening:
            # Started some other way: its output isn't ours to read.
            return {"running": True, "phase": None, "startedBy": "external"}
        if find_hub() is not None:
            return {"running": True, "phase": STARTING_PHASE, "startedBy": "external"}
        return {"running": False, "phase": "off", "startedBy": None}

    def _read_away(self) -> dict[str, Any] | None:
        try:
            return away_payload(self._brief_paths, datetime.now().astimezone())
        except BriefLogError as error:
            # The page words a null block as "can't tell"; the next refresh tries again.
            log.debug("away state unreadable: %s", error)
            return None

    async def _read_boards(self) -> None:
        self._boards = await read_board_status(self._session)
        self._boards_read_at = time.monotonic()


def _claim_note(claim: Claim | None) -> str:
    if claim is None:
        return "No Claude session is linked now, so messages can't be sent."
    who = f'the session labelled "{claim.label}"' if claim.label else "an unlabelled session"
    age = claimed_ago(claim.claimed_at, datetime.now(UTC))
    when = f" ({age})" if age else ""
    return f"Messages now go to {who}{when}."
