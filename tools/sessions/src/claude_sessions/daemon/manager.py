"""SessionManager: the daemon's operations on managed sessions (start, send, resume, stop, ...).

Owns every ManagedSession and persists their records after each change. On
load, sessions that were live when the daemon last ran are marked stopped:
their CLI processes are gone, but their Claude session ids can be resumed.
"""

import asyncio
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from signal_hub_notify import Notifier

from claude_sessions.approvals import Approver, validate_permission_mode
from claude_sessions.daemon.session import (
    ManagedSession,
    SessionDeps,
    SessionError,
    SessionRecord,
    SessionState,
    SessionStore,
    session_status,
    session_summary,
)
from claude_sessions.repos import RepoNotFoundError, require_inside_roots
from claude_sessions.sdk import ClientFactory, LaunchSpec

logger = logging.getLogger(__name__)

ID_PREFIX = "s-"
ID_HEX_CHARS = 8
DEFAULT_LAST_N = 3
_LIVE_STATES = frozenset(
    {SessionState.IDLE, SessionState.WORKING, SessionState.AWAITING_PERMISSION}
)

# Finds the folder an existing Claude session ran in (repos.find_transcript_cwd).
FindTranscriptCwd = Callable[[str], Path | None]


@dataclass(frozen=True)
class ManagerDeps:
    """The manager's collaborators; tests pass fakes for all but the store.

    Attributes:
        store: Persists records.
        client_factory: Builds SDK clients.
        approver: Decides tool calls.
        notifier: Sends voice notifications.
        find_transcript_cwd: Looks up where an unmanaged Claude session ran.
        clock: Seconds since the epoch.
        repo_roots: Sessions may only run in folders inside these.
    """

    store: SessionStore
    client_factory: ClientFactory
    approver: Approver
    notifier: Notifier
    find_transcript_cwd: FindTranscriptCwd
    clock: Callable[[], float]
    repo_roots: tuple[Path, ...]


