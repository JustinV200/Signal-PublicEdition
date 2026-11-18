"""read_board_status: offline without the daemon's files; saves, view and item count mapped
when it answers (an older build with no count, or junk, reads as unknown)."""

import json
from pathlib import Path

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from signal_console.status import read_board_status
from signal_console.status.whiteboard_api import (
    TOKEN_HEADER,
    WHITEBOARD_DAEMON_FILE,
    WHITEBOARD_TOKEN_FILE,
)

TOKEN = "whiteboard-token-for-tests"


async def test_no_daemon_file_means_offline(tmp_path: Path):
    async with aiohttp.ClientSession() as session:
        status = await read_board_status(session, tmp_path)
    assert status.online is False
    assert status.saves == [] and status.view is None and status.item_count is None


@pytest.mark.parametrize(
    ("daemon_status", "item_count"),
    [
        ({"view": "todo", "item_count": 3}, 3),
        ({"view": "todo", "item_count": 0}, 0),
        ({"view": "todo"}, None),
        ({"view": "todo", "item_count": True}, None),
        ({"view": "todo", "item_count": -1}, None),
        ({"view": "todo", "item_count": "3"}, None),
    ],
)
async def test_saves_view_and_count_come_from_the_daemon(
    tmp_path: Path, daemon_status: dict, item_count: int | None
):
    metas = [
        {"name": "a", "created_at": "2026-01-01", "description": "notes"},
        {"name": "b", "created_at": "2026-01-02", "description": ""},
        {"name": "c", "created_at": "2026-01-03"},
    ]

    def guarded(payload: dict):
        async def handler(request: web.Request) -> web.Response:
            if request.headers.get(TOKEN_HEADER) != TOKEN:
                raise web.HTTPUnauthorized
            return web.json_response(payload)

        return handler

    app = web.Application()
    app.router.add_get("/api/saves", guarded({"saves": metas}))
    app.router.add_get("/api/status", guarded(daemon_status))
    async with TestServer(app, host="127.0.0.1") as server:
        (tmp_path / WHITEBOARD_DAEMON_FILE).write_text(json.dumps({"port": server.port}))
        (tmp_path / WHITEBOARD_TOKEN_FILE).write_text(TOKEN)
        async with aiohttp.ClientSession() as session:
            status = await read_board_status(session, tmp_path)
    assert status.online is True
    assert status.view == "todo"
    assert status.item_count == item_count
    # A missing or empty description both mean "none saved".
    assert [(save["name"], save["description"]) for save in status.saves] == [
        ("a", "notes"),
        ("b", None),
        ("c", None),
    ]
