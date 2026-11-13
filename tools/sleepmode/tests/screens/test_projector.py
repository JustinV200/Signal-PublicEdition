"""Tests for keeping the projector out of the displays that get darkened."""

from support.fakes import PRIMARY

from sleepmode.screens import split_projector


def test_single_display_has_no_projector_and_is_darkened() -> None:
    assert split_projector([PRIMARY], "PROJ-1") == (None, [PRIMARY])
