"""Duck music (lower other apps' per-session volume) while Claude speaks.

Fades the configured processes' Windows sessions (default Spotify.exe) to
`level` times their volume and back; the voice output wraps speech in
`ducker.ducked()`. Everything is keyed by app id (no process id), because
sessions come and go when an app restarts and Windows brings it back at its
last, ducked, per-app volume. Apps that couldn't be restored become leftovers
in `.cache/ducking.json`; the next duck (or the next Ducker, after a crash)
puts any that are still at their ducked level back. Best effort: nothing here
raises, failures are logged, and duck/restore share a lock.
"""

import contextlib
import logging
import threading
from collections.abc import Callable, Iterator
from pathlib import Path

from audiohub.audio.ducking.fade import FadePlan, fade_volumes
from audiohub.audio.ducking.saved_volumes import (
    SavedVolume,
    delete_saved_volumes,
    load_saved_volumes,
    save_volumes,
)
from audiohub.audio.ducking.sessions import AppSession, com_initialized, find_sessions
from audiohub.config import CACHE_DIR, DuckingSettings

logger = logging.getLogger(__name__)

DUCKING_STATE_PATH = CACHE_DIR / "ducking.json"

# How close (0.0-1.0 scale) a volume must be to a saved ducked level to count
# as "still where ducking left it". Windows stores volumes as float32.
VOLUME_MATCH_TOLERANCE = 0.01


