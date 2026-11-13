"""POST /api/hook/turn refuses a malformed report with 400 and records nothing."""

import json
import math
import time

import pytest

from signal_console.local_api import HOOK_TURN_PATH
from signal_console.paths import LOCAL_KEY_HEADER

GOOD = {"phase": "start", "session_id": "s1", "at": 1_000.0}


@pytest.mark.parametrize(
    "bad",
    [
        {"phase": "pause"},
        {"session_id": ""},
        {"session_id": "s" * 129},
        {"at": True},
        {"at": math.nan},
        {"at": "now"},
        {"at": time.time() + 60},  # from the future
        {"background_tasks": -1},
        {"background_tasks": True},
    ],
)
async def test_bad_turn_report_is_refused_and_not_recorded(console, bad):
    # json.dumps writes NaN as a bare token, which the server's json.loads accepts.
    response = await console.client.post(
        HOOK_TURN_PATH,
        data=json.dumps(GOOD | bad),
        headers={LOCAL_KEY_HEADER: console.services.local_key, "Content-Type": "application/json"},
    )

    assert response.status == 400
    assert console.status.turn_reports == []
