# mail_digest.rollover

Starts each new week in `life/` by code, with no model involved. The digest and the assignment checker run it first thing (`steps.roll_week`), so the week's first digest already reads, edits and emails the new week, and the whiteboard sync after it shows that week. `mail-digest rollover` runs it by hand (`digest/rollover_cli.py`).

## What it does

If today's week (`terms/<term>/weeks/<Monday>-to-<Sunday>/`) has no `plan.md`, it takes the newest earlier plan across every term and writes, in this order:

1. The new week's `workspace/README.md` (one line), `log.md` and `review.md`, from the week templates with every `<date>` filled in: `life/templates/week-plan.md`, `week-log.md` and `week-review.md` if you made them, else the built-in defaults in `templates.py` (copy one there to add a section per course or area). Files that already exist (scratch saved early) are left alone.
2. Last week's `review.md`, if it's missing or still blank: Done lists the ticked todos, Carried over gives the counts and where they went and lists the todos whose `carried from` date is 3 or more weeks back (the mark has no year, so it's the latest such date; a plain `carried` has no age), Notes says it was automatic. Slipped and any prose are left for an agent or the owner.
3. The new `plan.md`: the template, a note naming the week the carried todos came from, then the carried todos appended to their sections (sections the template lacks, such as `## Errands`, go at the end).

Carry rules (`carry.py`): open `- [ ]` todos move, with their indented lines, marked `carried from <MM-DD>` on their first carry (the source week's Monday; `; carried from 11-02` inside the due parenthetical, else ` (carried from 11-02)` before the `(mail)`/`(site)` tag). A todo already marked carried, dated or not, keeps its mark. `## Overdue` stays Overdue. An open todo whose `(due ...)` day, on its own first line (an indented line's date doesn't count), is before the rollover's day is late, so it moves to Overdue as `(was due ...)`. Today's own todos aren't late yet (a date-only due counts as 23:59), so a mid-week rollover (the PC was off on Monday) still moves the todos due Monday to yesterday. A due date that isn't a real date (2026-02-30) counts as none. Ticked todos stay behind. Nothing is ever ticked or dropped, except an open line identical to one of the template's own placeholder todos (the new plan has a fresh copy). The `## Priorities` list isn't carried; the new plan starts with the template's.

- **Early plans**: a week whose `plan.md` was made before the rollover (by hand) has no carried note (`"carried" = moved over from the`). If last week has open todos, the ones the early plan lacks (same tag and name, open or ticked, so nothing ticked is re-opened) are merged into it with the note (status `merged`, and the counts are of the todos actually added). A `## Overdue` it lacks is added as its first section, only if there are overdue items. If it already has every carried todo, it's left alone.
- **Idempotent**: a week whose `plan.md` has the carried note is left alone, and no existing file is overwritten (a blank review is filled once). The plan is written last, so a crash part-way leaves no plan and the next run starts over.
- **First week** (`start.py`): with no earlier `plan.md` anywhere and no plan this week, there's nothing to carry. If `life/inbox.md` exists (the sign you use `life/`), it starts this week anyway (status `started`): the workspace README, log, review and plan from the templates, with no carried todos. The week goes in the term whose `Term dates:` cover it, else the only term folder unless its `Term dates:` say it has ended; with no term folders it creates `terms/<year>/README.md` (just `# <year>`). If the only term has ended, or there are several term folders and none covers the week, it writes nothing (status `between-terms`, so the runners' once-a-week notice asks for the next term's folder or a `Term dates:` line). Without `inbox.md` it writes nothing (status `no-source`). The next run finds the plan and returns `current`.
- **Catch-up**: after a gap (the PC off for weeks) it jumps straight to the current week and carries everything from the last plan. Empty in-between weeks would only repeat the same carried list, and every reader looks at this week and next.
- **Terms** (`terms.py`): a term README may have a line `Term dates: YYYY-MM-DD to YYYY-MM-DD`. A term whose dates overlap the week gets it; otherwise the week stays in the last plan's term unless that term's dates say it has ended. Then the week is between terms: nothing is written (status `between-terms`, logged) and readers keep falling back to last week's plan. Code never creates a course, nor a term except the very first one (see First week); the owner adds the next term's folder (with its dates), and the next run rolls into it.

## Public API (`from mail_digest.rollover import ...`)

- `roll_over(life_dir, today, dry_run=False)` returns `RolloverResult(week, status, source, carried, overdue, writes)`. `status` is `current` (already rolled over), `rolled`, `merged` (carried into an early plan), `started` (the first week, nothing carried), `no-source` (no earlier plan and no first week started) or `between-terms`. `writes` is `(path relative to life/, text)` per file, also on a dry run, which writes nothing. Raises `TemplateError` (a `ValueError`) for a `<date>` that doesn't follow a weekday, `OSError` or `UnicodeDecodeError` for a file it can't read or write.
- `describe(result)`: one line for the log. `BETWEEN_TERMS`: that status, for the runners' notice.

## Files

`roll.py` (the entry point and the writes), `start.py` (a new week's skeleton files and the first week), `weeks.py` (week math and lookups), `terms.py`, `templates.py`, `sections.py` (splitting a week file by `## ` heading and joining it back), `carry.py`, `plan_text.py`, `review.py`.

## Dependencies

`mail_digest.kb` (`week_folder_name`), `mail_digest.deadlines` (`DUE_MARKER`, `open_todos`). Standard library only.
