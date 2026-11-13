"""set_line_done, the whiteboard's only write to life/: exact line, refuse if changed."""

import codecs
import os
from datetime import date
from pathlib import Path

import pytest

from whiteboard.todo.source import (
    PlanEditError,
    PlanText,
    SourceLine,
    find_entries,
    parse_plan,
    plan_edit,
    read_plan,
    set_line_done,
)

MONDAY = date(2026, 10, 19)
PLAN = (
    "# Week plan\r\n## CHEM 120\r\n"
    "- [ ] [chem-120] A19 (due 2026-10-19 23:59)\r\n- [ ] [chem-120] A22\r\n"
)


def plan_with(tmp_path: Path, text: str, bom: bool = False) -> Path:
    path = tmp_path / "plan.md"
    path.write_bytes((codecs.BOM_UTF8 if bom else b"") + text.encode("utf-8"))
    return path


def source_of(path: Path, text_piece: str) -> SourceLine:
    entries = parse_plan(read_plan(path).text, path, MONDAY)
    return find_entries(entries, text_piece)[0].source


def test_ticking_changes_only_that_checkbox_and_keeps_endings_and_bom(tmp_path: Path) -> None:
    path = plan_with(tmp_path, PLAN, bom=True)
    assert set_line_done(source_of(path, "A19"), True, tmp_path) is True
    expected = PLAN.replace("- [ ] [chem-120] A19", "- [x] [chem-120] A19")
    assert path.read_bytes() == codecs.BOM_UTF8 + expected.encode("utf-8")
    # Already ticked: nothing to write.
    assert set_line_done(source_of(path, "A19"), True, tmp_path) is False
    # Undo puts it back exactly.
    assert set_line_done(source_of(path, "A19"), False, tmp_path) is True
    assert path.read_bytes() == codecs.BOM_UTF8 + PLAN.encode("utf-8")


def test_a_line_that_moved_is_found_by_its_exact_text(tmp_path: Path) -> None:
    path = plan_with(tmp_path, PLAN)
    source = source_of(path, "A22")
    path.write_bytes(("- [ ] [club] new line\r\n" + PLAN).encode("utf-8"))
    assert set_line_done(source, True, tmp_path)
    assert "- [x] [chem-120] A22\r\n" in path.read_bytes().decode("utf-8")


@pytest.mark.parametrize(
    "edited",
    [
        PLAN.replace("A22", "A22 (due Fri)"),  # the owner edited the line
        # It moved and is now there twice: which one is meant?
        "- [ ] [club] new\r\n" + PLAN + "- [ ] [chem-120] A22\r\n",
    ],
)
def test_a_changed_or_ambiguous_line_is_refused_and_the_file_left_alone(
    tmp_path: Path, edited: str
) -> None:
    path = plan_with(tmp_path, PLAN)
    source = source_of(path, "A22")
    path.write_bytes(edited.encode("utf-8"))
    with pytest.raises(PlanEditError):
        set_line_done(source, True, tmp_path)
    assert path.read_bytes() == edited.encode("utf-8")


def test_a_save_landing_mid_edit_is_kept_and_no_temp_file_is_left(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = plan_with(tmp_path, PLAN)
    source = source_of(path, "A22")
    owner_save = (PLAN + "- [ ] [club] added meanwhile\r\n").encode("utf-8")

    def read_then_owner_saves(plan_path: Path) -> PlanText:
        plan = read_plan(plan_path)
        plan_path.write_bytes(owner_save)
        return plan

    monkeypatch.setattr(plan_edit, "read_plan", read_then_owner_saves)
    with pytest.raises(PlanEditError, match="changed while"):
        set_line_done(source, True, tmp_path)
    assert path.read_bytes() == owner_save and list(tmp_path.iterdir()) == [path]


def link_folder(link: Path, target: Path) -> None:
    """A directory junction (no admin needed on Windows), else a symlink."""
    try:
        import _winapi

        _winapi.CreateJunction(str(target), str(link))
    except (ImportError, OSError):
        try:
            os.symlink(target, link, target_is_directory=True)
        except OSError as error:
            pytest.skip(f"can't create a folder link here: {error}")


@pytest.mark.parametrize("where", ["not a plan", "plan through a link out of life"])
def test_only_plan_files_inside_life_can_be_edited(tmp_path: Path, where: str) -> None:
    life, outside = tmp_path / "life", tmp_path / "outside"
    life.mkdir()
    outside.mkdir()
    if where == "not a plan":
        target = path = life / "README.md"
    else:
        target, path = outside / "plan.md", life / "terms" / "plan.md"
        link_folder(life / "terms", outside)
    target.write_text("- [ ] [chem-120] A22\n", encoding="utf-8")
    with pytest.raises(PlanEditError):
        set_line_done(SourceLine(path, 0, "- [ ] [chem-120] A22"), True, life)
    assert target.read_text(encoding="utf-8") == "- [ ] [chem-120] A22\n"
