"""POST /api/models: an index picks from fixed lists; a bad pick or a refusing file writes nothing.

The fixture's model files live in its tmp folder, never the repo's real settings.
"""

import json

import pytest

from signal_console.models import pick_options


@pytest.mark.parametrize(
    ("body", "status", "voice_file"),
    [
        (
            {"target": "voice", "field": "effort", "index": 2},
            200,
            {"model": None, "effort": pick_options("voice", "effort")[2]},
        ),
        ({"target": "voice", "field": "model", "index": 99}, 400, None),
        ({"target": "voice", "field": "model", "index": True}, 400, None),
        ({"target": "voice", "field": "model", "index": "opus"}, 400, None),
        ({"target": "settings", "field": "env", "index": 0}, 400, None),
        # The orchestrator's settings file doesn't exist in the fixture: refused, not created.
        ({"target": "orchestrator", "field": "model", "index": 1}, 409, None),
    ],
)
async def test_model_pick(console, body, status, voice_file):
    files = console.services.models

    response = await console.client.post("/api/models", json=body, headers=console.page_headers())

    assert response.status == status
    assert not files.settings.exists()
    if voice_file is None:
        assert not files.brain_choice.exists()
    else:
        assert json.loads(files.brain_choice.read_text(encoding="utf-8")) == voice_file
