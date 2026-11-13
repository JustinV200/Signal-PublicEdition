# signal_brief.away

Away mode (`away.json`).

- `away_on(paths, now, until, note)`: on, or a new end and note while on. No end keeps the one the owner gave earlier, else 3 days from now; an empty note keeps the current one. An expired record that wasn't ended yet is ended properly first.
- `away_off(paths, now)`: off ("I'm back"); returns how many entries were held, or None if it was off.
- `away_status(paths, now) -> AwayStatus`: `asleep` while sleepmode's `is_asleep` is set, `away` while the end is ahead, else `here`. It ends an expired away mode first: after 3 days with no end it logs a `heads_up` ("Away mode ended after 3 days, 14 items held"). Every end marks a full brief due.
- `parse_until(text, now)`: a weekday, "tomorrow" or an ISO date ends at 17:00 that day; an ISO date-time as given.

Depends on: `log`, `presence`, `store`, `text`, `times`.
