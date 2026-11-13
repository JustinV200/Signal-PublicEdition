"""The console's voice pick, applied between turns: a model change goes live, an effort change
reconnects resuming the conversation, an unknown value changes nothing, and a failed
reconnect fails only that request."""

import json

import pytest

from audiohub.brain import ReplyText, TurnDone
from audiohub.config import BrainSettings

DONE = TurnDone(duration_s=1.0, cost_usd=0.01, is_error=False)
CONVERSATION_ID = "conv-1"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("pick", "expected_sessions", "expected_models_set", "second_session_settings"),
    [
        ({"model": "opus"}, 1, ["opus"], None),
        ({"effort": "high"}, 2, [], BrainSettings(model="sonnet", effort="high")),
        # Both at once: the reconnect opens with the new model, so no set_model is needed.
        ({"model": "haiku", "effort": "medium"}, 2, [], BrainSettings("haiku", "medium")),
        ({"model": "gpt-5", "effort": "max"}, 1, [], None),  # unlisted: ignored
    ],
)
async def test_pick_is_applied_before_the_next_request(
    brain_kit, tmp_path, pick, expected_sessions, expected_models_set, second_session_settings
) -> None:
    choice_path = tmp_path / "brain-choice.json"
    harness = brain_kit.Harness(
        [[ReplyText("one"), DONE], [ReplyText("two"), DONE]], choice_path=choice_path
    )
    async with harness.brain as brain:
        await brain_kit.collect(brain.ask("first"))
        first = harness.session
        first.session_id = CONVERSATION_ID  # what the CLI's turn result carried
        choice_path.write_text(json.dumps(pick), encoding="utf-8")  # the owner picks in the console

        second = await brain_kit.collect(brain.ask("second"))

    assert second == [ReplyText("two"), DONE]
    assert first.settings == BrainSettings()  # opened with the defaults: sonnet, low
    assert len(harness.sessions) == expected_sessions
    assert first.models_set == expected_models_set
    if second_session_settings is not None:
        assert first.disconnect_count == 1
        assert harness.session.resumed == CONVERSATION_ID
        assert harness.session.settings == second_session_settings
        assert harness.session.sent == ["second"]


@pytest.mark.asyncio
async def test_a_failed_reconnect_fails_that_request_and_the_next_one_starts_afresh(
    brain_kit, tmp_path
) -> None:
    choice_path = tmp_path / "brain-choice.json"
    harness = brain_kit.Harness(
        [[ReplyText("one"), DONE], [ReplyText("three"), DONE]], choice_path=choice_path
    )
    async with harness.brain as brain:
        await brain_kit.collect(brain.ask("first"))
        harness.session.session_id = CONVERSATION_ID
        choice_path.write_text(json.dumps({"effort": "high"}), encoding="utf-8")
        harness.failing_connects = 1

        with pytest.raises(RuntimeError, match="didn't start"):
            await brain_kit.collect(brain.ask("second"))
        third = await brain_kit.collect(brain.ask("third"))

    assert third == [ReplyText("three"), DONE]
    retry = harness.session
    assert len(harness.sessions) == 3
    assert retry.resumed is None  # the resume that failed isn't tried again
    assert retry.settings.effort == "high"
    assert retry.sent == ["third"]
