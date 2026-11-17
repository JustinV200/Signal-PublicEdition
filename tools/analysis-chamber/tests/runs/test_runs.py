"""Tests for analysis_chamber.runs: ids, the manifest round trip, scanning and moving."""

import logging
from datetime import date
from pathlib import Path

import pytest

from analysis_chamber.runs import (
    Manifest,
    ManifestError,
    Phase,
    Status,
    create_run_dir,
    make_run_id,
    move_run,
    read_manifest,
    scan_runs,
    write_manifest,
)

TODAY = date(2026, 11, 16)
OLD_TIME = "2020-01-01T00:00:00+00:00"
# Every field with a value of the wrong top-level type ("5" for ints, 5 for the rest).
INT_FIELDS = {"percent", "queue_position", "schema_version"}
WRONG_TYPES = [
    {name: "5" if name in INT_FIELDS else 5} for name in Manifest(id="a", question="q").to_dict()
]


def test_run_id_slug_and_clash_suffix() -> None:
    question = "What's the median rent in Denver, with a very long tail?"
    first = make_run_id(question, TODAY, set())
    # cut at 40, trailing hyphen dropped
    assert first == "2026-11-16-what-s-the-median-rent-in-denver-with-a"
    assert make_run_id(question, TODAY, {first}) == f"{first}-2"
    assert make_run_id(question, TODAY, {first, f"{first}-2"}) == f"{first}-3"
    assert make_run_id("Café crème?", TODAY, set()) == "2026-11-16-cafe-creme"
    assert make_run_id("???", TODAY, set()) == "2026-11-16-run"
    # The 40-char cut lands on the hyphen after 39 letters; it's dropped, not kept.
    assert make_run_id("a" * 39 + " b", TODAY, set()) == "2026-11-16-" + "a" * 39


def test_manifest_round_trip(tmp_path: Path) -> None:
    run_dir = create_run_dir(tmp_path, "2026-11-16-q")
    manifest = Manifest(
        id="2026-11-16-q",
        question="q",
        personal=False,
        phase=Phase.ANALYSE,
        status=Status.RUNNING,
        percent=45,
        finished_phases=["plan", "collect"],
        sessions={"lead": "abc"},
        installs=[{"package": "xgboost", "version": "3.0.0"}],
        report_format="md",
        updated_at=OLD_TIME,
    )
    written = write_manifest(run_dir, manifest)
    assert read_manifest(run_dir) == written
    assert written.updated_at != OLD_TIME and manifest.updated_at == OLD_TIME
    assert (run_dir / "data" / "raw").is_dir()
    assert "data/raw/" in (run_dir / ".gitignore").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "change",
    [
        {"schema_version": 2},
        {"schema_version": True},
        {"phase": "nope"},
        {"percent": 101},
        {"percent": True},
        {"timings": {"plan": {"started": 5}}},
        {"outputs": {"report": None}},
        {"queue_position": True},
        {"finished_phases": ["plan", "nope"]},
        {"sessions": {"lead": 5}},
        {"installs": [{"package": "xgboost", "version": 5}]},
        {"finished_phases": [{}]},
        {"id": "../escape"},
        {"id": "a/b"},
        {"id": "a\\b"},
        {"id": ".."},
        {"id": "a.b"},
        {"id": "Ab"},
        {"percent": -1},
        {"queue_position": -1},
        {"report_format": "pdf"},
        {"timings": {"nope": {}}},
        {"installs": [{"package": "xgboost"}]},
        {"sources": [{"name": "a"}, 3]},
        {"x": 1},
        *WRONG_TYPES,
    ],
)
def test_bad_manifest_is_refused(change: dict) -> None:
    data = {**Manifest(id="a", question="q").to_dict(), **change}
    with pytest.raises(ManifestError):
        Manifest.from_dict(data)


def test_scan_skips_broken_manifest_with_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    good = create_run_dir(tmp_path, "good")
    write_manifest(good, Manifest(id="good", question="q"))
    broken = create_run_dir(tmp_path, "broken")
    (broken / "manifest.json").write_text("{", encoding="utf-8")
    renamed = create_run_dir(tmp_path, "renamed")
    write_manifest(renamed, Manifest(id="other", question="q"))
    with caplog.at_level(logging.WARNING):
        found = scan_runs([tmp_path, tmp_path / "missing-root"])
    assert [manifest.id for _, manifest in found] == ["good"]
    assert "broken" in caplog.text and "renamed" in caplog.text


def test_move_run_refuses_to_overwrite(tmp_path: Path) -> None:
    run_dir = create_run_dir(tmp_path / "private", "r1")
    moved = move_run(run_dir, tmp_path / "analyses")
    assert moved == tmp_path / "analyses" / "r1" and not run_dir.exists()
    create_run_dir(tmp_path / "private", "r1")
    with pytest.raises(FileExistsError):
        move_run(tmp_path / "private" / "r1", tmp_path / "analyses")
