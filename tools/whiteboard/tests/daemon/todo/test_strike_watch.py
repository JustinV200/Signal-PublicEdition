"""StrikeWatcher on synthetic clean snapshots: a confirmed cross-out ticks life/, doubt only hints,
other ink goes on to the board agent."""

import asyncio
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from whiteboard.camera import Calibration, CaptureRig, keep_mode
from whiteboard.daemon.todo import (
    StrikeHooks,
    StrikeVerdict,
    StrikeWatcher,
    TodoController,
    TodoFiles,
)
from whiteboard.display.scene import SceneStore
from whiteboard.display.server import BoardController
from whiteboard.todo import StrikeTarget

pytestmark = pytest.mark.asyncio

# No board fit, so the board is the projector's 1280x720.
BOARD_W, BOARD_H = 1280, 720
BOARD_GREY = 200
INK_GREY = 40
# A camera bump of about a row slides the wall, then the board's dark frame, in at the top.
WALL_GREY, FRAME_GREY = 170, 110
FRAME_TOP_PX, FRAME_BOTTOM_PX = 16, 30
A19_LINE = "- [ ] [chem-120] A19 Recursion Drill (due 2026-10-19 23:59)"
READING_LINE = "- [ ] [chem-120] Reading video (due Fri 12:00)"
A20_LINE = "- [ ] [chem-120] A20 Slides (due 2026-10-19 09:00)"
A17_LINE = "- [x] [chem-120] A17 Queues (due 2026-10-20)"
CHANGE_BBOX = (100, 47, 500, 6)

Line = tuple[float, float, float]


class Recorder:
    """Stands in for the confirm call and the agent's callbacks, keeping what it was given."""

    def __init__(self, verdict: StrikeVerdict | None = None) -> None:
        self.verdict = verdict
        self.calls: list[tuple] = []

    async def __call__(self, *args) -> StrikeVerdict | None:
        self.calls.append(args)
        return self.verdict

    def sync_call(self, *args) -> None:
        self.calls.append(args)


def snapshot(path: Path, lines: list[Line] = (), is_bumped: bool = False) -> Path:
    """A blank board photo with dark marker lines (x0, x1, y), saved as PNG.

    `is_bumped` shows the wall and the board's frame along the top, as after a bump.
    """
    image = np.full((BOARD_H, BOARD_W, 3), BOARD_GREY, dtype=np.uint8)
    if is_bumped:
        image[:FRAME_TOP_PX] = WALL_GREY
        image[FRAME_TOP_PX:FRAME_BOTTOM_PX] = FRAME_GREY
    for x0, x1, y in lines:
        cv2.line(image, (round(x0), round(y)), (round(x1), round(y)), (INK_GREY,) * 3, 4)
    cv2.imencode(".png", image)[1].tofile(path)
    return path


def across(row: StrikeTarget, rows_down: float = 0.0) -> Line:
    """A marker line across the row's text, `rows_down` row heights below its middle."""
    middle = (row.y0 + row.y1) / 2 + rows_down * (row.y1 - row.y0)
    return (row.x0 - 10, row.x1 + 10, middle)


def line_bbox(line: Line) -> tuple[int, int, int, int]:
    """The change watcher's bbox around one marker line."""
    x0, x1, y = line
    return (round(x0) - 2, round(y) - 3, round(x1 - x0) + 4, 6)


async def show_view(tmp_path: Path, life_dir: Path) -> tuple[BoardController, TodoController]:
    """The TODO view of life_dir's plan, showing."""
    board = BoardController(SceneStore(tmp_path / "scene.json"))
    files = TodoFiles(life_dir, tmp_path / "todo.json", tmp_path / "todo.log")
    todo = TodoController(board, files, lambda: datetime(2026, 10, 19, 12))
    await todo.show()
    return board, todo


def fake_rig(tmp_path: Path) -> CaptureRig:
    """A capture rig whose camera sees the board straight on (camera px = board px)."""
    size = (BOARD_W, BOARD_H)
    calibration = Calibration(np.eye(3), size, size, 0.0, 0, "2026-10-19T00:00:00Z")
    projected = np.full((BOARD_H, BOARD_W, 3), BOARD_GREY, dtype=np.uint8)
    camera = SimpleNamespace(latest=lambda: projected, read_fresh=lambda: projected)
    return CaptureRig(camera, keep_mode, tmp_path, 0, 1, calibration)


async def start_watcher(
    todo: TodoController,
    before: Path,
    verdict: StrikeVerdict | None,
    is_drifted: Callable[[], bool] = lambda: False,
):
    """A watcher whose first snapshot (its first "before") is `before`."""
    confirm, forward, noted = Recorder(verdict), Recorder(), Recorder()
    rig = fake_rig(before.parent)
    watcher = StrikeWatcher(todo, rig, confirm, forward, StrikeHooks(noted.sync_call, is_drifted))
    await watcher.on_board_changed(before, (0, 0, 1, 1))
    return watcher, rig, (confirm, forward, noted)


