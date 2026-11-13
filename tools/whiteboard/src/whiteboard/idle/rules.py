"""The idle view's default rule: show it once the items view has had no items for a while.

The board shows the idle view whenever the items view has had no items (ignoring the
"thinking" box) for `empty_s` seconds (refdocs/research/idle-board/plan.md section 1).
That covers daemon start on an empty scene, board_clear, and `todo hide` onto an empty
board; the delay stops a flicker in clear-then-draw sequences (the task grid, a load).
Under the night view the rule looks at the view the night goes back to, so switching
only changes that (scene.switch_view), and nothing lights up.
"""

from whiteboard.display.scene import ITEMS_VIEW, LOADING_KIND, Scene


def day_view(scene: Scene) -> str:
    """The view shown now, or the one the night view goes back to while it shows."""
    return scene.night.previous_view if scene.night is not None else scene.view


def track_empty(scene: Scene, empty_since: float | None, now_s: float) -> float | None:
    """When the items view became empty, carried from tick to tick.

    Args:
        scene: The scene now.
        empty_since: The last tick's answer (None if it wasn't empty then).
        now_s: Monotonic seconds now.

    Returns:
        None while the (day) view isn't the items or real items are on it; otherwise
        `empty_since`, or `now_s` if it only just became empty.
    """
    has_items = any(item.kind != LOADING_KIND for item in scene.items)
    if has_items or day_view(scene) != ITEMS_VIEW:
        return None
    return empty_since if empty_since is not None else now_s


def should_go_idle(empty_since: float | None, now_s: float, empty_s: float) -> bool:
    """Whether the items view has been empty long enough to switch to the idle view.

    Args:
        empty_since: From track_empty.
        now_s: Monotonic seconds now.
        empty_s: [idle] empty_s.
    """
    return empty_since is not None and now_s - empty_since >= empty_s
