"""IdleController: the default rule end to end, pushes on the minute flip, failing sources,
and board ink (InkWatch) blanking the view and holding the rule off."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import cv2
import numpy as np
import pytest
from signal_weather import Place, WeatherError

from whiteboard.camera import CleanFrame
from whiteboard.config import IdleSettings
from whiteboard.daemon.idle import IdleController, IdleFiles, IdleHooks, InkWatch, Lookups
from whiteboard.daemon.idle.ink_watch import REFERENCE_MAX_AGE_S
from whiteboard.display.scene import SceneStore, item_from_dict
from whiteboard.display.server import BoardController

pytestmark = pytest.mark.asyncio

NOW = datetime(2026, 10, 20, 12, 0, tzinfo=timezone(timedelta(hours=-4)))
TEXT_ITEM = {"id": "t1", "kind": "text", "x": 10, "y": 20, "w": 300, "h": 60, "content": "hi"}


class WallClock:
    """A settable local time."""

    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> datetime:
        return self.now


class Ticks:
    """A settable monotonic clock."""

    def __init__(self) -> None:
        self.now_s = 1000.0

    def __call__(self) -> float:
        return self.now_s


def no_network() -> Lookups:
    def fail(*_args: object) -> Place:
        raise WeatherError("offline")

    async def no_feed(_url: str) -> bytes:
        raise TimeoutError("offline")

    return Lookups(place=fail, forecast=fail, feed=no_feed)


def make_idle(
    board: BoardController, life_dir: Path, ticks: Ticks, wall: WallClock
) -> IdleController:
    state = life_dir.parent / "state"
    files = IdleFiles(
        life_dir,
        state / "todo.json",
        state / "tasks.json",
        state / "usage.json",
        state / "agenda.json",
        state / "idle",
    )
    hooks = IdleHooks(now=wall, monotonic=ticks, lookups=no_network())
    return IdleController(board, IdleSettings(), files, hooks)


def write_task(path: Path) -> None:
    task = {
        "id": "idle",
        "name": "Idle board",
        "pct": 50,
        "status": "building",
        "next": "",
        "you": "",
        "updated_at": NOW.isoformat(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"updated_at": NOW.isoformat(), "tasks": [task]}), "utf-8")


async def test_empty_board_goes_idle_pushes_once_and_drawing_brings_items_back(
    tmp_path: Path, life_dir: Path
) -> None:
    board = BoardController(SceneStore(tmp_path / "scene.json"))
    sent: list[dict] = []

    async def record(message: dict) -> None:
        sent.append(message)

    board.hub.broadcast = record
    ticks, wall = Ticks(), WallClock()
    idle = make_idle(board, life_dir, ticks, wall)

    def pushes() -> list[dict]:
        return [message["idle"] for message in sent if message["type"] == "idle"]

    await idle.start()
    try:
        await idle.tick()
        assert board.scene.view == "items"  # the timer only just started
        ticks.now_s += 10.0
        await idle.tick()
        assert board.scene.view == "idle"
        assert len(pushes()) == 1 and pushes()[0]["tasks"]
        # No network: weather and news show their empty states, nothing raised.
        assert pushes()[0]["weather"] is None and pushes()[0]["news"] is None
        # A new agent task mid-minute waits for the minute flip, so the drift monitor
        # still gets its quiet half-minute.
        write_task(life_dir.parent / "state" / "tasks.json")
        ticks.now_s += 20.0
        wall.now = NOW + timedelta(seconds=30)
        await idle.tick()
        assert len(pushes()) == 1
        wall.now = NOW + timedelta(minutes=1)
        await idle.tick()
        assert len(pushes()) == 2 and pushes()[1]["agents"]["active"][0]["name"] == "Idle board"
        # Nothing changed: the next flip pushes nothing.
        wall.now = NOW + timedelta(minutes=2)
        await idle.tick()
        assert len(pushes()) == 2
        await board.put_item(item_from_dict(TEXT_ITEM))
        assert board.scene.view == "items"
        assert (await idle.hide())["view"] == "items"
    finally:
        await idle.stop()


def board_photo(
    strokes: int = 0, specks: int = 0, light: int = 230, calibration: object = None
) -> CleanFrame:
    """A clean capture of a white board in `light`, with `strokes` short marker strokes
    (each about 0.0007 of the pixels, so it takes three to reach ink_min_ratio) and
    `specks` small grey specks (camera noise, about 0.0005 each), under `calibration`."""
    image = np.full((240, 320), light, dtype=np.uint8)
    for i in range(strokes):
        cv2.line(image, (60 + 25 * i, 120), (62 + 25 * i, 120), 30, 3)
    for i in range(specks):
        cv2.circle(image, (200 + 25 * i, 40), 2, 90, -1)
    return CleanFrame(image, True, calibration, image)  # type: ignore[arg-type]


async def go_idle(idle: IdleController, ticks: Ticks) -> None:
    await idle.tick()
    ticks.now_s += IdleSettings().empty_s
    await idle.tick()


class Watched:
    """An idle view going idle, its InkWatch and the changes InkWatch passed on."""

    def __init__(self, tmp_path: Path, life_dir: Path) -> None:
        self.board = BoardController(SceneStore(tmp_path / "scene.json"))
        self.ticks = Ticks()
        self.idle = make_idle(self.board, life_dir, self.ticks, WallClock())
        self.passed_on: list[Path] = []
        self.ink = InkWatch(self.idle, IdleSettings().ink_min_ratio, self._downstream)
        self.path = tmp_path / "snap.png"

    async def _downstream(self, path: Path, _bbox: tuple[int, int, int, int]) -> None:
        self.passed_on.append(path)

    async def report(self, photo: CleanFrame) -> None:
        """The watcher's clean capture, then its report of a change."""
        await self.ink.on_clean_frame(photo, self.ticks.now_s)
        await self.ink.on_board_changed(self.path, (1, 2, 3, 4))


