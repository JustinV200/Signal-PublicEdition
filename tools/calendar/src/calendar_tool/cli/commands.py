"""The `calendar` read and setup handlers: setup, add, agenda, sync-cache, mcp.

Each takes the parsed argparse namespace and returns an exit code.
CalendarErrors propagate to main(), which prints them as one line.
"""

import argparse
import json
from datetime import datetime

from calendar_tool.agenda import (
    AgendaEvent,
    agenda_payload,
    describe_sync_status,
    fetch_agenda,
    record_sync_status,
    sync_cache,
)
from calendar_tool.auth import load_client, open_client, sign_in
from calendar_tool.errors import CalendarError
from calendar_tool.google_api import CalendarClient
from calendar_tool.mcp_server import run_stdio_server
from calendar_tool.paths import (
    CACHE_PATH,
    CLIENT_SECRETS_PATH,
    SYNC_STATUS_PATH,
    TOKEN_PATH,
    TOOL_ROOT,
)

EXIT_OK = 0
EXIT_BAD_CLIENT = 2
SETUP_STEPS = """\
Calendar tool setup. The full click-path is {setup_doc}

1. In the mail tool's Google Cloud project, enable the Google Calendar API.
2. Google Auth Platform > Data Access: add the scopes calendar.events and
   calendar.calendarlist.readonly.
3. Sign in once (a browser opens; Advanced > Go to ... on the unverified-app warning):
   uv run --project tools/calendar calendar add
   A sign-in from before the tool could change events still reads; run add again to write.
"""


def build_client() -> CalendarClient:
    """A client over the stored sign-in (tests replace this).

    Raises:
        SetupError, ReauthRequired: No client file, no sign-in, or an undecryptable token.
    """
    return open_client(CLIENT_SECRETS_PATH, TOKEN_PATH)


def run_setup(args: argparse.Namespace) -> int:
    """`calendar setup`: print the steps, then the client file and sign-in status."""
    print(SETUP_STEPS.format(setup_doc=TOOL_ROOT / "SETUP.md"))
    try:
        client = load_client(CLIENT_SECRETS_PATH)
    except CalendarError as error:
        print(f"OAuth client file: PROBLEM. {error}")
        return EXIT_BAD_CLIENT
    print(f"OAuth client file: OK (project {client.project_id or 'unknown'}).")
    signed_in = "yes" if TOKEN_PATH.is_file() else "not yet (step 3)"
    print(f"Signed in: {signed_in}.")
    print(f"Last sync: {describe_sync_status(SYNC_STATUS_PATH)}.")
    return EXIT_OK


def add(args: argparse.Namespace) -> int:
    """`calendar add [--email ADDRESS]`: browser sign-in for the calendar scopes, then save it."""
    email = sign_in((CLIENT_SECRETS_PATH, TOKEN_PATH), args.email)
    print(f"Saved the calendar sign-in for {email}.")
    return EXIT_OK


def agenda(args: argparse.Namespace) -> int:
    """`calendar agenda [--days N] [--json]`: print the upcoming events with their ids."""
    now = datetime.now().astimezone()
    events, skipped = fetch_agenda(build_client(), now, args.days)
    if args.json:
        payload = agenda_payload(events, now, skipped, is_detailed=True)
        print(json.dumps(payload, indent=1, ensure_ascii=False))
        return EXIT_OK
    if skipped:
        print(f"Couldn't read: {', '.join(skipped)}.")
    if not events:
        print(f"Nothing in the next {args.days} days.")
    for event in events:
        print(agenda_line(event))
    return EXIT_OK


def sync(args: argparse.Namespace) -> int:
    """`calendar sync-cache`: rewrite .state/agenda.json for the idle board.

    The outcome also goes to .state/sync_status.json, since the scheduled run has no stderr.
    """
    now = datetime.now().astimezone()
    try:
        count, skipped = sync_cache(build_client(), CACHE_PATH, now)
    except CalendarError as error:
        record_sync_status(SYNC_STATUS_PATH, now, error)
        raise
    record_sync_status(SYNC_STATUS_PATH, now, skipped=skipped)
    print(f"Wrote {count} events to {CACHE_PATH}.")
    return EXIT_OK


def serve_mcp(args: argparse.Namespace) -> int:
    """`calendar mcp`: run the stdio MCP server until stdin closes."""
    run_stdio_server()
    return EXIT_OK


def agenda_line(event: AgendaEvent) -> str:
    """'Tue 21 Oct  09:00  Title  [calendar]  (flags)  id ID --calendar CALENDAR_ID'.

    The flags are mine, repeats and "invite: <response>", when they apply.

    The id and calendar id are what `calendar update/delete/respond` take.
    """
    when = "all day" if event.is_all_day else event.starts_at.strftime("%H:%M")
    flags = [
        name
        for name, is_set in (("mine", event.is_mine), ("repeats", event.is_recurring))
        if is_set
    ]
    if event.invite:
        flags.append(f"invite: {event.invite}")
    marks = f"  ({', '.join(flags)})" if flags else ""
    where = f"id {event.event_id} --calendar {event.calendar_id}"
    return (
        f"{event.starts_at:%a %d %b}  {when:<7}  {event.title}  [{event.calendar}]{marks}  {where}"
    )
