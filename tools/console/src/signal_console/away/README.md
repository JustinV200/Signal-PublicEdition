# away

The Devices page's Away/Here toggle. Away mode belongs to the brief (`packages/brief`, `signal_brief`): while it's on, sessions hold their news for the owner and a full brief is due when it ends.

- `away_payload(paths, now)`: `{state: here|away|asleep, endsAt, note}` (`asleep` comes from sleepmode).
- `set_away(paths, now, is_on, until="")`: `away_on` with `parse_until(until)` (a weekday, `tomorrow`, an ISO date or date-time; empty means the brief's 3-day default), or `away_off`. Raises `ValueError` for a bad end and `BriefLogError` when the state can't be written.

This is the owner's own control, so unlike every other console button it acts directly instead of asking the orchestrator. It runs only from the page's `POST /api/away`, behind the login token and origin checks.

Depends on: `signal_brief`.
