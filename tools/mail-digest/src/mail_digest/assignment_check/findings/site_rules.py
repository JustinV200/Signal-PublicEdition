"""The site-specific checks: an item's ref against the page's own links, and its status.

Names match only an element's whole quoted name, so "Homework" never borrows
"Homework 3"'s link or row. The link is built by the runner from a ref in the `/url:`
line under the item's own link, in the expected shape, so a URL the model wrote is
never used. Status comes from where the item was listed (Classroom) or from a fixed
table of Moodle phrases in the item's own row, so text elsewhere on a page can't
mark work as submitted.

Every shape and phrase here is DRAFT [unverified] (design sections 3.3 and 4): phase 0
records the real snapshots and corrects them.
"""

import re
from urllib.parse import urlsplit

from mail_digest.assignment_check.courses import CLASSROOM, Page
from mail_digest.assignment_check.findings.model import DONE, MISSING, OPEN, UNKNOWN, fold

# A link's URL line in a browser_tool snapshot: `- /url: <href>` (absolute or relative).
URL_LINE = re.compile(r"- /url:\s*(\S+)")
# DRAFT [unverified]: a snapshot names an element in quotes (`- link "A18 Sorting":`),
# nests each child indented deeper than its parent, puts a link's `- /url:` line
# straight after it, and nests a Moodle row's links under its `- row "<every cell>":`
# line. Any other layout fails closed: no link, or status unknown.
ROW_LINE = "- row "
LINK_LINE = "- link "
# DRAFT [unverified]: /mod/<type>/view.php?id=<n>, the query only the id.
MOODLE_PATH = re.compile(r"/mod/([a-z]{2,20})/view\.php")
MOODLE_QUERY = re.compile(r"id=([0-9]{1,10})")
# DRAFT [unverified]: /u/<n>/c/<class>/a/<item>/details.
CLASSROOM_PATH = re.compile(r"(?:/u/\d)?/c/([A-Za-z0-9_-]{4,40})/a/([A-Za-z0-9_-]{4,40})/details")
# Classroom's lists say the status themselves.
CLASSROOM_STATUS = {"turned-in": DONE, "missing": MISSING, "not-turned-in": OPEN}
# DRAFT [unverified]: Moodle's submission-status phrases, casefolded. Only the
# assignment index has them.
MOODLE_STATUS = {
    "submitted for grading": DONE,
    "no submission": OPEN,
    "draft (not submitted)": OPEN,
}
MOODLE_STATUS_LIST = "assign"


def item_link(page: Page, name: str, ref: str, text: str) -> str | None:
    """The runner's link for ref, or None unless ref is in the URL of name's own link."""
    found = _accepted_links(page, name, ref, _lines(text))
    return found[0][1] if found else None


def _accepted_links(page: Page, name: str, ref: str, lines: list[str]) -> list[tuple[int, str]]:
    """(line index, the runner's link) for each of name's links whose URL is ref's.

    A link's own URL is the `- /url:` line straight after it and indented deeper. A
    link line with anything else after it has no URL here, so it can't borrow the
    next one's.
    """
    accepted = []
    for index in _name_links(name, lines):
        if index + 1 >= len(lines) or _indent(lines[index + 1]) <= _indent(lines[index]):
            continue
        match = URL_LINE.fullmatch(lines[index + 1].strip())
        link = _link_from(page, match.group(1), ref) if match else None
        if link:
            accepted.append((index, link))
    return accepted


def _link_from(page: Page, href: str, ref: str) -> str | None:
    """The link built from href if it's this site's item link for ref, else None."""
    try:
        parts = urlsplit(href)
    except ValueError:
        return None
    # The page's own site host (from its base URL); a relative link has none.
    site_host = urlsplit(page.base).netloc
    if page.site == CLASSROOM:
        if parts.netloc not in ("", site_host) or parts.query:
            return None
        found = CLASSROOM_PATH.fullmatch(parts.path)
        # The item must be in this page's own class, not one the page links to.
        if found and found.group(1) == page.course.site_id and found.group(2) == ref:
            return f"{page.base}/c/{found.group(1)}/a/{found.group(2)}/details"
        return None
    if parts.netloc not in ("", site_host):
        return None
    path, query = MOODLE_PATH.fullmatch(parts.path), MOODLE_QUERY.fullmatch(parts.query)
    if path and query and query.group(1) == ref:
        return f"{page.base}/mod/{path.group(1)}/view.php?id={query.group(1)}"
    return None


