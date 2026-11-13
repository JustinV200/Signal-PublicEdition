# signal_brief (packages/brief)

The owner's catch-up brief as a library: the event log every producer writes to, the bookmark of what the owner has seen, away mode, presence, the rules for when to offer a brief, the composer and the acks. Stdlib only, plus `signal_untrusted` for the frame and `signal_jsonstate` (`packages/jsonstate`) for the lock and atomic files. Design: `refdocs/research/brief-me.md` (phase 1).

Producers depend only on this package. `tools/brief` puts it in front of Claude sessions (MCP server, CLI, prompt hook).

## State

Everything lives in `tools/brief/.state/` (gitignored); `BriefPaths()` finds it from this package's place in the repo. Every file is read, changed and atomically replaced under one lock, `events.lock` (`msvcrt.locking`, 2 s wait). Readers need no lock.

| File | Holds |
|---|---|
| `events.jsonl` | the log, one entry per line |
| `counters.json` | last seq, each ref letter's count, delivery count, last compaction |
| `bookmark.json` | `through`: the newest seq the owner has seen (only moves forward) |
| `away.json` | `on`, `since` (when it began), `until` (its end), `until_given` (the owner gave the end, else the 3-day default), `note`, `since_seq` (the seq when it began) |
| `presence.json` | `last_human_at`, the due full brief, the morning rule's day |
| `shown.json` | the last 50 deliveries (none over 7 days) and their acks |

## Public API (`from signal_brief import ...`)

- **Log.** `append_entry(paths, NewEntry(kind, title, key, detail, undo, priority, untrusted, source), now) -> Entry`. Kinds in section order: `waiting`, `decision` (needs `undo`), `heads_up`, `new`, `done`. Raises `ValueError` for a bad entry and `BriefLogError` when the state can't be locked or written (producers log it). `resolve_entry`, `current_entries`, `find_entry`, `read_through`.
- **Away.** `away_on(paths, now, until, note)`, `away_off(paths, now) -> held | None`, `away_status(paths, now) -> AwayStatus` (`asleep` from sleepmode's `is_asleep`, `away`, or `here`; it ends an expired away mode first), `parse_until(text, now)`, `held_count`.
- **Composing.** `compose(paths, kind="general") -> Brief`; `render_model(brief, max_chars, titles_only)` and `render_text(brief, max_chars)` return a `Render` with the entries shown and cut. Frame model renders with `signal_untrusted.framed(line, render.body, BRIEF_TAG)`. `entry_model_data(entry)`.
- **Deliveries.** `record_delivery(paths, brief, render, DeliveryOrigin(surface, session_id, due), now)`, `load_deliveries`, `ack_delivery(paths, id, through, now)`, `relayed_through(delivery, replies, bookmark)` (the Claude session ref rule).
- **Triggers.** `on_interaction(paths, now) -> Interaction` (offer `full`, `one_liner` or None, and `gap_one_liner`: whether the 6 h gap rule holds too), `one_liner_text(brief)`. Callers run it only when the owner is present.
- **Presence.** `idle_ms()`: milliseconds since the last input anywhere (`GetLastInputInfo`).

## Layout

`src/signal_brief/`: `paths.py`, `times.py`, `text.py` (the character rule), and the subpackages `store/`, `log/`, `presence/`, `away/`, `compose/`, `deliveries/`, `triggers/`, each with its own README. Dependencies point one way: `store` < `log` < `presence` < `away` < `compose` < `deliveries` < `triggers`.

## Not in phase 1

Weather, schedule and due items, the morning composer, `render_speech`, board data and `brief-cache.json` (the hook composes directly: with no network yet, composing is a local file read), presence marks from the console and hub, and `set_location`.

## Tests

`uv run --frozen --no-sync pytest` covers stable refs and kept unseen entries through compaction, the entry checks, away expiry and the 17:00 day end, the interaction rules (a due brief never expires), the cut rule and the session ref rule.
