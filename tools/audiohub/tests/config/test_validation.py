"""Tests for audiohub.config.validation: per-value type coercion and range checks."""

from dataclasses import dataclass

import pytest

from audiohub.config import ConfigError
from audiohub.config.validation import bounded, build_section, coerce_value, one_of


@dataclass(frozen=True)
class SampleSection:
    name: str = "x"
    count: int = bounded(1, minimum=0, maximum=10)
    ratio: float = 0.5
    is_on: bool = True
    device: str | int | None = None
    tags: tuple[str, ...] = ()
    mode: str = one_of("fast", ("fast", "slow"))


def test_build_section_applies_overrides_and_defaults():
    section = build_section(SampleSection, {"count": 3, "tags": ["a", "b"]}, "sample")
    assert section == SampleSection(count=3, tags=("a", "b"))


@pytest.mark.parametrize("annotation", [int, float])
def test_bool_is_rejected_for_numbers(annotation):
    with pytest.raises(ConfigError, match="got bool"):
        coerce_value(True, annotation, "s.k")


def test_int_is_rejected_for_bool():
    with pytest.raises(ConfigError, match="expected bool"):
        coerce_value(1, bool, "s.k")


@pytest.mark.parametrize("value", ["glasses", 7])
def test_union_accepts_any_member(value):
    assert coerce_value(value, str | int | None, "s.k") == value


def test_union_error_lists_members_without_none():
    with pytest.raises(ConfigError, match="expected str or int, got float"):
        coerce_value(1.5, str | int | None, "s.k")


def test_tuple_needs_an_array():
    with pytest.raises(ConfigError, match="expected array of str, got str"):
        coerce_value("a", tuple[str, ...], "s.k")


def test_tuple_item_error_names_the_position():
    with pytest.raises(ConfigError, match=r"s.k\[1\]: expected str, got int"):
        coerce_value(["a", 2], tuple[str, ...], "s.k")


def test_below_minimum_raises():
    with pytest.raises(ConfigError, match="sample.count: -1 is below the minimum of 0"):
        build_section(SampleSection, {"count": -1}, "sample")


def test_one_of_rejects_an_unlisted_value():
    with pytest.raises(ConfigError, match="sample.mode: 'medium' is not one of fast, slow"):
        build_section(SampleSection, {"mode": "medium"}, "sample")


def test_one_of_default_must_be_a_choice():
    with pytest.raises(ValueError, match="not one of"):
        one_of("other", ("fast", "slow"))


@pytest.mark.parametrize("value", [float("nan"), float("inf")])
def test_non_finite_floats_are_rejected(value):
    with pytest.raises(ConfigError, match="finite"):
        coerce_value(value, float, "s.k")
