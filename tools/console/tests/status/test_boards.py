"""read_board_status: offline without the daemon's files; saves and view mapped when it answers."""

import json
from pathlib import Path

import aiohttp
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
    assert status.saves == [] and status.view is None


async def test_saves_and_view_come_from_the_daemon(tmp_path: Path):
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
    app.router.add_get("/api/status", guarded({"view": "todo"}))
    async with TestServer(app, host="127.0.0.1") as server:
        (tmp_path / WHITEBOARD_DAEMON_FILE).write_text(json.dumps({"port": server.port}))
        (tmp_path / WHITEBOARD_TOKEN_FILE).write_text(TOKEN)
        async with aiohttp.ClientSession() as session:
            status = await read_board_status(session, tmp_path)
    assert status.online is True
    assert status.view == "todo"
    # A missing or empty description both mean "none saved".
    assert [(save["name"], save["description"]) for save in status.saves] == [
        ("a", "notes"),
        ("b", None),
        ("c", None),
    ]
