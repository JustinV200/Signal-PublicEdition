"""The Manifest record (a run's manifest.json) and its dict conversion.

from_dict is the trust boundary for a file on disk: it checks schema_version
first (the hook point for future migrations), then every field's type.
"""

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from analysis_chamber.runs.ids import RUN_ID_PATTERN
from analysis_chamber.runs.states import Phase, Status

SCHEMA_VERSION = 1
REPORT_FORMATS = frozenset({"html", "md", "ipynb", "artifact"})
PERCENT_RANGE = (0, 100)
INSTALL_KEYS = frozenset({"package", "version"})


class ManifestError(ValueError):
    """A manifest is missing, unreadable, from another schema version or malformed."""


def utc_now_iso() -> str:
    """The current time as an ISO-8601 UTC string, to the second."""
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass
class Manifest:
    """Everything the daemon knows about one run, checkpointed after each phase.

    Attributes:
        id: The run id, also the run folder's name.
        question: The user's question, as given.
        plan_text: The current plan (also in plan.md).
        personal: The user's flag from the plan check; None until the user sets it.
        phase, status, percent: Progress (percent is 0-100).
        finished_phases: Phase values done so far, in order.
        sessions: Agent role -> Agent SDK session id, for resume.
        installs: [{package, version}] installed into the run venv.
        sources: [{name, url, status, note, fetched_at}].
        timings: Phase value -> {started, finished} ISO strings.
        last_error: The last failure message, if any.
        outputs: Output name -> path relative to the run folder.
        report_format: "html", "md", "ipynb" or "artifact"; None until chosen.
        created_at, updated_at: ISO-8601 UTC strings.
        queue_position: Place in the queue while queued, else None.
        schema_version: Always SCHEMA_VERSION when written.
    """

    id: str
    question: str
    plan_text: str = ""
    personal: bool | None = None
    phase: Phase = Phase.PLAN
    status: Status = Status.AWAITING_APPROVAL
    percent: int = 0
    finished_phases: list[str] = field(default_factory=list)
    sessions: dict[str, str] = field(default_factory=dict)
    installs: list[dict[str, str]] = field(default_factory=list)
    sources: list[dict[str, Any]] = field(default_factory=list)
    timings: dict[str, dict[str, str]] = field(default_factory=dict)
    last_error: str | None = None
    outputs: dict[str, str] = field(default_factory=dict)
    report_format: str | None = None
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    queue_position: int | None = None
    schema_version: int = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        """A JSON-ready dict (enums become their string values)."""
        data = asdict(self)
        data["phase"] = self.phase.value
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: object) -> "Manifest":
        """Build a Manifest from parsed JSON, checking the version and every field.

        Raises:
            ManifestError: Not an object, another schema_version, or a bad field.
        """
        if not isinstance(data, dict):
            raise ManifestError("manifest: expected a JSON object")
        version = data.get("schema_version")
        # Migration hook point: older versions would be upgraded here.
        # Exact type check: bool is an int subclass and True == 1.
        if type(version) is not int or version != SCHEMA_VERSION:
            raise ManifestError(
                f"manifest: schema_version {version!r} is not supported (expected {SCHEMA_VERSION})"
            )
        try:
            enums = {"phase": Phase(data["phase"]), "status": Status(data["status"])}
            manifest = cls(**{**data, **enums})
        except (KeyError, TypeError, ValueError) as error:
            raise ManifestError(f"manifest: bad or missing field: {error}") from error
        _check_types(manifest)
        return manifest


# Field -> allowed types, checked after construction.
_FIELD_TYPES: dict[str, tuple[type, ...]] = {
    "id": (str,),
    "question": (str,),
    "plan_text": (str,),
    "personal": (bool, type(None)),
    "percent": (int,),
    "finished_phases": (list,),
    "sessions": (dict,),
    "installs": (list,),
    "sources": (list,),
    "timings": (dict,),
    "last_error": (str, type(None)),
    "outputs": (dict,),
    "report_format": (str, type(None)),
    "created_at": (str,),
    "updated_at": (str,),
    "queue_position": (int, type(None)),
}


def _check_types(manifest: Manifest) -> None:
    """Raise ManifestError for a field of the wrong type or out of range."""
    for name, allowed in _FIELD_TYPES.items():
        if not isinstance(getattr(manifest, name), allowed):
            raise ManifestError(f"manifest: {name} has the wrong type")
    # bool passes isinstance(int), so the int fields refuse it explicitly.
    position = manifest.queue_position
    if isinstance(position, bool) or (position is not None and position < 0):
        raise ManifestError("manifest: queue_position must be a non-negative integer")
    # The id names the run folder, so it must be one safe path segment (no `..`, slashes).
    if not RUN_ID_PATTERN.fullmatch(manifest.id):
        raise ManifestError(f"manifest: id {manifest.id!r} is not a valid run id")
    low, high = PERCENT_RANGE
    if isinstance(manifest.percent, bool) or not low <= manifest.percent <= high:
        raise ManifestError(f"manifest: percent must be {low}-{high}")
    if manifest.report_format is not None and manifest.report_format not in REPORT_FORMATS:
        raise ManifestError(f"manifest: unknown report_format {manifest.report_format!r}")
    _check_contents(manifest)


_PHASE_VALUES = frozenset(phase.value for phase in Phase)


def _is_str_dict(value: object) -> bool:
    """Whether value is a dict whose keys are all strings."""
    return isinstance(value, dict) and all(isinstance(key, str) for key in value)


def _is_str_to_str(value: object) -> bool:
    """Whether value is a dict of string keys to string values."""
    return _is_str_dict(value) and all(isinstance(item, str) for item in value.values())


def _is_install(value: object) -> bool:
    """Whether value is a {package, version, ...} object of strings."""
    return _is_str_to_str(value) and value.keys() >= INSTALL_KEYS


def _check_contents(manifest: Manifest) -> None:
    """Raise ManifestError for a container holding the wrong kind of item."""
    # isinstance first: a list or dict item is unhashable and the `in` would raise TypeError.
    phases = manifest.finished_phases
    if not all(isinstance(item, str) and item in _PHASE_VALUES for item in phases):
        raise ManifestError("manifest: finished_phases holds an unknown phase")
    for name in ("sessions", "outputs"):
        if not _is_str_to_str(getattr(manifest, name)):
            raise ManifestError(f"manifest: {name} must map strings to strings")
    timings = manifest.timings
    if not all(key in _PHASE_VALUES and _is_str_to_str(value) for key, value in timings.items()):
        raise ManifestError("manifest: timings must map phase values to {str: str}")
    if not all(_is_install(item) for item in manifest.installs):
        raise ManifestError("manifest: installs must hold {package, version} string objects")
    if not all(_is_str_dict(item) for item in manifest.sources):
        raise ManifestError("manifest: sources must hold objects with string keys")