class Ducker:
    """Fades target apps' session volume down and back up.

    `duck()` and `restore()` block for about `fade_ms`, so async callers
    should run them in an executor. They're safe to call from any thread.
    """

    def __init__(self, settings: DuckingSettings, state_path: Path = DUCKING_STATE_PATH) -> None:
        """Create a ducker, first restoring volumes a crashed run left ducked.

        Args:
            settings: Target process names, duck level, fade time, enabled flag.
            state_path: Where captures and leftovers are saved.
        """
        self._settings = settings
        self._state_path = state_path
        self._lock = threading.Lock()
        # app_id -> volumes for apps this run ducked; restored unconditionally.
        self._captured: dict[str, SavedVolume] = {}
        # app_id -> volumes not yet restored (earlier run, or app absent at
        # restore); restored only while still at the ducked level.
        self._leftovers = load_saved_volumes(state_path)
        self._has_logged_no_sessions = False
        if self._leftovers:
            with self._lock:
                _run_with_com(
                    lambda: self._recover_leftovers(self._find_sessions_by_app()),
                    "could not restore music volume left ducked by an earlier run",
                )

    @property
    def is_ducked(self) -> bool:
        """Whether this Ducker currently holds any app at a ducked volume."""
        return bool(self._captured)

    def duck(self) -> None:
        """Fade target apps to `level` times their volume. Never raises.

        Calling it again while ducked keeps the first captured originals.
        Does nothing (and logs once) when no target process has an audio session.
        """
        if not self._settings.enabled:
            return
        with self._lock:
            if not _run_with_com(self._duck_sessions, "music ducking failed; restoring volume"):
                self._restore_locked()

    def restore(self) -> None:
        """Put every ducked app back to its original volume. Never raises.

        If the sessions can't be listed, the captures are kept so a later
        `restore()` can retry.
        """
        with self._lock:
            self._restore_locked()

    @contextlib.contextmanager
    def ducked(self) -> Iterator[None]:
        """Duck for the duration of the block, and restore even if it raises."""
        try:
            self.duck()
            yield
        finally:
            self.restore()

    def _restore_locked(self) -> None:
        if self._captured:
            message = "could not restore music volume; will retry"
            _run_with_com(self._restore_sessions, message, log=logger.error)

    def _find_sessions_by_app(self) -> dict[str, list[AppSession]]:
        sessions_by_app: dict[str, list[AppSession]] = {}
        for session in find_sessions(self._settings.processes):
            sessions_by_app.setdefault(session.app_id, []).append(session)
        return sessions_by_app

    def _duck_sessions(self) -> None:
        sessions_by_app = self._find_sessions_by_app()
        self._recover_leftovers(sessions_by_app)
        if not sessions_by_app:
            self._log_no_sessions_once()
            return
        plan: FadePlan = []
        for app_id, sessions in sessions_by_app.items():
            levels = [session.volume.GetMasterVolume() for session in sessions]
            if app_id not in self._captured:
                original = max(levels)
                self._captured[app_id] = SavedVolume(original, original * self._settings.level)
            ducked = self._captured[app_id].ducked
            plan.extend((s.volume, now, ducked) for s, now in zip(sessions, levels, strict=True))
        # Save before fading, so a crash mid-fade can still be undone.
        self._save_state()
        fade_volumes(plan, self._settings.fade_ms)

    def _recover_leftovers(self, sessions_by_app: dict[str, list[AppSession]]) -> None:
        present_app_ids = [app_id for app_id in self._leftovers if app_id in sessions_by_app]
        for app_id in present_app_ids:
            saved = self._leftovers[app_id]
            # A session at any other level was changed by the user: leave it.
            still_ducked = [
                session
                for session in sessions_by_app[app_id]
                if abs(session.volume.GetMasterVolume() - saved.ducked) <= VOLUME_MATCH_TOLERANCE
            ]
            if _set_volumes(still_ducked, saved.original):
                del self._leftovers[app_id]
        if present_app_ids:
            self._save_state()

    def _restore_sessions(self) -> None:
        sessions_by_app = self._find_sessions_by_app()
        present = {app: sessions_by_app[app] for app in self._captured if app in sessions_by_app}
        try:
            plan: FadePlan = [
                (session.volume, session.volume.GetMasterVolume(), self._captured[app_id].original)
                for app_id, sessions in present.items()
                for session in sessions
            ]
            fade_volumes(plan, self._settings.fade_ms)
            restored = set(present)
        except Exception:
            logger.warning("fading music back failed; setting volume directly", exc_info=True)
            restored = {
                app_id
                for app_id, sessions in present.items()
                if _set_volumes(sessions, self._captured[app_id].original)
            }
        for app_id, saved in self._captured.items():
            if app_id not in restored:
                self._leftovers[app_id] = saved
        self._captured = {}
        self._save_state()

    def _save_state(self) -> None:
        entries = {**self._leftovers, **self._captured}
        if entries:
            save_volumes(self._state_path, entries)
        else:
            delete_saved_volumes(self._state_path)

    def _log_no_sessions_once(self) -> None:
        if self._has_logged_no_sessions:
            return
        targets = ", ".join(self._settings.processes)
        logger.info("no audio session found for %s; music ducking skipped", targets)
        self._has_logged_no_sessions = True


def _set_volumes(sessions: list[AppSession], level: float) -> bool:
    """Set each session to `level`, carrying on past failures. True if all succeeded."""
    is_complete = True
    for session in sessions:
        try:
            session.volume.SetMasterVolume(level, None)
        except Exception:
            # Keep going so one broken session doesn't leave the others quiet.
            logger.error("could not set volume of %s", session.process_name, exc_info=True)
            is_complete = False
    return is_complete


def _run_with_com(
    action: Callable[[], None], failure_message: str, log: Callable[..., None] = logger.warning
) -> bool:
    """Run `action` with COM initialised. Returns False (after logging) if anything failed.

    Broad on purpose: whatever goes wrong (COM error, process exiting
    mid-fade, a bug), speech must go on and the failure is logged.
    """
    try:
        with com_initialized():
            # The action runs, and any failure is logged, in a helper frame
            # inside this block. That way the traceback, which holds COM
            # pointers, is freed before CoUninitialize runs.
            return _run_logged(action, failure_message, log)
    except OSError:
        log("%s (COM could not be initialised)", failure_message, exc_info=True)
        return False


def _run_logged(action: Callable[[], None], failure_message: str, log: Callable[..., None]) -> bool:
    try:
        action()
    except Exception:
        log(failure_message, exc_info=True)
        return False
    return True
