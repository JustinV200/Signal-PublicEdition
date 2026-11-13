"""Claude Code UserPromptSubmit hook: away rules, session acks and the brief injection.

Run as `<tools/brief venv>/Scripts/python.exe -I -m brief_tool.hooks.prompt`; -I
keeps the cwd off sys.path, so a stray json.py there can't shadow the stdlib. Per
prompt:
1. If the owner is away or asleep, add the away rules (every prompt, managed or not).
2. Stop if this is a managed session, a subagent's prompt, a tag-wrapped turn (it
   starts with "<" once any leading IDE file/selection context is dropped: peer
   messages, task notifications) or the owner's last input came over 5 s before the hook:
   then the owner didn't just press Enter on it.
3. Ack this session's unseen deliveries by what Claude's replies relayed.
4. On "full", inject the brief's refs and titles once per session and due brief
   (again an hour on while nothing acked it), logged as a delivery; on
   "one_liner", inject the one-liner. A due brief never expires: it stays due
   until a delivery of it is acked; after that, the 6 h gap one-liner comes from
   on_interaction's own "one_liner" offer.
It always exits 0. hook.log gets the session id, decision and timings, never the
prompt text.
"""

import json
import os
import re
import sys
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from signal_brief import BriefPaths, away_status, idle_ms, local_now

from brief_tool.hooks.hook_log import log_hook_run
from brief_tool.hooks.injection import brief_injection
from brief_tool.hooks.session_acks import ack_session_deliveries
from brief_tool.surface import MANAGED, brief_surface
from brief_tool.wording import away_rules

# Only input this close before the hook is the Enter the owner pressed to send the prompt.
INPUT_WINDOW_MS = 5000
HOOK_LOG_NAME = "hook.log"
# Context the VS Code extension puts in front of the owner's own typed prompt.
IDE_CONTEXT = re.compile(r"^\s*(?:<(ide_opened_file|ide_selection)>.*?</\1>\s*)+", re.DOTALL)


@dataclass(frozen=True)
class HookRun:
    """One prompt's surroundings: the state, the time, input idleness and the env."""

    paths: BriefPaths
    now: datetime
    idle_ms: int | None  # None: GetLastInputInfo failed, so the owner counts as not present
    environ: Mapping[str, str]


def handle_prompt(event: dict[str, Any], run: HookRun) -> tuple[str | None, str]:
    """Steps 1-4 for one prompt.

    Returns:
        The additionalContext to add (None for nothing) and the decision for the log.

    Raises:
        BriefLogError: The away state couldn't be read (steps 3-4 failures are caught
            and logged, so the away rules still go out).
    """
    away = away_status(run.paths, run.now)
    parts = [away_rules(away)] if away.is_away else []
    skip = skip_reason(event, run)
    if skip:
        decision = f"skip:{skip}"
    else:
        try:
            decision, text = _ack_and_offer(event, run)
        except Exception as error:  # noqa: BLE001 - logged; the away rules must still go out
            decision, text = f"error:{type(error).__name__}", None
        parts += [text] if text else []
    return ("\n\n".join(parts) or None), decision


def skip_reason(event: dict[str, Any], run: HookRun) -> str | None:
    """Why this prompt can't be the owner's own just now (step 2), or None if it is."""
    prompt = event.get("prompt")
    if brief_surface(run.environ) == MANAGED:
        return "managed"
    if event.get("agent_id"):
        return "agent"
    if not isinstance(prompt, str):
        return "no_prompt"
    if IDE_CONTEXT.sub("", prompt).lstrip().startswith("<"):
        return "tagged"
    if not event.get("session_id"):
        return "no_session"
    if run.idle_ms is None or run.idle_ms > INPUT_WINDOW_MS:
        return "idle"
    return None


def _ack_and_offer(event: dict[str, Any], run: HookRun) -> tuple[str, str | None]:
    session_id = str(event["session_id"])
    transcript = event.get("transcript_path")
    path = Path(transcript) if isinstance(transcript, str) and transcript else None
    acked: int | str
    try:
        acked = ack_session_deliveries(run.paths, session_id, path, run.now)
    except OSError as error:
        # An unreadable transcript only costs this prompt's acks (logged), not the brief.
        acked = f"error:{type(error).__name__}"
    decision, text = brief_injection(run.paths, session_id, run.now)
    return f"{decision},acked={acked}", text


def main() -> int:
    """Hook entry point. Always returns 0."""
    started = time.perf_counter()
    paths, session_id, decision = BriefPaths(), "", "error"
    try:
        idle = _idle_or_none()
        event = json.loads(sys.stdin.buffer.read().decode("utf-8", errors="replace"))
        if not isinstance(event, dict):
            raise ValueError("hook input isn't a JSON object")
        session_id = str(event.get("session_id") or "")
        text, decision = handle_prompt(event, HookRun(paths, local_now(), idle, os.environ))
        if text:
            output = {"hookEventName": "UserPromptSubmit", "additionalContext": text}
            sys.stdout.write(json.dumps({"hookSpecificOutput": output}))
    except Exception as error:  # noqa: BLE001 - a hook must never fail the prompt
        decision = f"error:{type(error).__name__}"  # the type only: messages may quote input
    took_ms = round((time.perf_counter() - started) * 1000)
    log_hook_run(
        paths.state_dir / HOOK_LOG_NAME,
        {"session": session_id, "decision": decision, "ms": took_ms},
    )
    return 0


def _idle_or_none() -> int | None:
    try:
        return idle_ms()
    except OSError:
        return None


if __name__ == "__main__":
    sys.exit(main())
