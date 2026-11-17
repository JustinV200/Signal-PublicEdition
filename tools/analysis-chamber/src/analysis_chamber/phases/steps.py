"""The collect and analyse phases: one lead turn each, plus merging sources.json.

The chamber tools record their own sources straight into manifest.sources. For
the rest (Signal reads, files the user named) the lead keeps sources.json in the
run folder, which is merged in after collect and again before the report.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from analysis_chamber.phases.deps import PhaseAgents, StepCall
from analysis_chamber.phases.prompts import render
from analysis_chamber.phases.turns import lead_turn

if TYPE_CHECKING:
    from analysis_chamber.agents import RunContext

log = logging.getLogger(__name__)

SOURCES_FILE = "sources.json"
SOURCE_FIELDS = ("name", "url", "status", "note", "fetched_at")


async def run_collect(ctx: RunContext, agents: PhaseAgents, call: StepCall) -> None:
    """Lead gathers the data per the approved plan; sources.json is merged into the manifest.

    Raises:
        PhaseError: The lead turn failed.
    """
    await lead_turn(ctx, agents, call.intro + render("collect"))
    merge_sources(ctx)


async def run_analyse(ctx: RunContext, agents: PhaseAgents, call: StepCall) -> None:
    """Lead analyses the collected data into code/, figures/, models/ and results.md.

    Raises:
        PhaseError: The lead turn failed.
    """
    await lead_turn(ctx, agents, call.intro + render("analyse"))


def merge_sources(ctx: RunContext) -> None:
    """Add the lead's sources.json entries to manifest.sources, in place.

    The chamber tools append their own records to manifest.sources as they run
    (agents binds on_source to that list), so it's extended, never replaced. The
    lead logs every source it relies on, repeats included, so an entry whose url
    (or name, when it has no url) is already listed updates that record instead:
    its note (the lead's grade and data date) when non-empty, and its name if blank.
    """
    by_key = {_source_key(source): source for source in ctx.manifest.sources}
    for entry in _read_sources_file(ctx):
        known = by_key.get(_source_key(entry))
        if known is None:
            by_key[_source_key(entry)] = entry
            ctx.manifest.sources.append(entry)
            continue
        if entry["note"]:
            known["note"] = entry["note"]
        if not known.get("name"):
            known["name"] = entry["name"]


def _source_key(source: dict[str, Any]) -> str:
    """What makes two source records the same source."""
    return str(source.get("url") or source.get("name") or "")


def _read_sources_file(ctx: RunContext) -> list[dict[str, Any]]:
    """The lead's sources.json as source records ([] if missing or malformed).

    It's agent-written (read as utf-8-sig, since PowerShell writes a BOM), so it's
    validated: entries that aren't objects are dropped and every field becomes a
    string. A bad file logs a warning rather than failing a long run.
    """
    path = ctx.run_dir / SOURCES_FILE
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as error:
        log.warning("run %s: can't read %s: %s", ctx.manifest.id, path, error)
        return []
    if not isinstance(data, list):
        log.warning("run %s: %s is not a JSON list", ctx.manifest.id, path)
        return []
    return [
        {field: str(entry.get(field) or "") for field in SOURCE_FIELDS}
        for entry in data
        if isinstance(entry, dict)
    ]
