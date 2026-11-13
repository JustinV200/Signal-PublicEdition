"""Tests for the UserPromptSubmit hook: presence gating, once-per-session injection, acks."""

import io
import json
import sys

from signal_brief import (
    DeliveryOrigin,
    away_on,
    compose,
    load_deliveries,
    read_through,
    record_delivery,
    render_model,
)
from support import Transcript, at, log, make_paths, run_hook

from brief_tool.hooks import prompt
from brief_tool.mcp_server.app import SERVER_NAME
from brief_tool.wording import HOOK_BRIEF_LINE


def test_the_brief_is_injected_once_per_session_and_due_not_per_append(tmp_path) -> None:
    paths = make_paths(tmp_path)
    log(paths, "decision", "Picked port 8790 for the console", at(20, 2))
    one, two = Transcript(tmp_path / "s1.jsonl"), Transcript(tmp_path / "s2.jsonl")

    text, decision = run_hook(paths, one.path, at(20, 8))  # the morning rule marks it due
    assert decision.startswith("full,") and text.startswith(HOOK_BRIEF_LINE.split("{")[0])
    assert "D1" in text and "Picked port 8790" in text

    log(paths, "new", "Grade posted for statistics", at(20, 8, 1))  # a new brief id
    assert run_hook(paths, one.path, at(20, 8, 2)) == (None, "full:already,acked=0")
    other, _ = run_hook(paths, two.path, at(20, 8, 3), session_id="s2")
    assert "N1" in other  # another session still gets it, once
    assert [d.session_id for d in load_deliveries(paths)] == ["s1", "s2"]

    # Claude never relayed it, so an hour on s1 gets it again (with what's new), once.
    log(paths, "waiting", "Approve the purchase", at(20, 10))
    text, decision = run_hook(paths, one.path, at(20, 14, 30))
    assert decision == "full,acked=0" and "W1" in text
    assert run_hook(paths, one.path, at(20, 14, 31)) == (None, "full:already,acked=0")


def test_the_next_present_prompt_acks_only_what_claude_passed_on(tmp_path) -> None:
    paths = make_paths(tmp_path)
    log(paths, "decision", "Picked port 8790 for the console", at(20, 2))  # seq 1, D1
    log(paths, "new", "Grade posted for statistics", at(20, 3))  # seq 2, N1
    transcript = Transcript(tmp_path / "s1.jsonl")
    text, _ = run_hook(paths, transcript.path, at(20, 8))
    # Look-alike attachments (another hook name, another kind) don't place the delivery.
    transcript.hook_context(text, hook_name="prompt.mention")
    transcript.hook_context(text, kind="hook_success")
    transcript.reply("Your brief: D1, the console now uses port 8790. N1 too.")
    assert run_hook(paths, transcript.path, at(20, 8, 4))[1] == "full:already,acked=0"
    transcript.hook_context(text)
    transcript.reply("Your brief: D1, the console now uses port 8790. N1 too.")

    _, decision = run_hook(paths, transcript.path, at(20, 8, 5))
    assert decision == "none,acked=1"  # the ack dropped the due brief
    assert read_through(paths) == 1  # N1 was named without any of its title words


def test_brief_me_ids_count_only_from_brief_me_results(tmp_path) -> None:
    paths = make_paths(tmp_path)
    log(paths, "new", "Grade posted for statistics", at(20, 13))
    run_hook(paths, tmp_path / "none.jsonl", at(20, 13, 5))  # spend the gap one-liner
    brief = compose(paths)
    delivery = record_delivery(
        paths, brief, render_model(brief), DeliveryOrigin("session"), at(20, 14)
    )
    transcript = Transcript(tmp_path / "s1.jsonl")
    transcript.prompt(f"Here's an old one: {delivery.id}")
    transcript.tool_call("t1", "mcp__mail__mail_read", f"mail quoting {delivery.id}")
    transcript.reply("N1: your statistics grade is posted.")
    assert run_hook(paths, transcript.path, at(20, 14, 5))[1] == "none,acked=0"

    transcript.tool_call("t2", f"mcp__{SERVER_NAME}__brief_me", f"Signal brief {delivery.id} ...")
    # Only assistant text counts as a reply: a prompt or tool result saying it doesn't.
    transcript.prompt("N1: your statistics grade is posted.")
    transcript.tool_call("t3", "mcp__mail__mail_read", "N1: your statistics grade is posted.")
    assert run_hook(paths, transcript.path, at(20, 14, 6))[1] == "none,acked=0"
    transcript.reply("N1: your statistics grade is posted.")
    assert run_hook(paths, transcript.path, at(20, 14, 7))[1] == "none,acked=1"


