"""The idle view's default rule, and how the idle view sits among the other views."""

from pathlib import Path

import pytest

from whiteboard.display.scene import (
    Scene,
    SceneStore,
    hide_night,
    item_from_dict,
    show_drawn_items,
    show_night,
    switch_view,
)
from whiteboard.idle import should_go_idle, track_empty

TEXT = item_from_dict({"id": "t1", "kind": "text", "x": 0, "y": 0, "w": 9, "h": 9, "content": "x"})
LOADING = item_from_dict({**vars(TEXT), "id": "loading", "kind": "loading", "style": {}})
EMPTY_S = 10.0


@pytest.mark.parametrize(
    ("scene", "empty_since", "now_s", "goes_idle"),
    [
        (Scene(), None, 100.0, False),  # just became empty: the timer starts
        (Scene(), 90.0, 100.0, True),  # empty for 10 s
        (Scene(items=(LOADING,)), 90.0, 100.0, True),  # the thinking box doesn't count
        (Scene(items=(TEXT,)), 90.0, 100.0, False),  # something drawn
        (Scene(view="todo"), 90.0, 100.0, False),  # another view showing
        (show_night(Scene(), 1), 90.0, 100.0, True),  # under the night: items beneath
        (show_night(Scene(view="todo"), 1), 90.0, 100.0, False),
    ],
)
def test_items_view_empty_for_ten_seconds_goes_idle(
    scene: Scene, empty_since: float | None, now_s: float, goes_idle: bool
) -> None:
    since = track_empty(scene, empty_since, now_s)
    assert should_go_idle(since, now_s, EMPTY_S) is goes_idle


def test_idle_yields_to_drawing_and_waits_under_the_night(tmp_path: Path) -> None:
    idle = switch_view(Scene(), "idle")
    assert show_drawn_items(idle, [LOADING]).view == "idle"
    assert show_drawn_items(idle, [TEXT]).view == "items"
    # Under the night the rule only changes the view the night goes back to.
    night = switch_view(show_night(Scene(), 1), "idle")
    assert (night.view, night.night.previous_view) == ("night", "idle")
    assert hide_night(night).view == "idle"
    # Older code rejects "idle", so scene.json keeps the items there instead.
    store = SceneStore(tmp_path / "scene.json")
    store.save(night)
    assert store.load().night.previous_view == "items"
    store.save(idle)
    assert store.load().view == "items"
