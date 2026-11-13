"""Tests for the brain's event dataclasses."""

import dataclasses

import pytest

from audiohub.brain import ReplyText, TurnDone


def test_events_compare_by_value() -> None:
    assert ReplyText("hi") == ReplyText("hi")
    assert TurnDone(1.0, None, False) == TurnDone(duration_s=1.0, cost_usd=None, is_error=False)


def test_events_are_immutable() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        ReplyText("hi").text = "bye"  # type: ignore[misc]
