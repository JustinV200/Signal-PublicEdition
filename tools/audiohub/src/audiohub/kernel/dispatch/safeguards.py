"""The kernel's fixed rules: a fast path that skips Sonnet, and overrides on its decisions.

Fast path (`fast_path_decisions`, checked before Sonnet is asked): when every
pending message is urgent or a direct reply of at most `max_spoken_words`
words that isn't code-heavy, or the only pending message is such a short,
plain message from anyone that doesn't repeat the delivered history, all of
them are delivered at once, verbatim, in speaking order. Sonnet's 2-8 s per
decision is too slow for spoken replies, and it has nothing to condense or
drop there. They still enter the delivered history, so later decisions see
them.

Overrides (`apply_safeguards`, after parsing). Sonnet only advises on
condensing and dropping; these rules are enforced in code so that no reply,
mistaken or prompt-injected, can lose, bury, delay or rewrite a message:
- deliveries are spoken in `speaking_order`, whatever order Sonnet listed;
- urgent messages are always delivered, verbatim;
- a hold is delivered verbatim: the hub only asks when the user is free to
  hear, so holding would only make a message late;
- a drop stands only if its reason names a delivered message (from the history
  Sonnet was shown, or a delivery in this same batch) whose original text the
  dropped message repeats exactly (whitespace and a trailing "." or "!" aside);
- condensed text is used only for long or code-heavy messages, and only when
  it is actually shorter.
"""

import logging
import re
from collections.abc import Mapping, Sequence

from ..messages import Decision, DeliveredRecord, OutboundMessage, word_count
from .fallback import speaking_order
from .prompt import DecisionRequest, shown_history
from .text_checks import is_code_heavy, is_near_duplicate

logger = logging.getLogger(__name__)

# TODO: move this tunable to KernelSettings once audiohub.config is free to edit.
FAST_PATH_ENABLED = True

URGENT_REASON = "kernel: urgent messages are always delivered verbatim"
HOLD_REASON = "kernel: the user is free to hear it, held message delivered"
UNJUSTIFIED_DROP_REASON = "kernel: drop names no delivered near-duplicate, delivered instead"
REFUSED_CONDENSE_NOTE = " (kernel: condensed text refused, spoken verbatim)"
FAST_PATH_REASON = "kernel fast path: delivered verbatim without Sonnet"


def fast_path_decisions(
    pending: Sequence[OutboundMessage],
    recent_delivered: Sequence[DeliveredRecord],
    max_spoken_words: int,
) -> list[Decision] | None:
    """Decide without Sonnet when the fast-path rule allows it.

    Args:
        pending: Every pending message, oldest arrival first.
        recent_delivered: What the user already heard, oldest first.
        max_spoken_words: The longest message that may skip Sonnet.

    Returns:
        Verbatim deliveries in speaking order if every pending message is
        urgent or a short, plain direct reply, or if the only pending message
        is short, plain and not a repeat of the history; otherwise None (ask
        Sonnet).
    """
    if not FAST_PATH_ENABLED or not pending:
        return None
    is_all_fast = all(
        m.priority == "urgent" or (m.is_direct_reply and _is_plain_short(m, max_spoken_words))
        for m in pending
    )
    is_lone_fresh_note = (
        len(pending) == 1
        and _is_plain_short(pending[0], max_spoken_words)
        and not any(is_near_duplicate(pending[0].text, r.message.text) for r in recent_delivered)
    )
    if not (is_all_fast or is_lone_fresh_note):
        return None
    return [Decision(m.id, "deliver", None, FAST_PATH_REASON) for m in speaking_order(pending)]


def apply_safeguards(decisions: Sequence[Decision], request: DecisionRequest) -> list[Decision]:
    """Enforce the kernel's rules on one decision per pending message.

    Args:
        decisions: Parsed decisions, one per pending message, in Sonnet's order.
        request: The request they answer.

    Returns:
        The corrected decisions, in `speaking_order` of their messages.
    """
    messages = {message.id: message for message in request.pending}
    references = _drop_references(decisions, request, messages)
    by_id = {
        d.message_id: _enforce(d, messages[d.message_id], references, request.max_spoken_words)
        for d in decisions
    }
    # Speaking order is mechanical, so code sets it, not Sonnet.
    return [by_id[m.id] for m in speaking_order(request.pending) if m.id in by_id]


def _is_plain_short(message: OutboundMessage, max_spoken_words: int) -> bool:
    """True if the message is within the word limit and not code-heavy."""
    return word_count(message.text) <= max_spoken_words and not is_code_heavy(message.text)


def _drop_references(
    decisions: Sequence[Decision],
    request: DecisionRequest,
    messages: Mapping[str, OutboundMessage],
) -> dict[str, str]:
    """Original texts a drop may point at: the shown history plus this batch's deliveries."""
    references = {record.message.id: record.message.text for record in shown_history(request)}
    for decision in decisions:
        if decision.action == "deliver":
            references[decision.message_id] = messages[decision.message_id].text
    return references


def _enforce(
    decision: Decision,
    message: OutboundMessage,
    references: Mapping[str, str],
    max_spoken_words: int,
) -> Decision:
    """Apply every rule to one decision and return the decision that stands."""
    if message.priority == "urgent":
        if decision.action == "deliver" and decision.text is None:
            return decision
        return _deliver_verbatim(decision, URGENT_REASON)
    if decision.action == "drop" and not _is_justified_drop(decision, message, references):
        return _deliver_verbatim(decision, UNJUSTIFIED_DROP_REASON)
    if decision.action == "hold":
        return _deliver_verbatim(decision, HOLD_REASON)
    if decision.text is not None:
        if not _may_condense(message, decision.text, max_spoken_words):
            return _deliver_verbatim(decision, decision.reason + REFUSED_CONDENSE_NOTE)
        _log_if_over_limit(decision, max_spoken_words)
    return decision


def _is_justified_drop(
    decision: Decision, message: OutboundMessage, references: Mapping[str, str]
) -> bool:
    """True if the reason names a delivered message whose text this one repeats."""
    named_ids = [
        reference_id
        for reference_id in references
        if reference_id != message.id and _names_id(decision.reason, reference_id)
    ]
    return any(is_near_duplicate(message.text, references[rid]) for rid in named_ids)


def _may_condense(message: OutboundMessage, condensed: str, max_spoken_words: int) -> bool:
    """True if replacing the message's text with `condensed` is allowed."""
    is_excessive = word_count(message.text) > max_spoken_words or is_code_heavy(message.text)
    return is_excessive and len(condensed) < len(message.text)


def _deliver_verbatim(decision: Decision, reason: str) -> Decision:
    """Override a decision with a verbatim delivery, logging what was overridden."""
    logger.warning(
        "overriding dispatcher on %s (%s, %r): %s",
        decision.message_id,
        decision.action,
        decision.reason,
        reason,
    )
    return Decision(decision.message_id, "deliver", None, reason)


def _log_if_over_limit(decision: Decision, max_spoken_words: int) -> None:
    """Accepted condensed text may still run long; keep it but leave a trace."""
    words = word_count(decision.text or "")
    if words > max_spoken_words:
        logger.warning(
            "condensed text for %s is %d words (limit %d); keeping it",
            decision.message_id,
            words,
            max_spoken_words,
        )


def _names_id(reason: str, message_id: str) -> bool:
    """True if `reason` mentions `message_id` as a whole token ("m1" not inside "m12")."""
    return re.search(rf"(?<![A-Za-z0-9]){re.escape(message_id)}(?![A-Za-z0-9])", reason) is not None
