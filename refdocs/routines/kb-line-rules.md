## Line rules (a guard checks these after the run)

- End every line you add or change with ` {tag}`, so the owner can see where each line came from. It must be the very end of the line. Only these headings need no tag: `## Overdue`, `## Coming up` and `## For the <week> plan`. Any other heading you add ends in ` {tag}` too.
- In a table row, put ` {tag}` at the end of the last cell and leave off the closing `|`: `| Wed 2026-11-04 | Final exam | 25% {tag}`. A row has exactly as many cells as the table's header, the tag inside the last one. Never give the tag a cell of its own (`| 25% | {tag}`) or add any other extra cell: the guard undoes a file with a row wider than its header.
- Plain text only: letters (accented ones are fine), digits, spaces and basic punctuation (`. , : ; ! ? - ' " ( ) / % # & @ + * | [ ] _ =`, dashes, curly quotes and `… • · → € £ ° ® ™`). No emoji or other symbols, no backslash, no backticks, no `<` `>` `{` `}` `~` `^`, and no `$` (write money as `1,250 dollars`). If a line you change already has one of these, reword that part (`~9:15` becomes `about 9:15`).
- No links (nothing with `//`, `www.` or `]:`), no character references (`&#` or `&name;`), and no numbers of 6 or more digits (such as codes or account numbers). A line can be at most 300 characters.
- If updating a line would push it over 300 characters, add a short new tagged line instead of growing the old one, so the guard doesn't undo the file.
- Per file and run, change or delete at most 5 existing lines, and have at most 60 added or changed lines in all, blank lines included. A changed line counts toward both limits, so ticking a todo or updating a row uses one of the 5 and one of the 60. Change only the lines you need to. On a catch-up run with more than that, make the 5 most important changes, keep the total to at most 60, and add the rest to `inbox.md` as new lines.
- Don't edit a file that has a `<` followed by a letter, `!`, `?` or `/` anywhere in it: HTML such as `<!--` or `<details>`, an autolink, or an unfilled placeholder such as `<date>` all count. The guard undoes every edit to such a file, since a line could land inside hidden HTML. Put those items in `inbox.md` instead.
- If a file breaks these rules, the guard undoes all of your edits to it.

## KB conventions (from life/README.md)

- Todos: `- [ ] [course] task (due YYYY-MM-DD HH:MM) {tag}`, 24-hour clock, such as `(due 2026-10-26 08:30)`, or `(due 2026-10-26)` when no time is known. Notes go after the time, inside the same parentheses: `(due 2026-10-26 08:30; real date TBA)`. The runner reads these markers to announce what's due within 24 hours, so never write `(due Thu)`. Use the course tag this week's plan already uses for that course (for example `[hist-205]`).
- Dates are sortable: `2026-10-19`. Times are local, as the source gives them.
- Unknown or ambiguous details get `TODO: verify`. Never guess a date, time, course or name.
- Keep the existing structure and wording of every file.
- You can edit only `inbox.md`, this week's plan and the course READMEs the run context names, and you can't create files. If this week's plan is missing, the run context says where class items go instead.
