"""Public API of signal_brief: the brief's event log, away mode, presence, composer and acks.

Producers log with append_entry (a failed append raises BriefLogError, which they
log). tools/brief builds the MCP server, CLI and prompt hook on the rest.
"""

from signal_brief.away import AwayStatus, away_off, away_on, away_status, held_count, parse_until
from signal_brief.compose import (
    BRIEF_ID_HASH_CHARS,
    BRIEF_TAG,
    MAX_HOOK_CHARS,
    Brief,
    Render,
    compose,
    entry_model_data,
    render_model,
    render_text,
)
from signal_brief.deliveries import (
    Delivery,
    DeliveryOrigin,
    ack_delivery,
    load_deliveries,
    record_delivery,
    relayed_through,
)
from signal_brief.log import (
    KINDS,
    PRIORITIES,
    Entry,
    NewEntry,
    append_entry,
    current_entries,
    find_entry,
    read_through,
    resolve_entry,
)
from signal_brief.paths import BriefPaths
from signal_brief.presence import idle_ms
from signal_brief.store import BriefLogError
from signal_brief.text import ERROR_QUOTE_CHARS, strip_forbidden
from signal_brief.times import local_now, to_iso
from signal_brief.triggers import Interaction, on_interaction, one_liner_text

__all__ = [
    "BRIEF_ID_HASH_CHARS",
    "BRIEF_TAG",
    "ERROR_QUOTE_CHARS",
    "KINDS",
    "MAX_HOOK_CHARS",
    "PRIORITIES",
    "AwayStatus",
    "Brief",
    "BriefLogError",
    "BriefPaths",
    "Delivery",
    "DeliveryOrigin",
    "Entry",
    "Interaction",
    "NewEntry",
    "Render",
    "ack_delivery",
    "append_entry",
    "away_off",
    "away_on",
    "away_status",
    "compose",
    "current_entries",
    "entry_model_data",
    "find_entry",
    "held_count",
    "idle_ms",
    "load_deliveries",
    "local_now",
    "on_interaction",
    "one_liner_text",
    "parse_until",
    "read_through",
    "record_delivery",
    "relayed_through",
    "render_model",
    "render_text",
    "resolve_entry",
    "strip_forbidden",
    "to_iso",
]
