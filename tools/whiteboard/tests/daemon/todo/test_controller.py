"""TodoController: show/hide keep the items, done/undone write life/, cross-outs that fail hint."""

from datetime import datetime
from pathlib import Path

import pytest

from whiteboard.daemon.todo import TodoController, TodoFiles
from whiteboard.daemon.todo import controller as controller_module
from whiteboard.display.scene import SceneStore, item_from_dict
from whiteboard.display.server import BoardController
from whiteboard.todo import PlanEditError, set_line_done

pytestmark = pytest.mark.asyncio

MONDAY_NOON = datetime(2026, 10, 19, 12, 0)
A19 = "- [ ] [chem-120] A19 Recursion Drill (due 2026-10-19 23:59)"
PLAN = "terms/2026-fall/weeks/2026-10-19-to-10-25/plan.md"  # under life/
TEXT_ITEM = {"id": "t1", "kind": "text", "x": 10, "y": 20, "w": 300, "h": 60, "content": "hi"}


class Clock:
    """A settable local time."""

    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def board(tmp_path: Path) -> BoardController:
    return BoardController(SceneStore(tmp_path / "scene.json"))


def make_todo(board: BoardController, life_dir: Path, clock: Clock) -> TodoController:
    state = life_dir.parent / "state"
    files = TodoFiles(life_dir, state / "todo.json", state / "todo.log")
    return TodoController(board, files, clock)


def plan_text(life_dir: Path) -> str:
    return (life_dir / PLAN).read_text(encoding="utf-8")


def todo_ids(summary: dict, text: str) -> list[str]:
    return [item["id"] for item in summary["items"] if item["text"] == text]


async def test_show_and_hide_switch_views_and_keep_the_items(
    board: BoardController, life_dir: Path, tmp_path: Path
) -> None:
    await board.put_item(item_from_dict(TEXT_ITEM))
    todo = make_todo(board, life_dir, Clock(MONDAY_NOON))
    summary = await todo.show()
    assert board.scene.view == "todo" and [item.id for item in board.scene.items] == ["t1"]
    assert (summary["overdue"], summary["upcoming"], summary["of_note"]) == (1, 4, 2)
    # The undated A15 is folded into the Overdue heading.
    assert summary["not_shown"] == 1
    assert summary["plans"] == [f"life/{PLAN}"]
    # The view is saved with the scene, so a restarted daemon comes back to it.
    assert SceneStore(tmp_path / "scene.json").load().view == "todo"
    await todo.hide()
    assert board.scene.view == "items" and [item.id for item in board.scene.items] == ["t1"]
    # Drawing while the TODO view is up brings the items back; the thinking box doesn't.
    await todo.show()
    await board.put_item(item_from_dict({**TEXT_ITEM, "id": "loading", "kind": "loading"}))
    assert board.scene.view == "todo"
    await board.put_item(item_from_dict({**TEXT_ITEM, "id": "t2"}))
    assert board.scene.view == "items"


async def test_done_ticks_the_plan_and_animates_then_undone_reverts(
    board: BoardController, life_dir: Path
) -> None:
    sent: list[dict] = []
    board.hub.broadcast = lambda message: _record(sent, message)
    todo = make_todo(board, life_dir, Clock(MONDAY_NOON))
    first = await todo.sync()
    done = await todo.set_done("A19", True, "api")
    a19 = todo_ids(first, "A19 Recursion Drill")
    assert A19.replace("[ ]", "[x]") in plan_text(life_dir) and done["changed"] is True
    assert done["newly_done"] == a19 and sent[-1]["newly_done"] == a19
    row = next(row for row in sent[-1]["todo"]["rows"] if row["id"] == a19[0])
    assert row["done"] is True
    audit = (life_dir.parent / "state/todo.log").read_text(encoding="utf-8")
    where = f"life/{PLAN}:11"
    assert f"done (api): [chem-120] A19 Recursion Drill -- {where}" in audit
    undone = await todo.set_done(a19[0], False, "api")
    assert A19 in plan_text(life_dir) and undone["newly_done"] == []


async def test_done_reads_the_plan_fresh_so_edits_since_the_sync_are_fine(
    board: BoardController, life_dir: Path
) -> None:
    todo = make_todo(board, life_dir, Clock(MONDAY_NOON))
    await todo.sync()
    # The owner adds a line above and touches up the item after the board's last sync.
    plan = life_dir / PLAN
    edited = "- [ ] [club] New first line\n" + plan_text(life_dir).replace(A19, A19 + " ok")
    plan.write_text(edited, encoding="utf-8")
    await todo.set_done("A19 Recursion", True, "api")
    assert plan_text(life_dir) == edited.replace(A19 + " ok", A19.replace("[ ]", "[x]") + " ok")


async def test_a_write_that_fails_part_way_still_updates_the_page(
    board: BoardController, life_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Stands in for a multi-line item whose first line is written and a later one isn't.
    def write_then_fail(source, is_done, life):
        set_line_done(source, is_done, life)
        raise PlanEditError("the next line changed")

    monkeypatch.setattr(controller_module, "set_line_done", write_then_fail)
    todo = make_todo(board, life_dir, Clock(MONDAY_NOON))
    a19 = todo_ids(await todo.show(), "A19 Recursion Drill")
    with pytest.raises(PlanEditError):
        await todo.set_done(a19[0], True, "api")
    rows = board.todo_message()["todo"]["rows"]
    assert [row["done"] for row in rows if row["id"] == a19[0]] == [True]


async def test_a_cross_out_that_cant_be_ticked_shows_the_hint_instead(
    board: BoardController, life_dir: Path
) -> None:
    todo = make_todo(board, life_dir, Clock(MONDAY_NOON))
    a19 = todo_ids(await todo.show(), "A19 Recursion Drill")
    # The owner renamed the item after the board's last sync, so its id is gone.
    plan = life_dir / PLAN
    plan.write_text(
        plan_text(life_dir).replace("A19 Recursion Drill", "A19 Recursion"), encoding="utf-8"
    )
    await todo.mark_struck(a19)
    rows = board.todo_message()["todo"]["rows"]
    assert [row["hint"] for row in rows if row["id"] == a19[0]] == [True]


async def _record(sent: list[dict], message: dict) -> None:
    sent.append(message)
