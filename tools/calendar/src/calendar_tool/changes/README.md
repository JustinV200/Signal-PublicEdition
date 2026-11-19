# calendar_tool.changes

Adds, changes, deletes and answers events, one Calendar write each, behind the owner's gate.

## Public API

- `EventChanges(client, gate, zone=None)`:
  - `create(NewEvent) -> AgendaEvent`: on a calendar he can edit, with the tool's private marker, no attendees, `sendUpdates=none`. Never asks.
  - `update(EventRef, EventEdit) -> AgendaEvent`: title, times, location or description only, `sendUpdates=none`. A new start alone keeps the length; a timed value keeps the old `timeZone` (repeating events need one).
  - `delete(EventRef)`: the event, the one occurrence, or the series. `sendUpdates=none`.
  - `respond(EventRef, response)`: `accepted`, `declined` or `tentative`. It sends only the owner's own attendee entry with `attendeesOmitted`, and `sendUpdates=all` (`REPLY_SEND_UPDATES`) so the organizer gets the answer by email, as with Google Calendar's own buttons.
  - Update, delete and respond re-read the event first, pass the gate, and write with the re-read etag as `If-Match`.
- `NewEvent(title, start, end="", calendar_id="primary", location="", description="")`, `EventEdit(title, start, end, location, description)` (None keeps a field), `EventRef(calendar_id, event_id, is_series=False)`: the checked inputs. `RESPONSES`.
- `ChangeGate(is_enabled, ask=signal_confirm.confirm, zone=None)`: `check(target, changes)` returns at once for the tool's own events, skips the dialog when `is_enabled` is false unless the change covers a whole series, and otherwise raises `ChangeRefused` unless the owner clicks Allow. `dialog_text(...)` is the dialog body: the event, a line when other people are on it, then each change, with an old value and its new value on separate lines. Every new value is shown in full; an old one is cut past 110 characters with a count of the rest. A dialog longer than `MAX_DIALOG_CHARS` (2000, `signal_confirm`'s own limit, past which it cuts the middle) is refused with `ChangeRefused` before asking, so nothing is changed. `MAX_NEW_TEXT_CHARS` (850) is the new text that always fits, for the model's tool description.
- `Settings(changes_confirm=True)`, `load_settings(path)`: `.state/calendar.toml`'s `[changes] confirm`. The file is optional; an unknown section or key raises `SetupError`.

Times: `YYYY-MM-DD` is all-day, anything else an ISO date-time, local when it has no offset. All-day ends are exclusive.

## Files

- `models.py`: the inputs and their checks.
- `times.py`: parsing, keeping the length, and times in words for the dialog.
- `target.py`: `load_target`, the re-read and the occurrence-or-series choice.
- `bodies.py`: the request bodies and the dialog's change lines.
- `gate.py`: `ChangeGate` and the dialog text.
- `settings.py`: the config file.
- `writes.py`: `EventChanges`.

## Depends on

`calendar_tool.agenda` (`normalize_event`, `NO_TITLE`), `calendar_tool.google_api`, `calendar_tool.errors`, `signal_confirm`.
