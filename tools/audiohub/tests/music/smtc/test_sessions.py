"""Tests for audiohub.music.smtc.sessions: picking Spotify's media session over the current one."""

import logging

import pytest

from audiohub.music.smtc import sessions
from audiohub.music.smtc.sessions import pick_session


def test_spotify_session_wins_over_the_current_one(make_manager, edge_and_spotify):
    edge, spotify = edge_and_spotify
    assert pick_session(make_manager([edge, spotify], current=edge)) is spotify


def test_store_build_of_spotify_is_recognised(make_manager, make_session):
    store_spotify = make_session("SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify")
    edge = make_session("MSEdge")
    assert pick_session(make_manager([edge, store_spotify], current=edge)) is store_spotify


def test_without_spotify_the_current_session_is_used(make_manager, make_session):
    edge = make_session("MSEdge")
    assert pick_session(make_manager([edge], current=edge)) is edge


def test_missing_collections_projection_falls_back_with_one_warning(
    make_manager, edge_and_spotify, caplog
):
    edge, spotify = edge_and_spotify
    sessions._warn_sessions_unlisted.cache_clear()
    manager = make_manager([edge, spotify], current=edge, can_list=False)
    with caplog.at_level(logging.WARNING):
        assert pick_session(manager) is edge
        assert pick_session(manager) is edge
    warnings = [record for record in caplog.records if "collections" in record.getMessage()]
    assert len(warnings) == 1


def test_other_missing_modules_still_raise(make_manager):
    manager = make_manager([], current=None)

    def broken_get_sessions():
        raise ModuleNotFoundError("No module named 'other'", name="other")

    manager.get_sessions = broken_get_sessions
    with pytest.raises(ModuleNotFoundError):
        pick_session(manager)
