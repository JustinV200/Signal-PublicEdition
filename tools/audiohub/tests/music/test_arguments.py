"""Tests for audiohub.music.arguments: volume, query and search-kind checks."""

import pytest

from audiohub.music import check_query, check_search_kind, check_volume_percent


@pytest.mark.parametrize("percent", [0, 100])
def test_volume_in_range_is_returned(percent):
    assert check_volume_percent(percent) == percent


@pytest.mark.parametrize("percent", [-1, 101])
def test_volume_out_of_range_is_rejected(percent):
    with pytest.raises(ValueError, match="between 0 and 100"):
        check_volume_percent(percent)


@pytest.mark.parametrize("percent", [True, 50.0, "50"])
def test_volume_must_be_a_plain_int(percent):
    with pytest.raises(ValueError, match="whole number"):
        check_volume_percent(percent)


def test_query_is_stripped():
    assert check_query("  babydoll ") == "babydoll"


def test_blank_query_is_rejected():
    with pytest.raises(ValueError, match="empty"):
        check_query("   ")


def test_unknown_search_kind_is_rejected():
    with pytest.raises(ValueError, match="track, album, playlist, artist"):
        check_search_kind("podcast")