def test_a_morning_after_last_nights_brief_then_a_gap(tmp_path) -> None:
    paths = make_paths(tmp_path)
    log(paths, "new", "Grade posted for statistics", at(19, 22))  # N1
    transcript = Transcript(tmp_path / "s1.jsonl")
    run_hook(paths, transcript.path, at(19, 23))  # the owner's last prompt of the night
    brief = compose(paths)
    night = record_delivery(
        paths, brief, render_model(brief), DeliveryOrigin("session"), at(19, 23, 1)
    )
    transcript.tool_call("t1", f"mcp__{SERVER_NAME}__brief_me", f"Signal brief {night.id} ...")
    transcript.reply("N1: your statistics grade is posted.")
    log(paths, "decision", "Picked port 8790 for the console", at(20, 2))  # D1, overnight
    log(paths, "waiting", "Approve the purchase", at(20, 3))  # W1, overnight

    # The 08:00 prompt acks last night's brief first; the morning brief must still fire.
    text, decision = run_hook(paths, transcript.path, at(20, 8))
    assert decision == "full,acked=1" and "D1" in text and "W1" in text

    transcript.hook_context(text)
    transcript.reply("Your brief: D1, the console now uses port 8790. W1 needs your OK.")
    # Back at 15:00, this prompt acks the morning brief through D1 only (W1 came without a
    # title word). The gap one-liner still fires for W1: the injection showed it, stamped
    # the same second as the owner's 08:00 prompt, but an acked delivery reaches only its ack.
    assert run_hook(paths, transcript.path, at(20, 15))[1] == "one_liner,acked=1"


def test_presence_gating_and_the_5_second_caveat(tmp_path) -> None:
    paths = make_paths(tmp_path)
    log(paths, "new", "Grade posted for statistics", at(20, 13))
    path = tmp_path / "s1.jsonl"
    assert run_hook(paths, path, at(20, 13, 1), idle_ms=5001)[1] == "skip:idle"
    assert (
        run_hook(paths, path, at(20, 13, 1), event={"prompt": "<peer>hi</peer>"})[1]
        == "skip:tagged"
    )
    assert run_hook(paths, path, at(20, 13, 1), event={"agent_id": "a1"})[1] == "skip:agent"
    managed = {"SIGNAL_BRIEF_SURFACE": "managed"}
    assert run_hook(paths, path, at(20, 13, 1), environ=managed)[1] == "skip:managed"
    # Caveat: input within 5 s counts, so a plain (untagged) peer message that lands just
    # after the owner typed elsewhere is taken for the owner's own prompt and gets the one-liner.
    text, decision = run_hook(paths, path, at(20, 13, 2), idle_ms=4999)
    assert decision == "one_liner,acked=0" and text
    # The VS Code extension's file/selection context ahead of the owner's own prompt isn't a tag.
    ide = {"prompt": "<ide_opened_file>x</ide_opened_file>\n<ide_selection>y</ide_selection> fix"}
    assert run_hook(paths, path, at(20, 13, 3), event=ide)[1] == "none,acked=0"


def test_away_rules_reach_every_prompt_and_the_log_never_has_prompt_text(
    tmp_path, monkeypatch, capsys
) -> None:
    paths = make_paths(tmp_path)
    away_on(paths, at(20, 9), None)
    monkeypatch.setattr(prompt, "BriefPaths", lambda: paths)
    monkeypatch.setattr(prompt, "local_now", lambda: at(20, 10))
    monkeypatch.setattr(prompt, "idle_ms", lambda: 60_000)
    monkeypatch.setenv("SIGNAL_BRIEF_SURFACE", "managed")
    event = {"session_id": "s1", "prompt": "my secret plan", "transcript_path": "x"}
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(json.dumps(event).encode())))

    assert prompt.main() == 0
    output = json.loads(capsys.readouterr().out)["hookSpecificOutput"]
    assert output["hookEventName"] == "UserPromptSubmit"
    assert "the owner is away" in output["additionalContext"]  # the away rules
    hook_log = (paths.state_dir / "hook.log").read_text()
    assert "session=s1 decision=skip:managed" in hook_log and "secret" not in hook_log

    # Garbage input fails open: exit 0, no output, the error's type logged.
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(b"\xff{not json")))
    assert prompt.main() == 0
    assert capsys.readouterr().out == ""
    assert "decision=error:JSONDecodeError" in (paths.state_dir / "hook.log").read_text()
