"""Tests for audiohub.music.smtc.manager: the deferred winrt import and its failure modes."""

import sys
import types

import pytest

from audiohub.music import MusicUnavailable, UnavailableReason
from audiohub.music.smtc.manager import request_session_manager

WINRT_MODULE = "winrt.windows.media.control"


def install_fake_winrt(monkeypatch, request_async) -> None:
    module = types.ModuleType(WINRT_MODULE)
    module.GlobalSystemMediaTransportControlsSessionManager = types.SimpleNamespace(
        request_async=request_async
    )
    monkeypatch.setitem(sys.modules, WINRT_MODULE, module)


@pytest.mark.asyncio
async def test_returns_the_manager_windows_hands_back(monkeypatch):
    manager = object()

    async def request_async():
        return manager

    install_fake_winrt(monkeypatch, request_async)
    assert await request_session_manager() is manager


@pytest.mark.asyncio
async def test_missing_winrt_is_backend_missing(monkeypatch):
    # A None entry in sys.modules makes the import raise ImportError.
    monkeypatch.setitem(sys.modules, WINRT_MODULE, None)
    with pytest.raises(MusicUnavailable, match="aren't available") as error:
        await request_session_manager()
    assert error.value.reason is UnavailableReason.BACKEND_MISSING


@pytest.mark.asyncio
async def test_windows_refusing_is_request_failed(monkeypatch):
    async def request_async():
        raise OSError("RPC server unavailable")

    install_fake_winrt(monkeypatch, request_async)
    with pytest.raises(MusicUnavailable, match="aren't responding") as error:
        await request_session_manager()
    assert error.value.reason is UnavailableReason.REQUEST_FAILED
