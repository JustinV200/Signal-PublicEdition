"""Tests for on_interaction's rules: morning, a due brief that never expires, the gap
one-liner, away."""

from datetime import timedelta

from support import at, log, make_paths

from signal_brief import (
    DeliveryOrigin,
    ack_delivery,
    away_off,
    away_on,
    compose,
    on_interaction,
    record_delivery,
    render_model,
)
from signal_brief.presence import read_presence


def test_morning_marks_a_full_brief_due_until_an_ack(tmp_path) -> None:
    paths = make_paths(tmp_path)
    log(paths, "new", "Grade posted", at(20, 2))

    assert on_interaction(paths, at(20, 3)).offer == "one_liner"  # first ever: a gap
    first = on_interaction(paths, at(20, 8))
    assert first.offer == "full" and first.due.reason == "morning"
    assert on_interaction(paths, at(20, 8, 5)).offer == "full"  # still due

    brief = compose(paths)
    delivery = record_delivery(
        paths, brief, render_model(brief), DeliveryOrigin("session"), at(20, 8, 6)
    )
    ack_delivery(paths, delivery.id, delivery.through, at(20, 8, 7))
    log(paths, "new", "Another grade", at(20, 8, 30))
    assert on_interaction(paths, at(20, 9)).offer is None  # morning rule spent for the day


def test_a_due_brief_never_expires_unseen(tmp_path) -> None:
    paths = make_paths(tmp_path)
    away_on(paths, at(20, 12), None)
    log(paths, "waiting", "Approve the purchase", at(20, 12, 30))
    away_off(paths, at(20, 13))  # marks a full brief due at 13:00

    late = on_interaction(paths, at(21, 19))  # 30 h on, outside the morning window
    assert late.offer == "full" and late.due.reason == "away_end"
    assert on_interaction(paths, at(21, 19, 1)).offer == "full"  # offering it didn't drop it
    assert read_presence(paths).due is not None


def test_while_away_only_the_gap_one_liner_for_what_is_unseen_and_not_given_since(
    tmp_path,
) -> None:
    paths = make_paths(tmp_path)
    away_on(paths, at(19, 20), None)
    assert on_interaction(paths, at(20, 8)).offer is None  # nothing logged: nothing to offer

    log(paths, "waiting", "Approve the purchase", at(20, 9))
    assert on_interaction(paths, at(20, 10)).offer is None  # under 6 h since 08:00
    away_offer = on_interaction(paths, at(20, 10) + timedelta(hours=6))
    assert away_offer.offer == "one_liner"  # no morning or due rules while away

    # A "brief me" given since the owner's last interaction reached the newest item: no one-liner.
    brief = compose(paths)
    asked = record_delivery(
        paths, brief, render_model(brief), DeliveryOrigin("session"), at(20, 16, 1)
    )
    assert on_interaction(paths, at(20, 22, 1)).offer is None
    # Once seen, an open wait alone gives no one-liner after a gap, though it's still listed.
    ack_delivery(paths, asked.id, asked.through, at(20, 22, 2))
    later = on_interaction(paths, at(21, 4, 2))
    assert later.offer is None and later.brief.items

    # A relay that left the newest item out acks only up to it, so the delivery
    # didn't give that item: it still gets the one-liner after a gap.
    log(paths, "new", "Grade posted", at(21, 4, 3))
    log(paths, "new", "Another grade", at(21, 4, 4))
    brief = compose(paths)
    relayed = record_delivery(
        paths, brief, render_model(brief), DeliveryOrigin("session"), at(21, 4, 5)
    )
    ack_delivery(paths, relayed.id, relayed.through - 1, at(21, 4, 6))
    assert on_interaction(paths, at(21, 10, 3)).offer == "one_liner"