async def test_ink_while_idle_blanks_the_board_until_it_has_been_quiet(
    tmp_path: Path, life_dir: Path
) -> None:
    w = Watched(tmp_path, life_dir)
    quiet_s = IdleSettings().ink_quiet_minutes * 60
    await go_idle(w.idle, w.ticks)
    assert w.board.scene.view == "idle"
    await w.ink.on_clean_frame(board_photo(), w.ticks.now_s)
    await w.report(board_photo(strokes=3))
    assert w.board.scene.view == "items" and w.passed_on == [w.path]
    await w.idle.tick()  # the loop's next tick: the empty items view starts its clock
    w.ticks.now_s += quiet_s - 1.0
    await w.idle.tick()
    assert w.board.scene.view == "items"  # empty well past empty_s, but the ink is recent
    w.ticks.now_s += 1.0
    await w.idle.tick()
    assert w.board.scene.view == "idle"


async def test_noise_and_drifting_light_never_blank_the_idle_view(
    tmp_path: Path, life_dir: Path
) -> None:
    # Regression: daylight noise on an untouched board (0.0004-0.0005 live) was taken for
    # ink, so the idle view kept disappearing. Noise that comes and goes never adds up.
    w = Watched(tmp_path, life_dir)
    await go_idle(w.idle, w.ticks)
    await w.ink.on_clean_frame(board_photo(), w.ticks.now_s)
    for _ in range(3):
        await w.report(board_photo(specks=2))
        w.ticks.now_s += 30.0
        await w.report(board_photo())
    # Slow drift: a speck more each photo as the light dims would add up to over
    # ink_min_ratio against the first photo, but the reference follows it once it's old.
    for specks in range(1, 5):
        w.ticks.now_s += REFERENCE_MAX_AGE_S
        await w.report(board_photo(specks=specks, light=230 - 15 * specks))
    assert w.board.scene.view == "idle" and not w.idle.is_holding_off
    assert len(w.passed_on) == 10  # the agent and cross-out check still get every report


async def test_slow_writing_blanks_the_view_and_wiping_it_brings_the_view_back(
    tmp_path: Path, life_dir: Path
) -> None:
    w = Watched(tmp_path, life_dir)
    await go_idle(w.idle, w.ticks)
    await w.ink.on_clean_frame(board_photo(), w.ticks.now_s)
    w.ticks.now_s += REFERENCE_MAX_AGE_S + 1.0  # a long quiet: the reference is old
    # One short stroke per report, each under ink_min_ratio; they add up from the reference.
    for strokes in (1, 2):
        await w.report(board_photo(strokes=strokes))
        assert w.board.scene.view == "idle"
        w.ticks.now_s += 30.0
    await w.report(board_photo(strokes=3))
    assert w.board.scene.view == "items" and w.idle.is_holding_off
    await w.idle.tick()
    w.ticks.now_s += 30.0
    await w.report(board_photo(strokes=4))  # more writing keeps holding the view off
    assert w.idle.is_holding_off
    w.ticks.now_s += 30.0
    await w.report(board_photo())  # wiped back to the inkless reference
    assert not w.idle.is_holding_off and len(w.passed_on) == 5  # the agent sees the erase
    await w.idle.tick()
    assert w.board.scene.view == "idle"


async def test_noise_during_or_after_a_hold_never_extends_it_and_wiping_after_is_quiet(
    tmp_path: Path, life_dir: Path
) -> None:
    # Regressions: noise during a hold measured against the board before the ink and
    # extended the hold for good; after the hold, ink left on the board did the same.
    w = Watched(tmp_path, life_dir)
    quiet_s = IdleSettings().ink_quiet_minutes * 60
    await go_idle(w.idle, w.ticks)
    await w.ink.on_clean_frame(board_photo(), w.ticks.now_s)
    await w.report(board_photo(strokes=3))
    await w.idle.tick()
    for specks in (1, 0):
        w.ticks.now_s += quiet_s / 3
        await w.report(board_photo(strokes=3, specks=specks))
    w.ticks.now_s += quiet_s / 3
    await w.idle.tick()
    assert w.board.scene.view == "idle"  # the hold ran out with the ink still there
    # The leftover ink is the board now: new ink on it, wiped back to it, ends that hold.
    await w.report(board_photo(strokes=6))
    assert w.idle.is_holding_off
    await w.report(board_photo(strokes=3))
    assert not w.idle.is_holding_off
    await w.report(board_photo(strokes=3, specks=1))
    await w.report(board_photo())  # wiping the leftover ink isn't new ink either
    await go_idle(w.idle, w.ticks)
    assert w.board.scene.view == "idle" and not w.idle.is_holding_off


async def test_a_calibration_change_mid_hold_never_reads_as_wiped(
    tmp_path: Path, life_dir: Path
) -> None:
    # Regression: the new reference already had the ink, so noise read as a wipe.
    w = Watched(tmp_path, life_dir)
    await go_idle(w.idle, w.ticks)
    await w.ink.on_clean_frame(board_photo(), w.ticks.now_s)
    await w.report(board_photo(strokes=3))
    calibration = object()
    await w.report(board_photo(strokes=3, calibration=calibration))
    await w.report(board_photo(strokes=3, specks=1, calibration=calibration))
    assert w.idle.is_holding_off and w.board.scene.view == "items"
