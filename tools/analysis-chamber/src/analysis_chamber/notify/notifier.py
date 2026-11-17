"""notifier: the chamber's three notification channels (spec 7.8).

Part of analysis_chamber.notify. Progress goes to the console Tasks page; done
adds a brief entry and a voice ping; failed or cancelled runs only close the
console task. A failing channel is logged with context and never stops the
others, so a failed ping can't fail a run. Runs not confirmed non-personal
never put the finding in the brief or the voice note.
"""

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from signal_brief import (
    BriefLogError,
    BriefPaths,
    NewEntry,
    append_entry,
    local_now,
    strip_forbidden,
)
from signal_hub_notify import HubNote
from signal_hub_notify import Notifier as HubNotifier

from analysis_chamber.config import ChamberConfig
from analysis_chamber.notify.console_tasks import (
    RunCommand,
    done_args,
    remove_args,
    run_command,
    set_args,
)
from analysis_chamber.runs import Manifest, Status

log = logging.getLogger(__name__)

HUB_HOST = "127.0.0.1"
HUB_PORT = 8765
SOURCE = "chamber"
MAX_TITLE_CHARS = 140  # brief limits
MAX_DETAIL_CHARS = 600
MAX_VOICE_FINDING_CHARS = 300  # keeps the spoken note short

# Appends one brief entry; tests pass a fake. (entry, now) -> anything.
AppendBrief = Callable[[NewEntry, datetime], object]


class Notifier:
    """Sends a run's progress, done and closed notices."""

    def __init__(
        self,
        config: ChamberConfig,
        run: RunCommand = run_command,
        append_brief: AppendBrief | None = None,
        hub: HubNotifier | None = None,
    ) -> None:
        """Wire the channels; the defaults are the real ones.

        Args:
            config: Chamber config (repo_root is where the console CLI runs).
            run: Runs the console CLI argv from repo_root; tests pass a fake.
            append_brief: Writes a brief entry; default is signal_brief's append_entry.
            hub: Voice hub client with `async deliver(HubNote)`; default is the real hub.
        """
        self._root = config.repo_root
        self._run = run
        self._append = append_brief or _bind_append(BriefPaths())
        token_file = config.repo_root / "tools" / "audiohub" / ".cache" / "ipc-token"
        self._hub = hub or HubNotifier(HUB_HOST, HUB_PORT, token_file)
        self._last_sent: dict[str, tuple[str, int, str]] = {}

    async def progress(self, manifest: Manifest) -> None:
        """Show the run on the Tasks page; skipped when phase, percent and status are unchanged."""
        state = (manifest.phase.value, manifest.percent, manifest.status.value)
        if self._last_sent.get(manifest.id) == state:
            return
        status = "queued" if manifest.status is Status.QUEUED else "building"
        argv = set_args(manifest, status)
        if await self._console(argv, manifest.id, "progress"):
            self._last_sent[manifest.id] = state

    async def done(self, manifest: Manifest, top_finding: str, report_path: Path) -> None:
        """Brief entry, voice ping and console close for a finished run.

        The finding is included only when `manifest.personal is False`; None (not yet
        answered) counts as personal.
        """
        finding = top_finding if manifest.personal is False else ""
        await self._brief(manifest, finding, report_path)
        await self._voice(manifest, finding)
        await self._console(done_args(manifest.id), manifest.id, "done")
        self._last_sent.pop(manifest.id, None)

    async def closed(self, manifest: Manifest) -> None:
        """Remove the console task of a failed or cancelled run; no brief or voice."""
        await self._console(remove_args(manifest.id), manifest.id, "closed")
        self._last_sent.pop(manifest.id, None)

    async def _console(self, argv: list[str], run_id: str, what: str) -> bool:
        """Run one console command off the event loop; True if it worked."""
        try:
            await asyncio.to_thread(self._run, argv, self._root)
        except Exception as error:  # noqa: BLE001 - logged here; must never fail a run
            log.warning("chamber %s: console %s failed: %s", run_id, what, error)
            return False
        return True

    async def _brief(self, manifest: Manifest, finding: str, report_path: Path) -> None:
        """Log the done entry (the finding only when allowed)."""
        entry = NewEntry(
            kind="done",
            title=_clean(_done_text(manifest.id, finding, MAX_TITLE_CHARS), MAX_TITLE_CHARS),
            key=f"chamber:{manifest.id.lower()}",
            detail=_clean(f"Report: {report_path}", MAX_DETAIL_CHARS),
            untrusted=bool(finding),  # the finding is built from outside data
            source=SOURCE,
        )
        try:
            await asyncio.to_thread(self._append, entry, local_now())
        except (BriefLogError, ValueError) as error:
            log.warning("chamber %s: brief entry failed: %s", manifest.id, error)

    async def _voice(self, manifest: Manifest, finding: str) -> None:
        """Speak the done note. The hub client reports its own failures; this guards the rest."""
        note = HubNote(SOURCE, _done_text(manifest.id, finding, MAX_VOICE_FINDING_CHARS))
        try:
            await self._hub.deliver(note)
        except Exception as error:  # noqa: BLE001 - a failed ping must never fail a run
            log.warning("chamber %s: voice ping failed: %s", manifest.id, error)


def _done_text(run_id: str, finding: str, max_finding_chars: int) -> str:
    """The done sentence; without a finding it points at the run folder instead."""
    if not finding:
        return f"Personal run {run_id} done, see the run folder"
    return f"Chamber run {run_id} done, top finding: {finding[:max_finding_chars]}"


def _clean(text: str, max_chars: int) -> str:
    """One line, forbidden characters removed, cut to the brief's limit."""
    return strip_forbidden(" ".join(text.split()))[:max_chars]


def _bind_append(paths: BriefPaths) -> AppendBrief:
    """append_entry bound to the real brief paths."""
    return lambda entry, now: append_entry(paths, entry, now)
