# whiteboard.idle.sources

Each idle region's data from its source. Pure over text already read or bodies already fetched, except `read_agenda`, which reads its one small JSON file.

## Public API

- `today_rows(groups, today, done_ids, labels)` (`plan_items.py`): TODAY from `todo.view.build_groups`, with its short titles. The 2 newest overdue items (`OVERDUE_SLOTS`), then today's items, then the next days' open items until 6 rows. Items ticked before today are hidden; one ticked today stays (`done`, struck through, due column `✓ done`) and gives way first to any open row. Due column: `3d late`, the time or `today`, then `Wed` or `4 Nov`.
- `overdue_count(groups, done_ids)` (`plan_items.py`): every open overdue item, shown or folded, for the TODAY heading.
- `upcoming_items(entries, today, last_day, labels)` (`plan_items.py`): open dated plan items after today up to the window's end, as `DatedItem`s; titled with `short_title`, and a time goes into the title unless it already has it, and 23:59 counts as no time.
- `read_agenda(path, now, last_day)` (`agenda.py`): tools/calendar's `.state/agenda.json` (`{updated, events: [{start, end, all_day, title, calendar}]}`) as `DatedItem`s with the "Cal" chip. A missing, invalid or stale (over 2 h) file gives `[]`; a bad event is skipped; ended events drop off; a multi-day event that began earlier shows on today. Titles go through `clean_text` (80 characters). Raises `StateFileError` only when the file exists but can't be read.
- `upcoming_rows(items, today)` (`upcoming.py`): both sources merged by day then time (untimed last), with the day column (`Today`, `Wed`, `4 Nov`).
- `read_priorities(markdown, week_monday, today, labels)` (`priorities.py`): the first 3 numbered lines under `## Priorities` whose `(due ...)` notes aren't all before today (a line without one always counts), due notes taken out, the rest through `short_title` (a line that's all struck-through done parts is skipped), `[tag]` as the chip.
- `agents_region(groups)`, `usage_line(usage)` (`agents.py`): needs-you tasks first, then by % done; queued and done only counted. The usage line is null with no usage data.
- `parse_headlines(body, now)` (`news.py`): the first `MAX_HEADLINES` (6) RSS 2.0 `<item>`s or Atom `<entry>`s, in feed order, with a title and a date in the last 24 h (no date counts as fresh); a repeated title is skipped. Refuses (`NewsError`) a body over `MAX_FEED_BYTES` (512 KB), any DOCTYPE, or non-XML; each title goes through `clean_text` (140 characters).
