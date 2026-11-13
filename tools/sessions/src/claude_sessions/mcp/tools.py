"""SessionTools: the behaviour behind each sessions MCP tool.

Repo and transcript listings run here, in the MCP process (in a worker
thread, since they read the disk); the repo scan is reused for a minute, so
list_repos followed by start_session walks the disk once. Results are compact
JSON without null fields, to keep the calling model's context small.
Everything about managed sessions goes to
the daemon, which is started in the background on first use. Expected
failures become ToolError, so the calling model gets a plain-text error
result it can act on.
"""

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any, Literal

from mcp.server.mcpserver.exceptions import ToolError

from claude_sessions.approvals import PermissionModeError
from claude_sessions.config import Settings
from claude_sessions.ipc import (
    DaemonNotRunningError,
    DaemonRequestError,
    DaemonStartError,
    ProtocolError,
)
from claude_sessions.repos import (
    Repo,
    RepoNotFoundError,
    find_repos,
    list_transcripts,
    looks_like_path,
    resolve_repo,
)
from claude_sessions.text import format_local_time_ms

# (op, args) -> result. The real one starts the daemon if needed (ipc.call_running_daemon).
DaemonCall = Callable[[str, dict[str, Any]], Awaitable[Any]]
PermissionMode = Literal["default", "acceptEdits", "plan"]

# The newest reply is usually all a caller needs; older ones cost up to 8000 chars each.
DEFAULT_LAST_N = 1
# shortcut: a repo created within this window isn't found by name until it passes.
REPO_CACHE_TTL_S = 60.0
# list_managed_sessions shows this many of the newest sessions, plus any older live ones.
MAX_LISTED_SESSIONS = 10
_EXPECTED_ERRORS = (
    RepoNotFoundError,
    PermissionModeError,
    ProtocolError,
    DaemonRequestError,
    DaemonNotRunningError,
    DaemonStartError,
    TimeoutError,
    OSError,
)


class SessionTools:
    """Backs every sessions MCP tool. Tool parameters are named as the tools' schemas show them."""

    def __init__(self, settings: Settings, call_daemon: DaemonCall) -> None:
        """Configure the tools.

        Args:
            settings: Repo roots and search depth.
            call_daemon: Sends one request to the (running) daemon; tests pass a fake.
        """
        self._settings = settings
        self._call_daemon = call_daemon
        # (monotonic time of the scan, its repos); see _repos.
        self._repo_cache: tuple[float, list[Repo]] | None = None

    async def list_repos(self, query: str = "") -> str:
        """See descriptions.LIST_REPOS."""
        repos = await self._repos()
        wanted = query.strip().lower()
        matching = [r for r in repos if wanted in r.name.lower() or wanted in str(r.path).lower()]
        return _json([{"name": r.name, "path": str(r.path), "is_git": r.is_git} for r in matching])

    async def list_sessions(self, repo: str = "") -> str:
        """See descriptions.LIST_SESSIONS."""
        repo_path = await self._locate(repo) if repo.strip() else None
        transcripts = await _guarded(asyncio.to_thread(list_transcripts, repo_path))
        rows = []
        for transcript in transcripts:
            row = asdict(transcript)
            row["last_modified"] = format_local_time_ms(row.pop("last_modified_ms"))
            if repo_path is not None:
                del row["cwd"]  # Every row has the repo the caller asked for.
            rows.append(row)
        return _json(rows)

    async def start_session(
        self, repo: str, prompt: str, model: str = "", permission_mode: PermissionMode = "default"
    ) -> str:
        """See descriptions.START_SESSION."""
        repo_path = await self._locate(repo)
        args: dict[str, Any] = {
            "repo": str(repo_path),
            "prompt": prompt,
            "permission_mode": permission_mode,
        }
        if model.strip():
            args["model"] = model.strip()
        return await self._daemon("start", args)

    # `id` shadows the builtin, but it is the argument name the tool schema promises.
    async def send_to_session(self, id: str, prompt: str) -> str:
        """See descriptions.SEND_TO_SESSION."""
        return await self._daemon("send", {"id": id, "prompt": prompt})

    async def session_status(self, id: str, last_n: int = DEFAULT_LAST_N) -> str:
        """See descriptions.SESSION_STATUS."""
        return await self._daemon("status", {"id": id, "last_n": last_n})

    async def resume_session(self, claude_session_id: str, prompt: str) -> str:
        """See descriptions.RESUME_SESSION."""
        return await self._daemon("resume", {"session": claude_session_id, "prompt": prompt})

    async def stop_session(self, id: str) -> str:
        """See descriptions.STOP_SESSION."""
        return await self._daemon("stop", {"id": id})

    async def list_managed_sessions(self) -> str:
        """See descriptions.LIST_MANAGED_SESSIONS."""
        sessions = await _guarded(self._call_daemon("list", {}))
        # The daemon lists newest first; old stopped sessions are rarely wanted.
        shown = [s for i, s in enumerate(sessions) if s["is_live"] or i < MAX_LISTED_SESSIONS]
        return _json(shown)

    async def _repos(self) -> list[Repo]:
        """The repos under the roots, rescanned (in a worker thread) once REPO_CACHE_TTL_S old."""
        now = time.monotonic()
        if self._repo_cache is None or now - self._repo_cache[0] > REPO_CACHE_TTL_S:
            settings = self._settings
            repos = await _guarded(
                asyncio.to_thread(find_repos, settings.repo_roots, settings.max_depth)
            )
            self._repo_cache = (now, repos)
        return self._repo_cache[1]

    async def _locate(self, repo: str) -> Path:
        """Resolve a repo path or name; only a name needs the (cached) repo scan."""
        repos = () if looks_like_path(repo.strip()) else await self._repos()
        roots = self._settings.repo_roots
        return await _guarded(asyncio.to_thread(resolve_repo, repo, repos, roots))

    async def _daemon(self, op: str, args: dict[str, Any]) -> str:
        """Run one daemon op and return its result as JSON text."""
        return _json(await _guarded(self._call_daemon(op, args)))


async def _guarded[T](work: Awaitable[T]) -> T:
    """Await work, turning expected failures into ToolError with their message."""
    try:
        return await work
    except _EXPECTED_ERRORS as error:
        raise ToolError(str(error) or type(error).__name__) from error


def _json(data: Any) -> str:
    """Tool results are compact JSON with null fields dropped, to spare the model's context."""
    return json.dumps(_without_nulls(data), separators=(",", ":"), ensure_ascii=False)


def _without_nulls(data: Any) -> Any:
    """data with every None-valued dict key removed, at any depth."""
    if isinstance(data, dict):
        return {key: _without_nulls(value) for key, value in data.items() if value is not None}
    if isinstance(data, list):
        return [_without_nulls(item) for item in data]
    return data
