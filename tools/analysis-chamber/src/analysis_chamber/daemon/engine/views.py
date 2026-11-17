"""JSON views of a run for /status and /list (spec 21 Q4 fields, plus the publish offer)."""

from typing import Any

from analysis_chamber.daemon.engine.run_state import RunState
from analysis_chamber.guard import can_publish
from analysis_chamber.runs import Manifest, Status

HTML_SUFFIX = ".html"


def status_view(run: RunState) -> dict[str, Any]:
    """The full status of one run.

    Output paths are absolute. `publish` ({html_path}) appears only for a done run
    the leak guard allows to publish (non-personal, artifact format) that has an
    HTML output; the starting chat then publishes it.
    """
    manifest = run.manifest
    view = brief_view(manifest) | {
        "created_at": manifest.created_at,
        "sources_count": len(manifest.sources),
        "last_error": manifest.last_error,
        "outputs": {name: str(run.run_dir / rel) for name, rel in manifest.outputs.items()},
        "report_format": manifest.report_format,
        "run_dir": str(run.run_dir),
    }
    html_path = _publishable_html(run)
    if html_path is not None:
        view["publish"] = {"html_path": html_path}
    return view


def brief_view(manifest: Manifest) -> dict[str, Any]:
    """One /list row: what the run is and where it's at."""
    return {
        "run_id": manifest.id,
        "question": manifest.question,
        "phase": manifest.phase.value,
        "status": manifest.status.value,
        "percent": manifest.percent,
        "queue_position": manifest.queue_position,
        "personal": manifest.personal,
        "updated_at": manifest.updated_at,
    }


def _publishable_html(run: RunState) -> str | None:
    manifest = run.manifest
    if manifest.status is not Status.DONE or not can_publish(manifest):
        return None
    # Prefer the output named "report"; otherwise the first HTML output.
    paths = [manifest.outputs.get("report", ""), *manifest.outputs.values()]
    html = next((path for path in paths if path.endswith(HTML_SUFFIX)), None)
    return None if html is None else str(run.run_dir / html)
