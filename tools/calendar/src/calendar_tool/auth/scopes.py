"""The OAuth scopes the calendar tool asks for, and the read-only pair older sign-ins hold.

`calendar.events` lets the tool add, change and delete events on every calendar
the owner can edit; `calendar.calendarlist.readonly` lists his calendars. Sign-ins
saved before the tool could write hold only the read-only pair, so they keep
reading but can't write until `calendar add` runs again.
"""

WRITE_SCOPE = "https://www.googleapis.com/auth/calendar.events"
CALENDAR_LIST_SCOPE = "https://www.googleapis.com/auth/calendar.calendarlist.readonly"

# What `calendar add` asks for (all must be granted, see signal_googleauth.run_browser_flow).
SCOPES = (WRITE_SCOPE, CALENDAR_LIST_SCOPE)

# What a token file without a "scopes" entry was granted (the read-only tool's sign-in).
LEGACY_SCOPES = (
    "https://www.googleapis.com/auth/calendar.events.readonly",
    CALENDAR_LIST_SCOPE,
)
