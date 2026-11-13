"""Session models: the hook records every session (newest 20), PostModelSwitch updates one,
and the strip shows the claimed session's model by the id its turn hooks report."""

import json

from conftest import tmp_model_files

from signal_console.hooks.session import record_from_hook
from signal_console.models import models_state
from signal_console.paths import SESSION_MODELS_FILE


def _hook(state_dir, event, session_id, at, **fields):
    raw = json.dumps({"hook_event_name": event, "session_id": session_id, **fields})
    return record_from_hook(raw.encode(), state_dir, at)


def _now(tmp_path, session_id):
    files = tmp_model_files(tmp_path)
    return models_state(files, session_id, "medium", is_claimed=True)["orchestrator"]["now"]


def test_newest_20_sessions_are_kept(tmp_path):
    for number in range(25):
        assert _hook(tmp_path, "SessionStart", f"s{number}", float(number), model="claude-opus-5-5")

    sessions = json.loads((tmp_path / SESSION_MODELS_FILE).read_text(encoding="utf-8"))
    assert sorted(sessions, key=lambda s: int(s[1:])) == [f"s{n}" for n in range(5, 25)]


def test_post_model_switch_updates_and_a_late_session_start_does_not_undo_it(tmp_path):
    _hook(tmp_path, "SessionStart", "claimed", 1.0, model="claude-opus-5-5")
    _hook(tmp_path, "SessionStart", "other", 1.5, model="claude-haiku-5-5")
    _hook(tmp_path, "PostModelSwitch", "claimed", 3.0, to_model="claude-sonnet-5-5")
    # Async hooks land out of order: an older SessionStart arrives last.
    assert not _hook(tmp_path, "SessionStart", "claimed", 2.0, model="claude-opus-5-5")

    assert _now(tmp_path, "claimed") == {"model": "claude-sonnet-5-5", "effort": "medium"}
    assert _now(tmp_path, "other")["model"] == "claude-haiku-5-5"


def test_an_odd_or_missing_model_is_never_recorded(tmp_path):
    assert not _hook(tmp_path, "SessionStart", "s1", 1.0)  # SessionStart sometimes omits it
    assert not _hook(tmp_path, "SessionStart", "s1", 1.0, model="Opus <script>")
    assert _now(tmp_path, "s1") == {"model": None, "effort": "medium"}  # "model unknown"
