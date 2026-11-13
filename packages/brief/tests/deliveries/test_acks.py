"""Tests for what an ack may cover: the cut rule, the session ref rule, and ack_delivery."""

from signal_untrusted import frame
from support import at, log, make_paths

from signal_brief import (
    BRIEF_TAG,
    DeliveryOrigin,
    ack_delivery,
    away_off,
    away_on,
    compose,
    load_deliveries,
    read_through,
    record_delivery,
    relayed_through,
    render_model,
)
from signal_brief.presence import read_presence


def test_a_cut_render_acks_only_up_to_its_oldest_cut_new_entry(tmp_path) -> None:
    paths = make_paths(tmp_path)
    log(paths, "waiting", "Approve the purchase", at(20, 9))  # seq 1, W1
    first = compose(paths)
    seen = record_delivery(paths, first, render_model(first), DeliveryOrigin("session"), at(20, 9))
    assert ack_delivery(paths, seen.id, seen.through, at(20, 9)) == 1

    for hour in (10, 11, 12):
        log(paths, "done", f"Finished task number {hour}", at(20, hour))  # seqs 2, 3, 4
    brief = compose(paths)
    # One character short of everything: the lowest-ranked item, the oldest done (seq 2), goes.
    whole = len(frame(render_model(brief, titles_only=True).body, BRIEF_TAG))
    render = render_model(brief, max_chars=whole - 1, titles_only=True)
    assert [e.seq for e in render.shown] == [1, 4, 3] and [e.seq for e in render.cut] == [2]

    delivery = record_delivery(paths, brief, render, DeliveryOrigin("session"), at(20, 13))
    assert delivery.through == 1  # just before seq 2
    assert ack_delivery(paths, "b-0000000000.99", 99, at(20, 13)) is None  # unknown: nothing
    assert ack_delivery(paths, delivery.id, 99, at(20, 13)) == 1  # capped at its through
    assert read_through(paths) == 1


def test_only_an_ack_of_a_delivery_given_since_the_due_drops_it(tmp_path) -> None:
    paths = make_paths(tmp_path)
    log(paths, "waiting", "Approve the purchase", at(20, 9))
    brief = compose(paths)
    old = record_delivery(paths, brief, render_model(brief), DeliveryOrigin("session"), at(20, 13))
    away_on(paths, at(20, 13, 30), None)
    away_off(paths, at(20, 14))  # marks a full brief due at 14:00

    ack_delivery(paths, old.id, old.through, at(20, 14, 2))  # given at 13:00, before the due
    assert read_presence(paths).due is not None
    late = record_delivery(
        paths, brief, render_model(brief), DeliveryOrigin("session"), at(20, 14, 1)
    )
    ack_delivery(paths, late.id, late.through, at(20, 14, 2))
    assert read_presence(paths).due is None


def test_session_replies_ack_only_through_the_oldest_unrelayed_ref(tmp_path) -> None:
    paths = make_paths(tmp_path)
    log(paths, "waiting", "Approve the purchase", at(20, 9))  # seq 1, W1, seen below
    first = compose(paths)
    seen = record_delivery(paths, first, render_model(first), DeliveryOrigin("session"), at(20, 9))
    ack_delivery(paths, seen.id, seen.through, at(20, 9))
    log(paths, "decision", "Picked port 8790 for the console", at(20, 10))  # seq 2, D1
    log(paths, "new", "Grade posted for statistics", at(20, 11))  # seq 3, N1
    brief = compose(paths)
    delivery = record_delivery(
        paths, brief, render_model(brief), DeliveryOrigin("session"), at(20, 12)
    )
    bookmark = read_through(paths)

    # W1 is an old wait, so leaving it out doesn't hold the ack back.
    full = ["Here's your brief:\n- D1: the console now uses port 8790\n- N1: statistics grade"]
    assert relayed_through(delivery, full, bookmark) == 3
    # N1 named bare, without any of its title words, isn't relayed: stop just before it.
    bare = ["D1: the console moved to port 8790. Also N1."]
    assert relayed_through(delivery, bare, bookmark) == 2
    assert relayed_through(delivery, ["Noted D1, N1 and W1."], bookmark) is None
    # Only the already-seen wait passed on: nothing new was, so no ack (and the due stays).
    assert relayed_through(delivery, ["W1: approve the purchase."], bookmark) is None
    # A render with room for W1 alone cuts every new entry: relaying W1 still acks nothing.
    room = len(frame(render_model(first, titles_only=True).body, BRIEF_TAG)) + len(', "more": 2')
    hidden = render_model(brief, max_chars=room, titles_only=True)
    assert [entry.ref for entry in hidden.shown] == ["W1"]
    record_delivery(paths, brief, hidden, DeliveryOrigin("session"), at(20, 12))
    hid = load_deliveries(paths)[-1]  # read back, so cut_new must survive shown.json
    assert relayed_through(hid, ["W1: approve the purchase."], bookmark) is None
