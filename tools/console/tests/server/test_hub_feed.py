"""The hub feed drops speech with no wake phrase and shows a burst of one error once."""

from signal_console.paths import HUB_FILE, HUB_LOG_FILE
from signal_console.server import EventHub
from signal_console.server.hub_feed import HubFeed
from signal_console.state_files import write_json

ERROR = "2026-10-23 07:00:50,211 ERROR audiohub.loop.voice_output: could not play a chunk"


def test_ignored_speech_and_repeat_errors_never_reach_the_feed(tmp_path):
    write_json(tmp_path / HUB_FILE, {"pid": 1, "createTime": 1.0})
    log_path = tmp_path / HUB_LOG_FILE
    log_path.write_text("", encoding="utf-8")
    events = EventHub(tmp_path / "history.jsonl")
    feed = HubFeed(events, tmp_path)
    feed.read()  # the replay of what was there at start

    lines = [
        '[21:58:32.0] heard: "private chat" (1.0 s audio, stt 63 ms)',
        "[21:58:32.0] ignored: no wake phrase",
        ERROR,
        ERROR,
        '[21:59:12.6] heard: "Pull up my to-do list." (2.0 s audio, stt 360 ms)',
    ]
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    feed.read()
    feed.read()  # nothing new: the held "heard" line now stands

    texts = [data["text"] for name, data in events.history() if name == "voice"]
    assert texts == ["error: could not play a chunk", "Pull up my to-do list."]