async def setup(tmp_path: Path, life_dir: Path, verdict: StrikeVerdict | None):
    board, todo = await show_view(tmp_path, life_dir)
    watcher, _, recorders = await start_watcher(todo, snapshot(tmp_path / "before.png"), verdict)
    return board, todo, watcher, recorders


async def target_for(todo: TodoController, text_piece: str, board: BoardController) -> StrikeTarget:
    rows = board.todo_message()["todo"]["rows"]
    row_id = next(row["id"] for row in rows if text_piece in row["text"])
    targets = await todo.strike_targets(todo.layout_generation)
    return next(target for target in targets if target.id == row_id)


async def change(watcher: StrikeWatcher, path: Path, bbox: tuple[int, int, int, int]) -> None:
    """Report a change and wait for the background check to finish."""
    await watcher.on_board_changed(path, bbox)
    while watcher._tasks:
        await asyncio.sleep(0.01)


def plan_path(life_dir: Path) -> Path:
    return life_dir / "terms/2026-fall/weeks/2026-10-19-to-10-25/plan.md"


def plan_text(life_dir: Path) -> str:
    return plan_path(life_dir).read_text(encoding="utf-8")


async def test_a_confirmed_cross_out_ticks_the_item_and_skips_the_agent(
    tmp_path: Path, life_dir: Path
) -> None:
    board, todo, watcher, (confirm, forward, noted) = await setup(tmp_path, life_dir, None)
    target = await target_for(todo, "A19", board)
    # The model gets the row as projected, and the rows around it.
    assert target.text == "[chem-120] A19 Recursion Drill (due 23:59)"
    above = "[hist-205] Practice Quiz (due 4d late)"
    assert (target.above, target.below) == (above, "[chem-120] A17 Queues")
    confirm.verdict = StrikeVerdict((target.id,), (), "a line through box 1")
    after = snapshot(tmp_path / "after.png", [across(target)])
    await change(watcher, after, line_bbox(across(target)))
    assert A19_LINE.replace("[ ]", "[x]") in plan_text(life_dir)
    # (before, after, projected, candidates)
    assert [call[3] for call in confirm.calls] == [[target]]
    # Only the first (baseline) change went to the agent; this one moved its "before" on.
    assert len(forward.calls) == 1 and noted.calls == [(after,)]
    # The tick synced the view but moved no row, so the next cross-out is checked too.
    ttl = await target_for(todo, "Reading video", board)
    confirm.verdict = StrikeVerdict((ttl.id,), (), "a line through box 1")
    second = snapshot(tmp_path / "second.png", [across(target), across(ttl)])
    await change(watcher, second, line_bbox(across(ttl)))
    assert READING_LINE.replace("[ ]", "[x]") in plan_text(life_dir)


@pytest.mark.parametrize(
    ("is_sure", "twin_line"),
    [(False, None), (True, A19_LINE.replace("chem-120", "math-201"))],
    ids=["the check is unsure", "sure, but the next row reads the same under another tag"],
)
async def test_an_unsure_cross_out_only_shows_a_hint(
    tmp_path: Path, life_dir: Path, is_sure: bool, twin_line: str | None
) -> None:
    if twin_line is not None:
        plan_path(life_dir).write_text(
            plan_text(life_dir).replace(A19_LINE, f"{A19_LINE}\n{twin_line}"), encoding="utf-8"
        )
    board, todo, watcher, (confirm, forward, _) = await setup(tmp_path, life_dir, None)
    target = await target_for(todo, "A19", board)
    answer = ((target.id,), ()) if is_sure else ((), (target.id,))
    confirm.verdict = StrikeVerdict(*answer, "a line through box 1")
    middle = (target.y0 + target.y1) / 2
    after = snapshot(tmp_path / "after.png", [(target.x0, target.x1, middle)])
    await change(watcher, after, (round(target.x0), round(middle) - 3, 300, 6))
    assert "[x]" not in plan_text(life_dir).replace(A17_LINE, "")
    rows = board.todo_message()["todo"]["rows"]
    assert [row["hint"] for row in rows if row["id"] == target.id] == [True]


async def test_a_sync_that_moves_the_rows_before_the_check_reads_them_ticks_nothing(
    tmp_path: Path, life_dir: Path
) -> None:
    board, todo, watcher, (confirm, forward, _) = await setup(tmp_path, life_dir, None)
    line = across(await target_for(todo, "A19", board))
    after = snapshot(tmp_path / "after.png", [line])
    # Reported under the old rows; the check task starts but waits for the sync's lock.
    await watcher.on_board_changed(after, line_bbox(line))
    await _between_snapshots("sync moved the rows", todo, None, life_dir)
    while watcher._tasks:
        await asyncio.sleep(0.01)
    # Matched against the new rows, the line would run through A20, which took A19's place.
    assert confirm.calls == [] and "[x]" not in plan_text(life_dir).replace(A17_LINE, "")
    assert forward.calls[-1] == (after, line_bbox(line))