class SessionManager:
    """Every managed session, keyed by managed id."""

    def __init__(self, deps: ManagerDeps) -> None:
        """Create an empty manager; call load() to restore persisted sessions."""
        self._deps = deps
        self._session_deps = SessionDeps(
            deps.client_factory, deps.approver, deps.notifier, self._save, deps.clock
        )
        self._sessions: dict[str, ManagedSession] = {}

    def load(self) -> None:
        """Restore records from the store, marking formerly live sessions stopped."""
        for record in self._deps.store.load():
            if record.state in _LIVE_STATES:
                record.state = SessionState.STOPPED
            self._sessions[record.id] = ManagedSession(record, self._session_deps)
        logger.info("Loaded %d managed sessions", len(self._sessions))
        self._save()

    async def start(
        self, repo: str, prompt: str, model: str | None = None, permission_mode: str = "default"
    ) -> dict[str, Any]:
        """Start a new session in a repo folder. Returns once the CLI is starting.

        Args:
            repo: Absolute path of an existing folder inside a repo root.
            prompt: The first user message.
            model: Model name or alias, or None/"" for the settings' default.
            permission_mode: "default", "acceptEdits" or "plan".

        Returns:
            The new session's status (state "working").

        Raises:
            SessionError: repo isn't an existing local folder inside a repo root.
            PermissionModeError: The mode isn't allowed.
        """
        mode = validate_permission_mode(permission_mode)
        repo_path = self._contained(repo)
        record = self._new_record(repo_path, model or None, mode, str(uuid.uuid4()))
        session = ManagedSession(record, self._session_deps)
        self._sessions[record.id] = session
        spec = LaunchSpec(repo_path, record.model, mode, session_id=record.claude_session_id)
        session.launch(prompt, spec)
        logger.info("Started session %s in %s", record.id, repo_path)
        return session_status(session, 0)

    async def send(self, session_id: str, prompt: str) -> dict[str, Any]:
        """Send a prompt to a live, idle session (see ManagedSession.send for errors)."""
        session = self._get(session_id)
        await session.send(prompt)
        return session_status(session, 0)

    def status(self, session_id: str, last_n: int = DEFAULT_LAST_N) -> dict[str, Any]:
        """A session's status with its newest last_n assistant texts.

        Raises:
            SessionError: No session has this id.
        """
        return session_status(self._get(session_id), last_n)

    async def resume(self, session_ref: str, prompt: str) -> dict[str, Any]:
        """Resume a stopped session, or adopt and resume any existing Claude session.

        Args:
            session_ref: A managed id, or a Claude session id (managed or not).
            prompt: The user message to continue with.

        Returns:
            The session's status (state "working").

        Raises:
            SessionError: The session is already live, no transcript or folder
                for it can be found, or its folder is outside the repo roots.
        """
        session = self._find(session_ref) or await self._adopt(session_ref)
        record = session.record
        # Any live record on this transcript counts: two CLIs resuming one transcript conflict.
        live = self._live_on(record.claude_session_id)
        if live is not None:
            raise SessionError(f"Session {live.record.id} is already running; use send instead.")
        repo_path = self._contained(record.repo_path)
        spec = LaunchSpec(
            repo_path, record.model, record.permission_mode, resume=record.claude_session_id
        )
        session.launch(prompt, spec)
        logger.info("Resumed Claude session %s as %s", record.claude_session_id, record.id)
        return session_status(session, 0)

    async def stop(self, session_id: str) -> dict[str, Any]:
        """Stop a session's CLI; it stays listed and can be resumed.

        Raises:
            SessionError: No session has this id.
        """
        session = self._get(session_id)
        await session.stop()
        return session_status(session, 0)

    def list(self) -> list[dict[str, Any]]:
        """Summaries of every managed session, most recently updated first."""
        sessions = sorted(self._sessions.values(), key=lambda s: s.record.updated_at, reverse=True)
        return [session_summary(session) for session in sessions]

    async def stop_all(self) -> None:
        """Stop every live session (daemon shutdown)."""
        live = [session for session in self._sessions.values() if session.is_live]
        await asyncio.gather(*(session.stop() for session in live))

    def _get(self, session_id: str) -> ManagedSession:
        """The session with this managed id, or SessionError."""
        session = self._sessions.get(session_id)
        if session is None:
            raise SessionError(
                f"No managed session {session_id!r}; list_managed_sessions shows them."
            )
        return session

    def _find(self, session_ref: str) -> ManagedSession | None:
        """A session by managed id, else the newest one with this Claude session id."""
        if session_ref in self._sessions:
            return self._sessions[session_ref]
        matches = [s for s in self._sessions.values() if s.record.claude_session_id == session_ref]
        return max(matches, key=lambda s: s.record.updated_at, default=None)

    def _live_on(self, claude_session_id: str) -> ManagedSession | None:
        """A live session running this Claude session id, or None."""
        return next(
            (
                s
                for s in self._sessions.values()
                if s.is_live and s.record.claude_session_id == claude_session_id
            ),
            None,
        )

    async def _adopt(self, claude_session_id: str) -> ManagedSession:
        """Create a managed record for an existing, unmanaged Claude session."""
        cwd = await asyncio.to_thread(self._deps.find_transcript_cwd, claude_session_id)
        if cwd is None:
            raise SessionError(
                f"No Claude session {claude_session_id!r} found in ~/.claude/projects; "
                "list_sessions shows the existing ones."
            )
        # A concurrent resume of the same id may have adopted it while we looked.
        existing = self._find(claude_session_id)
        if existing is not None:
            return existing
        # A transcript's cwd is data from disk; it gets the same check as a caller's path.
        record = self._new_record(self._contained(cwd), None, "default", claude_session_id)
        session = ManagedSession(record, self._session_deps)
        self._sessions[record.id] = session
        return session

    def _new_record(
        self, repo_path: Path, model: str | None, mode: str, claude_session_id: str
    ) -> SessionRecord:
        """A fresh record in the stopped state (launch() moves it on)."""
        now = self._deps.clock()
        return SessionRecord(
            id=f"{ID_PREFIX}{uuid.uuid4().hex[:ID_HEX_CHARS]}",
            repo_name=repo_path.name or str(repo_path),
            repo_path=str(repo_path),
            claude_session_id=claude_session_id,
            model=model,
            permission_mode=mode,
            state=SessionState.STOPPED,
            created_at=now,
            updated_at=now,
        )

    def _contained(self, folder: str | Path) -> Path:
        """The folder fully resolved, or SessionError unless it is a local folder inside a root."""
        try:
            return require_inside_roots(folder, self._deps.repo_roots)
        except RepoNotFoundError as error:
            raise SessionError(str(error)) from error

    def _save(self) -> None:
        """Persist every record; a failed write is logged and retried on the next change."""
        try:
            self._deps.store.save(session.record for session in self._sessions.values())
        except OSError:
            logger.exception("Couldn't save the sessions file; sessions keep running in memory")
