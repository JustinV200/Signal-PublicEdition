# mail_digest.deadlines

Step 5 of the mail digest routine, done by the runner instead of the model: pick the plan todos the owner should hear about now, with stable keys and a short spoken sentence.

## Public API (`from mail_digest.deadlines import ...`)

- `pick_announcements(life_dir, now)`: the picks of this week's plan, or last week's until the owner rolls over (rollover is by hand, so on a Monday morning last week's plan still has the Monday todos), and next week's (it catches a todo due early Monday), each key once. A plan that can't be read is logged and skipped.
- `select_announcements(plan_text, now)`: the picks of one plan.
  - Only open `- [ ]` todos count; ticked `- [x]` ones never do.
  - Every open todo under `## Overdue` is kind `overdue`.
  - Any other open todo whose due marker, `(due YYYY-MM-DD[ HH:MM]` followed by `)`, `;` or `,`, falls after now and within 24 hours is kind `due`. No time means 23:59 that day. Times are local wall-clock times.
  - The key is `due|<YYYY-MM-DD>|<slug>` or `overdue|<slug>`, the slug being the tag and name. The name leaves out every parenthetical (due marker, notes, the `(mail)` or `(site)` tag), so a new note or a new time on the same day keeps the key, and the announcer speaks it once. The due day lets a weekly todo with the same name be spoken each week. Keys from before the due day was added don't match, so the first run after the change speaks that day's due items once more.
  - The sentence is `CHEM 120, due today at 17:00: <name>.` or `CHEM 120, overdue: <name>.`, through `clean_sentence` (so a name with a domain, an `@` or a long number isn't spoken). The course and time come first, so the 120-char cut only shortens the name. Spaces left before punctuation where notes were cut out are removed.
- `open_todos(plan_text)` returns `PlanTodo(tag, name, due, has_time, is_overdue)` per open todo.

The runner hands the model the picks made before claude starts, for context, and speaks the picks made from the plans after the guard.

## Files

`todos.py` (reading a plan), `pick.py` (choosing and wording).

## Dependencies

`mail_digest.settings`, `mail_digest.announce` (the `Announcement` type), `mail_digest.claude` (`slugify`, `clean_sentence`), `mail_digest.kb` (`find_plan`). Standard library only.
