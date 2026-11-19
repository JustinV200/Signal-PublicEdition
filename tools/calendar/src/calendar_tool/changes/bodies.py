"""A change's request body, built from fixed keys only, and the words the owner's dialog shows.

No body ever lists attendees, except a reply, which carries the owner's own
entry alone with attendeesOmitted (Google's documented way to change only the
participant's response). Nothing here adds a guest or touches anyone else's.

Each dialog line holds one value, flattened to one line. A new value is shown
in full (the gate refuses a change too long for the dialog), so text the owner
approves can't hide past a cut. An old value is only context, so it's cut with
a count of what's hidden.
"""

from datetime import tzinfo
from typing import Any

from signal_confirm import sanitize_text

from calendar_tool.agenda import NO_TITLE
from calendar_tool.changes.models import EventEdit, NewEvent
from calendar_tool.changes.times import describe_span, edited_span, new_span
from calendar_tool.errors import ApiError, ChangeRefused
from calendar_tool.google_api import marker_properties, own_attendee

# How much of an old value the dialog shows.
MAX_OLD_SHOWN_CHARS = 110


def create_body(new: NewEvent, zone: tzinfo | None) -> dict[str, Any]:
    """The events.insert body: title, times, optional location/description, the tool's marker.

    Raises:
        CalendarError: The times can't be read or are in the wrong order.
    """
    start, end = new_span(new.start, new.end, zone)
    body: dict[str, Any] = {
        "summary": new.title.strip(),
        "start": start,
        "end": end,
        "extendedProperties": marker_properties(),
    }
    if new.location:
        body["location"] = new.location
    if new.description:
        body["description"] = new.description
    return body


def edit_body(
    raw: dict[str, Any], edit: EventEdit, zone: tzinfo | None
) -> tuple[dict[str, Any], list[str]]:
    """The events.patch body for `edit` on `raw`, and the dialog lines for it.

    An old value from Google and its new value go on separate lines ("title was
    ...", "title becomes ..."). Location and description aren't read, so only
    their new text shows. Old values are cut; new ones are shown in full.

    Raises:
        CalendarError: The new times can't be read or are in the wrong order.
    """
    body: dict[str, Any] = {}
    changes: list[str] = []
    if edit.title is not None:
        body["summary"] = edit.title.strip()
        old_title = _shown_old(str(raw.get("summary") or NO_TITLE))
        changes += [f"title was {old_title}", f"title becomes {_shown_new(body['summary'])}"]
    if edit.start is not None or edit.end is not None:
        old = (_value(raw, "start"), _value(raw, "end") or None)
        start, end = edited_span(old, edit.start, edit.end, zone)
        body["start"], body["end"] = _patch_time(start, old[0]), _patch_time(end, old[1])
        before, after = describe_span(old[0], old[1], zone), describe_span(start, end, zone)
        changes += [f"time was {before}", f"time becomes {after}"]
    for key, new_text in (("location", edit.location), ("description", edit.description)):
        if new_text is not None:
            body[key] = new_text
            changes.append(
                f"{key} becomes {_shown_new(new_text)}" if new_text else f"remove the {key}"
            )
    return body, changes


def reply_body(raw: dict[str, Any], response: str) -> dict[str, Any]:
    """The events.patch body that sets only the owner's own response to an invitation.

    Raises:
        ChangeRefused: Nobody else invited him (no invitation to answer).
        ApiError: His attendee entry has no address.
    """
    attendee = own_attendee(raw)
    if attendee is None:
        raise ChangeRefused("Nobody else invited you to this event, so there's nothing to answer.")
    email = attendee.get("email")
    if not isinstance(email, str) or not email:
        raise ApiError("The Calendar API sent your attendee entry without an address.")
    return {"attendees": [{"email": email, "responseStatus": response}], "attendeesOmitted": True}


def _flat(text: str) -> str:
    """`text` flattened to one line, uncut (flattening never lengthens it)."""
    return sanitize_text(text, len(text))


def _shown_new(text: str) -> str:
    """A new value: flattened to one quoted line, in full."""
    # Plain quotes, not repr: repr doubles backslashes, so the owner wouldn't see the exact text.
    return f"'{_flat(text)}'"


def _shown_old(text: str) -> str:
    """An old value: flattened to one quoted line, cut to MAX_OLD_SHOWN_CHARS with a count."""
    flat = _flat(text)
    if len(flat) <= MAX_OLD_SHOWN_CHARS:
        return f"'{flat}'"
    return f"'{flat[:MAX_OLD_SHOWN_CHARS]}' ({len(flat) - MAX_OLD_SHOWN_CHARS} more characters)"


def _value(raw: dict[str, Any], key: str) -> dict[str, Any]:
    """raw[key] when it's an object, else {} (read_moment then reports it unreadable)."""
    value = raw.get(key)
    return value if isinstance(value, dict) else {}


def _patch_time(value: dict[str, str], old: dict[str, Any] | None) -> dict[str, Any]:
    """A start/end for PATCH.

    PATCH merges nested objects, so the key not used is sent as null (else a timed
    event moved to all-day would keep its dateTime too). A timed value keeps the
    old timeZone: Google needs one on a repeating event.
    """
    if "date" in value:
        return {"date": value["date"], "dateTime": None}
    patched: dict[str, Any] = {"dateTime": value["dateTime"], "date": None}
    zone_name = old.get("timeZone") if old else None
    if isinstance(zone_name, str) and zone_name:
        patched["timeZone"] = zone_name
    return patched
