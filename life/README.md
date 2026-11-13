# life/ (optional)

An optional private knowledge base for the owner: responsibilities, weekly plans, an inbox and notes that agents read for context. Everything in this folder except this README is gitignored, so it never leaves your PC.

Tools that use it, if you set them up:
- `tools/mail-digest` adds dated lines from email to `inbox.md` and to the current week's plan (`terms/<term>/weeks/<YYYY-MM-DD>-to-<YYYY-MM-DD>/plan.md`) and course or area READMEs, and starts each new week (see Weeks below).
- `tools/whiteboard` shows the week plan's open `- [ ]` todos on its TODO view.
- `tools/jobhunt` keeps its runbook, profile, resume and tracker in `areas/job-search/`.
- The browser tool may upload files from here (`[uploads] roots`).

Start with an empty `inbox.md`; setup creates the folders a chosen tool needs.

## Weeks

- Layout: `terms/<term>/README.md`, then one folder per week, `terms/<term>/weeks/<Monday YYYY-MM-DD>-to-<Sunday MM-DD>/`, holding `plan.md`, `log.md`, `review.md` and a `workspace/` for that week's scratch files.
- Todos: `- [ ] [tag] task (due YYYY-MM-DD HH:MM)`, 24-hour clock, or `(due YYYY-MM-DD)` when no time is known. Late items go in `## Overdue` at the top of the plan.
- Term dates: a term's README may say `Term dates: YYYY-MM-DD to YYYY-MM-DD` on a line of its own. Once a term with dates has ended and no other term folder's dates cover the week, the rollover stops (between terms, spoken once a week) until you add the next term's folder with its own `Term dates:` line. A term without the line never ends.
- Week rollover is automatic: each mail digest run (and each assignment check) first starts the current week if it hasn't been started. With an `inbox.md` here and no weeks yet, it starts the first week itself (in the term whose `Term dates:` cover it, else your only term folder, else a new `terms/<year>/`). After that it creates the week folder from `templates/week-plan.md`, `week-log.md` and `week-review.md` (built-in defaults if you have none; copy one there to add a section per course or area), moves last week's open todos over marked `carried from <MM-DD>`, moves past-due ones to `## Overdue`, and fills last week's `review.md` counts. It never ticks or drops anything, catches up after missed weeks, and is safe to run again. By hand: `uv run --project tools/mail-digest --frozen --no-sync mail-digest rollover` (add `--dry-run` to preview).
- Don't create next week's `plan.md` by hand: let the rollover start it. If one is made early anyway, the rollover merges the carried todos into it once.
