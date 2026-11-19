"""What a raw Calendar API event says about itself: the tool's marker, repeats, guests, invites.

The marker is a *private* extended property, which Google keeps on one
calendar's copy of an event only. Whoever sends the owner an invite can't set
it on his copy. Anyone who can write to the same calendar can, though (as can
another app using the key "signal"), so it's a convenience, not a boundary
against co-writers.
"""

from typing import Any

MARKER_KEY = "signal"
MARKER_VALUE = "1"


def marker_properties() -> dict[str, Any]:
    """The extendedProperties value that marks a new event as the tool's own."""
    return {"private": {MARKER_KEY: MARKER_VALUE}}


def is_tool_event(raw: dict[str, Any]) -> bool:
    """True when the event carries the tool's private marker."""
    properties = raw.get("extendedProperties")
    private = properties.get("private") if isinstance(properties, dict) else None
    return isinstance(private, dict) and private.get(MARKER_KEY) == MARKER_VALUE


def is_recurring(raw: dict[str, Any]) -> bool:
    """True for an occurrence of a repeating series, or the series itself."""
    return bool(raw.get("recurringEventId") or raw.get("recurrence"))


def own_attendee(raw: dict[str, Any]) -> dict[str, Any] | None:
    """The owner's own attendee entry when someone else invited him, else None.

    An event he organises himself isn't an invitation, even when he's on its guest list.
    """
    organizer = raw.get("organizer")
    if isinstance(organizer, dict) and organizer.get("self") is True:
        return None
    attendees = raw.get("attendees")
    if not isinstance(attendees, list):
        return None
    for attendee in attendees:
        if isinstance(attendee, dict) and attendee.get("self") is True:
            return attendee
    return None


def has_guests(raw: dict[str, Any]) -> bool:
    """True when people other than the owner are on the event.

    Needs no addresses, and doesn't rely on Google setting attendeesOmitted when
    maxAttendees cuts the list (that counts too). Any attendee list counts, even one
    holding only the owner's own entry, so the dialog's Guests line errs towards
    showing, on purpose.
    """
    attendees = raw.get("attendees")
    return raw.get("attendeesOmitted") is True or (isinstance(attendees, list) and bool(attendees))


def invite_response(raw: dict[str, Any]) -> str | None:
    """The owner's response to someone else's invite (needsAction, accepted, ...), else None."""
    attendee = own_attendee(raw)
    status = attendee.get("responseStatus") if attendee else None
    return status if isinstance(status, str) else None
