# assignment_check.findings

The boundary between page text and `life/` (design section 3.3). Pure: no files, no processes.

## Public API

- `check_findings(sites, now)` returns `Findings(items, problems)` (`check.py`), from one `SiteReading(pages, visit, reading, cut)` per site.
- `Item`, `Problem` and the status and reason constants (`model.py`).
- `due_at(due, now)` (`flags.py`).

## Rules

- `pages.py`: a page is used only if the visit got it, the reader got all of it and marked it readable, it isn't suspicious, and a Classroom page shows `owner@school.example.edu`. A problem with any page leaves its whole course out.
- `items.py`: the name (at most 120 chars, `kb.is_safe_text`, an element's whole quoted name on the page, so "Homework" never matches "Homework 3"), the ref (in the URL under the item's own link, `site_rules.item_link`), the class (Classroom), the kind and the due date; 60 items per page and 150 in all.
- `site_rules.py`: links built by the runner from the page's own `/url:` lines, and the status from the list (Classroom) or only when every step is unambiguous (Moodle): exactly one link for the name and ref, in a row holding no other link, with exactly one fixed phrase left once the name is taken out; anything else is unknown. Snapshots are split on `\n` only, and Playwright's single-quoted keys (`- 'link "Lab 3: Arrays"':`) are unquoted before any match. Its shapes and phrases are DRAFT [unverified] until phase 0.
- `flags.py`: repeats merged by course and link (a trusted status beats unknown; two trusted ones that disagree give unknown, except on Classroom, where the worse list wins so done never beats open or missing), then `overdue` and `due_soon`.

## Dependencies

`assignment_check.courses`, `reader` and `visit` (types), `mail_digest.kb`.
