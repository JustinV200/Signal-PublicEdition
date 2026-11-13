# whiteboard.todo.view

What the TODO view shows, where, and what changed since the last sync.

## Public API

- `build_groups(entries, today, hidden_ids)` (`sections.py`) → `TodoGroup(key, label, rows, folded)` in order:
  1. Overdue (`GROUP_OVERDUE`): everything in `## Overdue` that's undated or past due (a line re-dated to today or later shows on that day), plus any open item whose due day has passed wherever it sits. Only open items at most `OVERDUE_RECENT_DAYS` (7) late show, newest first, `MAX_OVERDUE_ROWS` (5) at most; the rest (older, undated, past the cap) go in `folded` and the label says `Overdue · +2 older`. Items in the group done today follow the open ones.
  2. `Today · Mon 19 Oct`, `Tomorrow · Tue 20 Oct`, then `This week` (the rest of `WINDOW_DAYS`, 7, ahead), by date and time, untimed last on a day.
  3. Work items of note: `## Of note` items due after the window or undated. An of-note item due inside the window shows on its day.
  Anything else is left out: done and past due outside Overdue, further out, or undated. When one item is placed twice, the later line wins (next week's copy of a carried item). Each `GroupRow` has a `title` (`short_title`) and a `due_label` (`labels.py`): `3d late` in Overdue, the time today and tomorrow, `Wed 14:30` this week, `Wed 4 Nov` in of note.
- `short_title(text)` (`titles.py`): the row's title, by code: struck-through done parts, parentheticals over 12 characters and trailing source tags (`SOURCE_TAGS`: `(site)`, `(mail)`, `(email)`, `(cal)`, `(web)`) dropped; other short notes like `(attend)` stay. A title still over 40 characters is cut at its first `, `, `; `, `: ` or dash that keeps 20 to 40 characters, else at the last space within 40, ending in `…`. "" if all of it was struck through.
- `labels.py`: the group keys, `DONE_LABEL` ("✓ done", shown in place of a done row's due text), `day_label`, `long_day_label`, `due_label`.
- `track(entries, previous, today)` (`tracking.py`) → `TrackResult(tracking, done_ids, hidden_ids, newly_done)`:
  - an item is done if any of its lines is ticked;
  - `done_since` remembers the first day a sync saw it done; from the next day it's hidden (the daily refresh);
  - `newly_done` is what was open at the last sync and is done now: the page animates those;
  - an item first seen already done counts as done today, without animation.
- `TodoStore(path)`: keeps `DoneTracking` in `.state/todo.json`. An unreadable file is logged and starts fresh.
- `layout_todo(groups, (width, height), keynotes=())` (`layout.py`) → `TodoLayout`: header, the keynotes block under it (fixed 22 px lines, when there are keynotes), body, `Metrics`, `HeadingPlace`s and `RowPlace`s in board pixels. One column unless its font would drop under 18 px, then two; at 14 px in two columns the tail is cut and a `+N more` line added. Each row knows where its text starts (`text_x`), its room (`text_w`), and its estimated rendered width (`ink_w`, from the title's character count) for strike checks.
- `WEEKDAYS`, `MONTHS`: the short English day and month names the labels use (the idle view shares them).
- `build_payload(layout, header, done_ids, hint_ids)` (`payload.py`): the page's JSON (see `static/todo.js`): rows carry the title, a done row's due text is `DONE_LABEL`, and `keynotes` is `{label, lines, font_px, x, y, w, h}` or null. `tag_color(tag)` picks from `TAG_COLORS` by a hash of the tag, so a course keeps its colour.

## Depends on

`whiteboard.todo.source`, the standard library.
