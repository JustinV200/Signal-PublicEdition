"""The report phase: the lead writes the report and writeup; the format and top finding are parsed.

Leak rule (spec 7.5): only a run the user flagged non-personal (personal is False)
may use the artifact format. Anything else that says artifact is recorded as
html, which is the same report.html file, so it is never offered for publishing.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from analysis_chamber.phases.deps import PhaseAgents, PhaseError, StepCall
from analysis_chamber.phases.markers import find_marker
from analysis_chamber.phases.prompts import render
from analysis_chamber.phases.steps import SOURCE_FIELDS, merge_sources
from analysis_chamber.phases.turns import lead_turn

if TYPE_CHECKING:
    from analysis_chamber.agents import RunContext

ARTIFACT = "artifact"
FALLBACK_FORMAT = "html"
REPORT_FILES = {
    "html": "report.html",
    "md": "report.md",
    "ipynb": "report.ipynb",
    ARTIFACT: "report.html",
}
# Every output a run can leave, by manifest.outputs name.
OUTPUT_FILES = {
    "plan": "plan.md",
    "sources": "sources.json",
    "results": "results.md",
    "critique": "critique.md",
    "writeup": "writeup.md",
    "qa": "qa.md",
}
NO_TOP_FINDING = "see the writeup"


@dataclass(frozen=True)
class ReportResult:
    """What the done notification needs."""

    report_path: Path
    top_finding: str


async def run_report(ctx: RunContext, agents: PhaseAgents, call: StepCall) -> ReportResult:
    """Lead writes report.* and writeup.md; sets report_format and outputs.

    Raises:
        PhaseError: The lead turn failed, or the report or writeup is missing.
    """
    merge_sources(ctx)  # sources.json may have grown since collect
    reply = await lead_turn(ctx, agents, call.intro + _report_prompt(ctx))
    report_format = _pick_format(ctx, find_marker(reply, "REPORT_FORMAT"))
    report_path = ctx.run_dir / REPORT_FILES[report_format]
    if not report_path.is_file() or not (ctx.run_dir / OUTPUT_FILES["writeup"]).is_file():
        raise PhaseError(f"report phase didn't leave {report_path.name} and writeup.md")
    ctx.manifest.report_format = report_format
    ctx.manifest.outputs = existing_outputs(ctx.run_dir, report_format)
    return ReportResult(report_path, find_marker(reply, "TOP_FINDING") or NO_TOP_FINDING)


def existing_outputs(run_dir: Path, report_format: str | None) -> dict[str, str]:
    """manifest.outputs for the output files that exist now (also used on failure)."""
    names = dict(OUTPUT_FILES)
    if report_format in REPORT_FILES:
        names["report"] = REPORT_FILES[report_format]
    return {name: file for name, file in names.items() if (run_dir / file).is_file()}


def _report_prompt(ctx: RunContext) -> str:
    """The report prompt, offering artifact only for a non-personal run."""
    allowed = ctx.manifest.personal is False
    installs = ", ".join(
        f"{item.get('package')} {item.get('version')}" for item in ctx.manifest.installs
    )
    return render(
        "write_report",
        playbook=ctx.config.playbook_path,
        formats="html, md, ipynb or artifact" if allowed else "html, md or ipynb",
        artifact_note=(
            "Artifact means report.html written for a claude.ai page; the starting chat "
            "publishes it, never you."
            if allowed
            else "This is a personal run: never the artifact format."
        ),
        installs=installs or "none",
        sources=_sources_lines(ctx) or "(none recorded)",
    )


def _sources_lines(ctx: RunContext) -> str:
    """manifest.sources as one `name | url | status | note | fetched_at` line each."""
    return "\n".join(
        "- " + " | ".join(str(source.get(field) or "") for field in SOURCE_FIELDS)
        for source in ctx.manifest.sources
    )


def _pick_format(ctx: RunContext, stated: str | None) -> str:
    """The format to record: the stated one if valid and allowed, else what's on disk."""
    stated = (stated or "").strip().lower()
    if stated == ARTIFACT and ctx.manifest.personal is not False:
        return FALLBACK_FORMAT
    if stated in REPORT_FILES:
        return stated
    for report_format, file in REPORT_FILES.items():
        if (ctx.run_dir / file).is_file():
            return report_format
    raise PhaseError("report phase didn't write report.html, report.md or report.ipynb")
