"""Tests for choosing the projector among monitors (fake monitor lists, no hardware)."""

import pytest

from whiteboard.display.screen import Monitor, ProjectorNotFoundError, pick_projector

PRIMARY = Monitor("\\\\.\\DISPLAY5", "PRIMARY", 0, 0, 1920, 1080, True, 1.0)
PROJECTOR = Monitor("\\\\.\\DISPLAY1", "PROJ-1", 1920, 0, 1920, 1080, False, 1.5)
OTHER = Monitor("\\\\.\\DISPLAY2", "SIDE", -1600, 0, 1600, 900, False, 1.0)


def test_name_match_beats_order_and_logical_size_uses_scale() -> None:
    projector = pick_projector([PRIMARY, OTHER, PROJECTOR], "proj-1")
    assert projector is PROJECTOR
    assert projector.logical_size == (1280, 720)


def test_falls_back_to_first_non_primary_then_fails() -> None:
    assert pick_projector([PRIMARY, OTHER], "PROJ-1") is OTHER
    with pytest.raises(ProjectorNotFoundError):
        pick_projector([PRIMARY], "PROJ-1")