def is_named_on_page(name: str, folded_text: str) -> bool:
    """True if the page names an element exactly name (in quotes), not just contains it.

    So "Homework" isn't on a page that only has "Homework 3". folded_text is fold(text).
    """
    return f'"{fold(name)}"' in folded_text


def item_status(page: Page, name: str, ref: str, status_text: str, text: str) -> str:
    """The item's status, from the runner's rules only (see the module docstring).

    On Moodle a status is trusted only when every step is unambiguous, else UNKNOWN:
    exactly one of name's links has ref's URL; it sits in a row; that row holds no
    other link (so "Homework" inside Homework 2's row can't take its status) and has
    the name in its text; and with the name taken out, exactly one MOODLE_STATUS
    phrase is left, status_text's.
    """
    if page.site == CLASSROOM:
        return CLASSROOM_STATUS.get(page.list_kind, UNKNOWN)
    phrase = fold(status_text)
    if page.list_kind != MOODLE_STATUS_LIST or phrase not in MOODLE_STATUS:
        return UNKNOWN
    lines = _lines(text)
    found = _accepted_links(page, name, ref, lines)
    row_at = _row_of(lines, found[0][0]) if len(found) == 1 else None
    if row_at is None or _link_count(lines, row_at) != 1:
        return UNKNOWN
    row = _key(lines[row_at])
    # A row's line holds all its cells, so the item's own row has its name too.
    if fold(name) not in row:
        return UNKNOWN
    # "\x00", not a space, so the name's two sides can't join into a phrase.
    cells = row.replace(fold(name), "\x00")
    present = [known for known in MOODLE_STATUS if known in cells]
    return MOODLE_STATUS[phrase] if present == [phrase] else UNKNOWN


def _lines(text: str) -> list[str]:
    """A snapshot's lines, split on "\n" only.

    The browser tool's redactor already split the snapshot with splitlines(), so a
    U+2028 or U+0085 in a page's text reached us as a line break; splitting on "\n"
    alone means no other character can start a line here that the browser tool's own
    line handling didn't. A name that held one has been cut at it and simply won't match.
    """
    return text.split("\n")


def _key(line: str) -> str:
    """line's folded key, with Playwright's YAML single quotes undone.

    Playwright single-quotes a whole key that holds ": ", " #", "{", "}" or a
    backtick (`- 'link "Lab 3: Arrays" [ref=e4]':`), doubling any ' inside. That
    becomes `- link "lab 3: threads" [ref=e4]:` here, so every matcher sees one form.
    A quote that never closes is left as it is, so nothing matches it.
    """
    stripped = line.strip()
    if not stripped.startswith("- '"):
        return fold(stripped)
    body, index = stripped[len("- '") :], 0
    while index < len(body):
        if body[index] == "'":
            if body[index + 1 : index + 2] != "'":
                return fold("- " + body[:index].replace("''", "'") + body[index + 1 :])
            index += 1  # a doubled '' inside the key
        index += 1
    return fold(stripped)


def _name_links(name: str, lines: list[str]) -> list[int]:
    """The indexes of the lines that are a link named exactly name."""
    wanted = f'- link "{fold(name)}"'
    # Folded only to compare names: Classroom's ids are case-sensitive.
    return [index for index, line in enumerate(lines) if _key(line).startswith(wanted)]


def _row_of(lines: list[str], index: int) -> int | None:
    """The index of the table row line lines[index] sits inside, or None if it's in no row.

    Its ancestors are the earlier lines each indented less than the last; the first
    of them that is a row line is its row. A link outside every table (a sidebar,
    a block) has none, so it never borrows the last row above it.
    """
    depth = _indent(lines[index])
    for above in range(index - 1, -1, -1):
        line = lines[above]
        if _indent(line) < depth:
            if _key(line).startswith(ROW_LINE):
                return above
            depth = _indent(line)
    return None


def _link_count(lines: list[str], row_at: int) -> int:
    """How many link lines the row at row_at holds (the lines below it, indented deeper).

    A blank line doesn't end the row, so a link after one is still counted.
    """
    depth, count = _indent(lines[row_at]), 0
    for line in lines[row_at + 1 :]:
        if not line.strip():
            continue
        if _indent(line) <= depth:
            break
        count += _key(line).startswith(LINK_LINE)
    return count


def _indent(line: str) -> int:
    """How far line is indented: a snapshot nests a child deeper than its parent."""
    return len(line) - len(line.lstrip())
