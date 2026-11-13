# whiteboard.todo.source

Reads todos from the owner's KB, and ticks one back.

## Reading

- `find_week_plans(life_dir, today)`: this week's and next week's `life/terms/<term>/weeks/<Monday>-to-<Sunday>/plan.md`, those that exist. `week_folder_name(day)` gives `2026-10-19-to-10-25` for any day of that week.
- `read_week_entries(life_dir, today)` → `(entries, plans)`, this week's entries first.
- `parse_plan(markdown, path, week_monday)` → `PlanEntry` per todo line (`- [ ] [tag] text (due ...)` or `- [x] ...`):
  - `section`: `SECTION_OVERDUE` under `## Overdue`, `SECTION_OF_NOTE` under `## Of note` (or any `## ... of note`), else `SECTION_OTHER`. `###` headings stay in their section.
  - `id`: a hash of the tag and the shown text, so ticking the box or editing the due note keeps it. Two lines with the same tag and text (e.g. under Overdue and under the course, or carried into next week) are one item. Except a recurring item: when those lines are due on two or more dates outside Overdue (`Reading (due Tue)`, `Reading (due Thu)`), each dated line's id adds its date (`split_recurring`, run by `read_week_entries`), and an Overdue copy with one of those dates joins that day's line. An undated copy of a recurring item keeps the plain id and shows as its own row.
  - `due` (`due.py`): `(due 2026-10-21 08:30)`, `(due 2026-10-21)`, `(was due ...)`, `(were due d1, d2; ...)` (first date), and `(due Thu)` / `(due Thursday 17:00)` in the plan's own week. Notes after `;` are ignored. A due note whose date can't be read gives no date but still leaves the shown text.
  - `source`: the file, 0-based line number and exact line, for edits.
- `find_entries(entries, ref, by_text=True)`: every line of the one item named by its id or a unique piece of `[tag] text` (`by_text=False`: the id only). `TodoLookupError` otherwise.

## Writing (plan_edit.py)

`set_line_done(source, is_done, life_dir)` flips the `[ ]`/`[x]` mark of one line, and nothing else:
- only files named `plan.md` (callers pass only this and next week's plans) that resolve to a place inside `life_dir`, so a symlink or junction under `life/terms` can't point the write elsewhere;
- the stored line must still be at its line number, or appear exactly once in the file; otherwise `PlanEditError` and the file is untouched;
- line endings and a UTF-8 BOM are kept; the file is replaced atomically (`whiteboard.shared.write_atomically`), and only if it still holds the bytes that were read, so an edit the owner saves meanwhile is never lost.

## Depends on

`whiteboard.shared`, the standard library.
