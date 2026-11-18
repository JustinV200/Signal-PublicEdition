"""DaemonClient: the blocking stdlib client the MCP server and CLI use to reach the daemon.

It reads daemon.json for the port and token, sends one POST per call and
returns the JSON reply. start, approve and ask wait for an agent turn on the
daemon side (drafting or revising a plan, answering a question), so they get
AGENT_TURN_TIMEOUT_S; the rest get QUICK_TIMEOUT_S. Every failure, including
"the daemon isn't running", is a DaemonError with a message for a person.
"""

import http.client
import json
from pathlib import Path
from typing import Any

from analysis_chamber.daemon.state_file import LOOPBACK_HOST, STATE_FILE_NAME, read_state

QUICK_TIMEOUT_S = 30.0
# Agent turns are uncapped by design (spec 6); an hour covers a long plan draft.
AGENT_TURN_TIMEOUT_S = 3600.0
NOT_RUNNING_HINT = "start it with `analysis-chamber serve`"


class DaemonError(Exception):
    """The daemon isn't running, refused the request, or the call failed."""


class DaemonNotRunningError(DaemonError):
    """No daemon.json, or nothing listens on its port: the daemon isn't running."""


class DaemonClient:
    """Calls the daemon's routes. Each method returns the reply dict."""

    def __init__(self, state_dir: Path) -> None:
        """Args:
        state_dir: config.state_dir, where the daemon writes daemon.json.
        """
        self._state_dir = state_dir

    def start(self, question: str) -> dict[str, Any]:
        """Start a run; returns {run_id, plan}. Waits for the plan draft."""
        return self._post("/start", {"question": question}, AGENT_TURN_TIMEOUT_S)

    def approve(
        self, run_id: str, edits: str | None = None, personal: bool | None = None
    ) -> dict[str, Any]:
        """Revise (edits) or approve (personal set) a plan; returns {run_id, status, ...}."""
        body = {"run_id": run_id, "edits": edits, "personal": personal}
        return self._post("/approve", body, AGENT_TURN_TIMEOUT_S)

    def status(self, run_id: str) -> dict[str, Any]:
        """One run's status view."""
        return self._post("/status", {"run_id": run_id}, QUICK_TIMEOUT_S)

    def list(self, timeout_s: float = QUICK_TIMEOUT_S) -> dict[str, Any]:
        """{runs: [...]} for every run; `timeout_s` caps the wait (the health check's is short)."""
        return self._post("/list", {}, timeout_s)

    def ask(self, run_id: str, question: str) -> dict[str, Any]:
        """Ask the run's Q&A agent; returns {run_id, answer}."""
        return self._post("/ask", {"run_id": run_id, "question": question}, AGENT_TURN_TIMEOUT_S)

    def cancel(self, run_id: str) -> dict[str, Any]:
        """Cancel a run; returns {run_id, status}."""
        return self._post("/cancel", {"run_id": run_id}, QUICK_TIMEOUT_S)

    def _post(self, path: str, body: dict[str, Any], timeout_s: float) -> dict[str, Any]:
        """Send one request and return its JSON reply.

        Raises:
            DaemonError: Not running (DaemonNotRunningError), connection dropped, timeout,
                or an error reply.
        """
        state = read_state(self._state_dir)
        if state is None:
            raise DaemonNotRunningError(
                f"the analysis-chamber daemon isn't running (no {STATE_FILE_NAME}); "
                + NOT_RUNNING_HINT
            )
        connection = http.client.HTTPConnection(LOOPBACK_HOST, state.port, timeout=timeout_s)
        headers = {"Authorization": f"Bearer {state.token}", "Content-Type": "application/json"}
        try:
            connection.request("POST", path, json.dumps(body).encode("utf-8"), headers)
            response = connection.getresponse()
            raw = response.read()
        except ConnectionRefusedError as error:
            raise DaemonNotRunningError(
                f"the analysis-chamber daemon isn't running; {NOT_RUNNING_HINT}"
            ) from error
        except http.client.RemoteDisconnected as error:
            raise DaemonError(
                "the daemon closed the connection (stale daemon.json token?)"
            ) from error
        except (OSError, http.client.HTTPException) as error:
            raise DaemonError(f"daemon call {path} failed: {error}") from error
        finally:
            connection.close()
        return _parse_reply(path, response.status, raw)


def _parse_reply(path: str, status: int, raw: bytes) -> dict[str, Any]:
    try:
        reply = json.loads(raw)
    except ValueError as error:
        raise DaemonError(f"daemon call {path} returned non-JSON (HTTP {status})") from error
    if status != http.client.OK or not isinstance(reply, dict):
        message = reply.get("error") if isinstance(reply, dict) else None
        raise DaemonError(message or f"daemon call {path} failed (HTTP {status})")
    return reply