@pytest.mark.parametrize(
    "other_row",
    [None, "Poster draft"],
    ids=["note in the header", "note across a row the check didn't confirm"],
)
async def test_a_cross_out_with_writing_elsewhere_ticks_and_still_goes_to_the_agent(
    tmp_path: Path, life_dir: Path, other_row: str | None
) -> None:
    board, todo, watcher, (confirm, forward, noted) = await setup(tmp_path, life_dir, None)
    target = await target_for(todo, "A19", board)
    confirm.verdict = StrikeVerdict((target.id,), (), "a line through box 1")
    middle = (target.y0 + target.y1) / 2
    note_y = 50.0
    if other_row is not None:
        other = await target_for(todo, other_row, board)
        note_y = (other.y0 + other.y1) / 2
    lines = [(target.x0 - 10, target.x1 + 10, middle), (100, 600, note_y)]
    after = snapshot(tmp_path / "after.png", lines)
    top, bottom = round(min(middle, note_y)) - 3, round(max(middle, note_y)) + 3
    bbox = (100, top, 500, bottom - top)
    await change(watcher, after, bbox)
    assert A19_LINE.replace("[ ]", "[x]") in plan_text(life_dir)
    assert forward.calls[-1] == (after, bbox) and noted.calls == []


async def _between_snapshots(event: str | None, todo: TodoController, rig, life_dir: Path) -> None:
    """Something that happens after the watcher's "before" and before the change."""
    if event == "hide":
        await todo.hide()
    elif event == "re-align":
        rig.calibration = object()  # a re-align replaces the calibration object
    elif event == "sync moved the rows":
        # A plan edit picked up by a sync (another session, or a tick's own sync): a new
        # item takes A19's place, and the last one goes, so the rows keep their size.
        edited = plan_text(life_dir).replace(A19_LINE, f"{A20_LINE}\n{A19_LINE}")
        edited = edited.replace("- [ ] [club] Pitch deck draft\n", "")
        plan_path(life_dir).write_text(edited, encoding="utf-8")
        await todo.sync()
    elif event == "items view in between":
        await todo.hide()
        await todo.show()


@pytest.mark.parametrize(
    ("ink", "event"),
    [
        (lambda row: ([], [across(row)]), "hide"),
        (lambda row: ([across(row)], []), None),
        (lambda row: ([], [across(row)]), "re-align"),
        # Two old cross-outs on neighbouring rows, a row lower: the ink erased is two
        # rows above the ink added.
        (lambda row: ([across(row, -2), across(row, -1)], [across(row, -1), across(row)]), None),
        # The frame shows along the top, outside the area the shift check weighs; the
        # old line's own erased ink is what trips it.
        (lambda row: ([across(row, -1)], [across(row)]), "bump shows the frame"),
        (lambda row: ([], [across(row)]), "drift"),
        (lambda row: ([], [across(row)]), "sync moved the rows"),
        (lambda row: ([], [across(row)]), "items view in between"),
    ],
    ids=[
        "without the TODO view",
        "erasing a cross-out",
        "first change after a re-align",
        "two old cross-outs shifted a row",
        "a bump that slides the board's frame into view",
        "the drift check found the board moved",
        "a sync moved the rows after the line was drawn",
        "the items view showed in between",
    ],
)
async def test_these_changes_go_to_the_agent_unchecked(
    tmp_path: Path, life_dir: Path, ink, event: str | None
) -> None:
    board, todo = await show_view(tmp_path, life_dir)
    before_lines, after_lines = ink(await target_for(todo, "A19", board))
    before = snapshot(tmp_path / "before.png", before_lines)
    watcher, rig, (confirm, forward, _) = await start_watcher(
        todo, before, None, is_drifted=lambda: event == "drift"
    )
    await _between_snapshots(event, todo, rig, life_dir)
    after = snapshot(tmp_path / "after.png", after_lines, event == "bump shows the frame")
    await change(watcher, after, CHANGE_BBOX)
    assert confirm.calls == [] and forward.calls[-1] == (after, CHANGE_BBOX)


async def test_the_first_cross_out_after_showing_the_view_is_checked(
    tmp_path: Path, life_dir: Path
) -> None:
    # Regression: the last change before the switch was the only "before", so the first
    # line drawn under the list (2026-10-20 15:36) went to the agent unchecked.
    board, todo = await show_view(tmp_path, life_dir)
    await todo.hide()
    confirm, forward = Recorder(), Recorder()
    watcher = StrikeWatcher(todo, fake_rig(tmp_path), confirm, forward)
    todo.on_shown = watcher.note_view_shown
    await todo.show()
    while watcher._tasks:  # the fresh "before" capture
        await asyncio.sleep(0.01)
    target = await target_for(todo, "A19", board)
    confirm.verdict = StrikeVerdict((target.id,), (), "a line through box 1")
    after = snapshot(tmp_path / "after.png", [across(target)])
    await change(watcher, after, line_bbox(across(target)))
    assert A19_LINE.replace("[ ]", "[x]") in plan_text(life_dir) and forward.calls == []
