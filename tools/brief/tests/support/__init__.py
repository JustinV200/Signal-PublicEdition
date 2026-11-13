"""Shared test fakes: temp state paths, fixed times, hook runs and transcript lines."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from signal_brief import BriefPaths, NewEntry, append_entry

from brief_tool.hooks.prompt import HookRun, handle_prompt

PRESENT_IDLE_MS = 800  # the owner pressed Enter just now


def make_paths(tmp_path: Path) -> BriefPaths:
    """State in tmp_path/.state, and a sleepmode file that doesn't exist (awake)."""
    return BriefPaths(tmp_path / ".state", tmp_path / "sleep-state.json")


def at(day: int, hour: int, minute: int = 0) -> datetime:
    """A local, aware time in October 2026 (the 20th is a Tuesday)."""
    return datetime(2026, 10, day, hour, minute).astimezone()


def log(paths: BriefPaths, kind: str, title: str, now: datetime) -> None:
    """Append one entry (decisions get an undo)."""
    undo = {"tool": "Bash", "args": {"command": "git revert 1a2b3c4"}}
    append_entry(paths, NewEntry(kind, title, undo=undo if kind == "decision" else None), now)


def run_hook(
    paths: BriefPaths,
    transcript: Path,
    now: datetime,
    session_id: str = "s1",
    **overrides: Any,
) -> tuple[str | None, str]:
    """handle_prompt for a plain prompt; overrides set idle_ms, environ or event fields."""
    event = {"session_id": session_id, "transcript_path": str(transcript), "prompt": "hi"}
    event |= overrides.get("event", {})
    run = HookRun(
        paths, now, overrides.get("idle_ms", PRESENT_IDLE_MS), overrides.get("environ", {})
    )
    return handle_prompt(event, run)


class Transcript:
    """A fake Claude Code transcript, one JSON record per line."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.write_text("", encoding="utf-8")

    def _add(self, record: dict[str, Any]) -> None:
        with self.path.open("a", encoding="utf-8") as transcript:
            transcript.write(json.dumps({"isSidechain": False} | record) + "\n")

    def hook_context(
        self,
        text: str,
        hook_name: str = "UserPromptSubmit",
        kind: str = "hook_additional_context",
    ) -> None:
        """What Claude Code writes for a UserPromptSubmit hook's additionalContext.

        Other hook names or attachment kinds make the look-alikes that mustn't count.
        """
        attachment = {"type": kind, "content": [text]}
        attachment |= {"hookName": hook_name, "hookEvent": "UserPromptSubmit"}
        self._add({"type": "attachment", "attachment": attachment})

    def prompt(self, text: str) -> None:
        self._add({"type": "user", "message": {"role": "user", "content": text}})

    def reply(self, text: str) -> None:
        content = [{"type": "text", "text": text}]
        self._add({"type": "assistant", "message": {"role": "assistant", "content": content}})

    def tool_call(self, call_id: str, name: str, result: str) -> None:
        use = {"type": "tool_use", "id": call_id, "name": name, "input": {}}
        self._add({"type": "assistant", "message": {"role": "assistant", "content": [use]}})
        answer = {"type": "tool_result", "tool_use_id": call_id}
        answer["content"] = [{"type": "text", "text": result}]
        self._add({"type": "user", "message": {"role": "user", "content": [answer]}})
