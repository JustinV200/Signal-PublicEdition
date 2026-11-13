# whiteboard.idle

The idle view's logic: the board's default when nothing is drawn (clock, date, weather, today's tasks, the week's priorities, agent tasks, upcoming dates, a news ticker). Free of the daemon, the camera and the web server; `whiteboard.daemon.idle` wires it to the board and `display/static/idle/` draws it. Every region is picked by a fixed rule; no model is called anywhere (refdocs/research/idle-board/plan.md and design.md).

## Public API (`from whiteboard.idle import ...`)

- Rules (`rules.py`):
  - `track_empty(scene, empty_since, now_s)`: when the items view became empty (the "thinking" box doesn't count), carried tick to tick; None when items are drawn or another view shows. Under the night view it looks at the view the night goes back to.
  - `should_go_idle(empty_since, now_s, empty_s)`: empty for `empty_s` ([idle] empty_s, 10 s).
  - `day_view(scene)`: the view shown, or the one under the night view.
- Chips (`chips.py`): `parse_tag_labels(["tag=Label", ...])`, `chip(tag, labels)` → `{label, color}` (the TODO view's `tag_color`; unlabelled tags title-cased), `CALENDAR_CHIP` ("Cal", grey).
- Sources (`sources/`, see its README): `today_rows`, `overdue_count`, `upcoming_items`, `upcoming_rows`, `DatedItem`, `read_priorities`, `read_agenda`, `agents_region`, `usage_line`, `parse_headlines`, `NewsError`, `MAX_FEED_BYTES`, `MAX_HEADLINES`.
- `clean_text(raw, max_chars)` (`text.py`): outside text made one safe line (tags stripped, unescaped, control and format characters dropped, whitespace collapsed, capped with an ellipsis).

## The page payload

`{usage, weather, tasks, overdue, notes, keynotes, agents, upcoming, news}`:

- `usage`: `{five_hour, week, agents}` (whole percents or null) or null.
- `weather`: `{code, is_day, temp, hi, lo, rain, word, place, as_of}` or null; `as_of` (HH:MM) only on a stale cached reading.
- `tasks`: `[{id, chip, text, due, when: overdue|today|later, done}]` (`text` is the short title); `overdue`: every open overdue item, shown or not, for the heading; `notes`: `[{chip, text}]`; `keynotes`: today's lines (`[]` when stale or missing), shown in the priorities' place; `upcoming`: `[{day, today, chip, text}]`.
- `agents`: `{active: [{name, pct, status, you}], queued, done}`; `news`: `{headlines, source, px_s}` (the ticker's headlines in feed order, its source label and speed in design px a second) or null.

## Depends on

`whiteboard.display.scene` (views), `whiteboard.todo` (plan parsing, grouping, tracking, tag colours), `signal_tasks` (types), `signal_jsonstate` (the agenda read).
