"""Shared fixtures for the mail-digest tests."""

import _winapi

import pytest


@pytest.fixture
def lock_file():
    """lock_file(path) opens path with no sharing, so nothing can read it until the test ends."""
    handles = []

    def lock(path):
        handle = _winapi.CreateFile(
            str(path), _winapi.GENERIC_READ, 0, 0, _winapi.OPEN_EXISTING, 0, 0
        )
        handles.append(handle)

    yield lock
    for handle in handles:
        _winapi.CloseHandle(handle)
