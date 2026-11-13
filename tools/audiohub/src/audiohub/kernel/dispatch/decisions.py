"""Strict parsing of Sonnet's JSON reply into `Decision`s.

Structural problems (bad JSON, wrong shape, repeated ids) raise
`DecisionError` so the dispatcher falls back to the deterministic policy. A
decision for an id that isn't pending (Sonnet re-deciding a message it saw
in the delivered history) is skipped with a warning, and a pending id Sonnet
left out is delivered verbatim. A reply with no decision for any pending id
(empty, or only unknown ids) answered some other question, so it raises too.
The parsed decisions then go through `safeguards.apply_safeguards`, which
enforces the kernel's fixed rules (order, urgent, holds, drops, condensing).
"""

import json
import logging
import re
from typing import Any

from ..messages import ACTIONS, Decision
from .prompt import DecisionRequest
from .safeguards import apply_safeguards

logger = logging.getLogger(__name__)

REQUIRED_KEYS = frozenset({"id", "action", "reason"})
ALLOWED_KEYS = REQUIRED_KEYS | {"text"}
MISSING_REASON = "kernel: not mentioned by the dispatcher, delivered verbatim"

# Sonnet sometimes wraps JSON in a markdown fence despite being told not to.
# Unwrapping one fence is harmless; anything else around the JSON is an error.
_FENCE = re.compile(r"\A```(?:json)?\s*\n(?P<body>.*)\n```\Z", re.DOTALL)


class DecisionError(ValueError):
    """Sonnet's reply was not a valid decision object; the fallback must be used."""


def parse_decisions(raw_reply: str, request: DecisionRequest) -> list[Decision]:
    """Turn Sonnet's raw reply into one checked decision per pending message.

    Args:
        raw_reply: The model's full text reply.
        request: The request it answered (pending ids, history, word limit).

    Returns:
        One decision per pending message, after the safeguards, in speaking
        order. A message the model left out is delivered verbatim.

    Raises:
        DecisionError: If the reply is not the expected JSON object, names the
            same id twice, or decides no pending id at all.
    """
    decisions = _parse_entries(_load_object(raw_reply), {m.id for m in request.pending})
    decided_ids = {decision.message_id for decision in decisions}
    for message in request.pending:
        if message.id not in decided_ids:
            logger.warning("dispatcher left out %s; delivering it verbatim", message.id)
            decisions.append(Decision(message.id, "deliver", None, MISSING_REASON))
    return apply_safeguards(decisions, request)


def _load_object(raw_reply: str) -> dict[str, Any]:
    """Parse the reply text as a JSON object, unwrapping one markdown fence."""
    text = raw_reply.strip()
    fenced = _FENCE.match(text)
    if fenced:
        text = fenced.group("body").strip()
    try:
        data = json.loads(text)
    except (ValueError, RecursionError) as error:
        # RecursionError: absurdly deep nesting. JSONDecodeError is a ValueError.
        raise DecisionError(f"reply is not valid JSON: {error}") from error
    if not isinstance(data, dict) or set(data) != {"decisions"}:
        raise DecisionError('reply must be an object with exactly one key, "decisions"')
    return data


def _parse_entries(data: dict[str, Any], pending_ids: set[str]) -> list[Decision]:
    """Check every entry of the "decisions" list and convert it to a `Decision`."""
    entries = data["decisions"]
    if not isinstance(entries, list):
        raise DecisionError('"decisions" must be a list')
    decisions: list[Decision] = []
    seen_ids: set[str] = set()
    for entry in entries:
        decision = _parse_entry(entry)
        if decision.message_id not in pending_ids:
            # Usually a message already delivered: stale, not a reason to
            # distrust the decisions for the messages that are pending.
            logger.warning("dispatcher decided unknown id %r; ignoring it", decision.message_id)
            continue
        if decision.message_id in seen_ids:
            raise DecisionError(f"id {decision.message_id!r} decided more than once")
        seen_ids.add(decision.message_id)
        decisions.append(decision)
    if not decisions:
        # A reply about no pending id (e.g. the warm-up's empty list) answered
        # some other request; trust the fallback, not its silence.
        raise DecisionError("no decision for any pending id")
    return decisions


def _parse_entry(entry: Any) -> Decision:
    """Validate one entry's keys and types."""
    if not isinstance(entry, dict):
        raise DecisionError("each decision must be an object")
    keys = set(entry)
    if not keys >= REQUIRED_KEYS or not keys <= ALLOWED_KEYS:
        raise DecisionError(f"decision keys must be {sorted(ALLOWED_KEYS)}, got {sorted(keys)}")
    message_id, action, reason = entry["id"], entry["action"], entry["reason"]
    text = entry.get("text")
    if not isinstance(message_id, str) or not isinstance(reason, str):
        raise DecisionError("decision id and reason must be strings")
    if action not in ACTIONS:
        raise DecisionError(f"unknown action {action!r}")
    if text is not None and not isinstance(text, str):
        raise DecisionError("decision text must be a string or null")
    # Only a delivery can carry replacement text, and blank text would erase
    # the message, so both cases fall back to the original words.
    if action != "deliver" or (text is not None and not text.strip()):
        text = None
    return Decision(message_id=message_id, action=action, text=text, reason=reason)
