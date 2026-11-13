r"""The line rules every run's edit to one KB file must pass (the guard applies them).

- Every added non-blank line ends in its run's tag (" (mail)" for the digest,
  " (site)" for checker v2: LineRules), or is one of the routine's fixed
  section headings. It is at most MAX_ADDED_LINE_CHARS long (or, for a changed
  line, MAX_LINE_GROWTH_CHARS longer than the owner's line it replaces, so ticking
  a long todo works) and uses only allowed
  characters: letters, marks and digits of any script, the ALLOWED_SPACES and the
  ALLOWED_PUNCTUATION set. So no backslash, backtick, "<", ">", "{", "}", "~", "^"
  or "$", no other symbol (emoji included) and no control, format, unassigned or
  other space character. It also has none of the letters and marks that render as
  nothing (INVISIBLE), no overlay or enclosing mark, no run of more than
  MAX_MARK_RUN marks, and none of the FORBIDDEN sequences: "//" or "www." (a URL),
  "](" or "]:" (a Markdown link, image or link definition), "&#" or "&name;" (a
  character reference) and 6+ digit numbers.
- An added table row has no more cells than its table's header (tables.py), since
  renderers drop the extra ones and the text in them.
- At most MAX_ADDED_LINES_PER_FILE lines are added (blank ones too) and
  MAX_REMOVED_LINES_PER_FILE non-blank lines removed. A changed line counts as both.
- Before the edit, the file had no HTML (HTML_START) and no lone "\r"
  (LONE_CARRIAGE_RETURN). An added line can hold neither, but it could land inside
  the file's own HTML comment or closed <details>, which hide it, and a lone "\r"
  is a line break to renderers that these rules don't see.
- On a site run (LineRules.forbid_untick), the file's todo and ticked counts don't
  drop (todo_counts.py).

Lines are split on "\n" (and "\r\n") only, so any other line break (a lone "\r",
"\x0c", U+2028...) stays inside its line and fails the character check.
Otherwise one tagged line could hide a second line that a viewer shows.
"""

import difflib
import itertools
import re
import unicodedata
from dataclasses import dataclass

from mail_digest.kb.tables import MARKDOWN_SPACING, cell_count, table_widths
from mail_digest.kb.todo_counts import untick_problems
from mail_digest.settings import (
    MAIL_TAG,
    MAX_ADDED_LINE_CHARS,
    MAX_ADDED_LINES_PER_FILE,
    MAX_REMOVED_LINES_PER_FILE,
)

# The characters a digest line may use. An allowlist, because every deny-list round
# found another Markdown trick that hides text (code spans, comments, fences, escapes,
# math). Unicode letters, marks and digits (L*, M*, N*) keep accented names working.
# The punctuation is what the routine's line formats and the KB's own lines use, plus
# the dashes, curly quotes and signs the model and email text often have: no-break
# hyphen, ellipsis, bullet, middle dot, arrow, euro, pound, degree, registered and
# trade mark. None of those means anything in Markdown.
# Left out on purpose: "\" (escapes, math commands), "`" (code), "<" and ">" (HTML,
# comments, autolinks, quotes), "{" "}" "^" (math, footnotes), "~" (fences,
# strikethrough) and "$". "$" opens math, where "%" starts a comment that hides the
# rest of the line, even with no other markup. The KB needs "%" (grade weights) but
# never uses "$", so money is written as "1,250 dollars".
ALLOWED_PUNCTUATION = frozenset(
    ".,:;!?-'\"()/%#&@+*|[]_="
    "\u2013\u2014\u2018\u2019\u201c\u201d"
    "\u2011\u2026\u2022\u00b7\u2192\u20ac\u00a3\u00b0\u00ae\u2122"
)
# The plain space, and the no-break spaces email text is full of (U+00A0, and U+202F
# before "PM"). Markdown doesn't take those two for spacing, so they can't indent a
# line into a code block, make it blank or trim a table cell away (tables.py).
ALLOWED_SPACES = frozenset(" \u00a0\u202f")
ALLOWED_CATEGORY_GROUPS = "LMN"
# Allowed letters and marks that render as nothing: the variation selectors (Mn:
# U+FE00-U+FE0F, U+E0100-U+E01EF and Mongolian U+180B-U+180D and U+180F), which can
# smuggle bytes, the combining grapheme joiner and Khmer inherent vowels (Mn), and
# the Hangul fillers (Lo). They're the default-ignorable characters the allowlist
# lets through (it rejects the Cf and Cn ones). The Khitan filler (Mn) is blank too.
INVISIBLE = re.compile(
    "[\ufe00-\ufe0f\U000e0100-\U000e01ef\u180b-\u180d\u180f"
    "\u034f\u17b4\u17b5\u115f\u1160\u3164\uffa0\U00016fe4]"
)
# Marks stack on their letter, and a long run spills over the lines around it
# ("Zalgo" text). Decomposed Vietnamese, the most real text needs, has 2 in a row.
MAX_MARK_RUN = 3
# Canonical combining class 1 (Overlay): marks drawn through their letter, such as
# U+0336 or U+0338, which fake a strikethrough and make a todo look crossed out.
OVERLAY_COMBINING_CLASS = 1
# Enclosing marks (Me) draw a circle, square or "no" sign around their letter. U+20E0,
# a circle with a backslash, makes an item look cancelled. The KB never needs them.
ENCLOSING_MARK_CATEGORY = "Me"
# Sequences of allowed characters no digest line may contain: links, character
# references and long numbers (verification codes, account numbers). "//" catches
# every URL, with a scheme or without (//host), and "www." the scheme-less ones GFM
# links. "](" catches every inline Markdown link or image, whatever its target
# (mailto:, https:host). "]:" catches every link reference definition wherever it
# sits (in a list item or quote): its destination can be "https:host", and since it
# doesn't render, "[//]: # (...)" hides a comment. No digest line has "]:", as its
# tags are followed by a space. "&#" and "&name;" are character references, which
# render as any character, a hidden one (&#x202E;, &zwnj;) or a "/" (&sol;) included.
# shortcut: bare domains (evil.example), digits split by spaces (482 910), digits
# that aren't decimal digits (circled or superscript ones aren't "\d") and email
# addresses (GFM links them as mailto:, also in the mailto:x@host and xmpp: forms)
# still pass; block them too if a planted line ever gets through that way.
FORBIDDEN = re.compile(r"//|www\.|\]\(|\]:|&#|&[A-Za-z][A-Za-z0-9]*;|\d{6,}", re.IGNORECASE)
# The only headings the routine may add without the tag (refdocs/routines/mail-digest.md
# and the run context's missing-plan line): Overdue, Coming up, For the <week> plan,
# where <week> is a week folder name such as 2026-10-19-to-10-25.
FIXED_HEADING = re.compile(
    r"#{2,4} (Overdue|Coming up|For the [0-9]{4}-[0-9]{2}-[0-9]{2}-to-[0-9]{2}-[0-9]{2} plan)"
)
# The start of an HTML tag, comment or declaration (an autolink too). A deny-list of
# the hiding tags would miss one, and no target file has any "<" today. A file the
# owner gives HTML can't take digest edits until it's gone (each one is undone).
HTML_START = re.compile(r"<[!?/A-Za-z]")
# A carriage return with no "\n" after it. GFM ends a line there, but these rules
# split on "\n" only, so tables.py would count a table's rows from the wrong lines
# (a delimiter row hidden after one would be missed).
LONE_CARRIAGE_RETURN = re.compile(r"\r(?!\n)")
# How much longer than the line it replaces a changed line may grow (a tick plus a
# "(confirmed by email ...) (mail)" suffix), when that's past MAX_ADDED_LINE_CHARS.
MAX_LINE_GROWTH_CHARS = 100
# How much of a rejected line to put in the log.
LOGGED_LINE_CHARS = 80


@dataclass(frozen=True)
class LineRules:
    """Which run's rules apply: the tag every added line ends in, and the no-untick rule.

    tag: "(mail)" for the digest, "(site)" for checker v2. It must end the line, so
      the tag in the middle of a planted line doesn't count.
    forbid_untick: True on site runs, where a file's todo or ticked count may not
      drop (todo_counts.py). Off for the digest.
    """

    tag: str = MAIL_TAG
    forbid_untick: bool = False


DIGEST_RULES = LineRules()


def edit_problems(before: str, after: str, rules: LineRules = DIGEST_RULES) -> list[str]:
    """Why the edit from before to after breaks the line rules ([] if it doesn't).

    rules picks the tag and the no-untick rule; the digest's by default.
    """
    if HTML_START.search(before):
        return ["the file has HTML (a tag or comment), which could hide added lines"]
    if LONE_CARRIAGE_RETURN.search(before):
        return ["the file has a lone carriage return, a line break the table check misses"]
    new_lines = _lines(after)
    added, removed = _changed_lines(_lines(before), new_lines)
    if len(added) > MAX_ADDED_LINES_PER_FILE:
        # Before the line checks, so a flood isn't checked and logged line by line.
        return [f"{len(added)} lines added or changed (at most {MAX_ADDED_LINES_PER_FILE})"]
    widths = table_widths(new_lines)
    problems = [
        f"bad added line {new_lines[i][:LOGGED_LINE_CHARS]!r}"
        for i, old in added.items()
        if not _is_allowed(new_lines[i], rules.tag, _max_chars(old))
        or _has_extra_cells(new_lines[i], widths[i])
    ]
    if len(removed) > MAX_REMOVED_LINES_PER_FILE:
        problems.append(
            f"{len(removed)} lines changed or removed (at most {MAX_REMOVED_LINES_PER_FILE})"
        )
    if rules.forbid_untick:
        problems += untick_problems(before, after)
    return problems


def added_lines(before: str, after: str) -> list[str]:
    """The non-blank lines of after that the edit from before added or changed, in order.

    The same diff edit_problems checks, so these are the lines the guard let through.
    """
    new_lines = _lines(after)
    added, _removed = _changed_lines(_lines(before), new_lines)
    return [new_lines[i] for i in added if new_lines[i].strip()]


def _lines(text: str) -> list[str]:
    """A file's lines. Not splitlines(): see the module docstring."""
    return text.replace("\r\n", "\n").split("\n")


def _changed_lines(
    old_lines: list[str], new_lines: list[str]
) -> tuple[dict[int, str | None], list[str]]:
    """(added line's index in new_lines -> the old line it replaces or None, the
    removed lines), blank removals left out.

    In a replaced block the old and new lines pair up by position.
    """
    matcher = difflib.SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
    added: dict[int, str | None] = {}
    removed = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in ("replace", "delete"):
            removed += [line for line in old_lines[i1:i2] if line.strip()]
        if tag in ("replace", "insert"):
            old = old_lines[i1:i2] if tag == "replace" else []
            for k, j in enumerate(range(j1, j2)):
                added[j] = old[k] if k < len(old) else None
    return added, removed


def _max_chars(old_line: str | None) -> int:
    """The length cap for an added line, given the old line it replaces (None if new)."""
    if old_line is None:
        return MAX_ADDED_LINE_CHARS
    return max(MAX_ADDED_LINE_CHARS, len(old_line) + MAX_LINE_GROWTH_CHARS)


def _has_extra_cells(line: str, table_width: int | None) -> bool:
    """True if line is a row of a table_width-cell table (tables.py) with more cells than that.

    The tag cell counts too, so a row carries its tag in its last real cell.
    """
    return table_width is not None and cell_count(line) > table_width


def _is_allowed(line: str, tag: str, max_chars: int) -> bool:
    """True if one added line, at most max_chars long, follows the rules for lines
    tagged tag (blank lines always do)."""
    # Blank means spaces and tabs only: str.strip() would also take a line of "\x1f",
    # U+2028 or no-break spaces for blank, past the character check.
    if not line.strip(MARKDOWN_SPACING):
        return True
    # Headings go through the allowlist too, so the strip() below only drops spaces.
    if len(line) > max_chars or not is_safe_text(line):
        return False
    return line.rstrip().endswith(f" {tag}") or FIXED_HEADING.fullmatch(line.strip()) is not None


def is_safe_text(text: str) -> bool:
    """True if text could sit in a KB line: allowed characters only, none of the
    FORBIDDEN sequences, no INVISIBLE letter and no long run of marks.

    No length or tag check: the checker also runs this on assignment names from a
    course site before the writer ever sees them.
    """
    if FORBIDDEN.search(text) or INVISIBLE.search(text):
        return False
    return all(_is_allowed_character(char) for char in text) and not _has_long_mark_run(text)


def _is_allowed_character(char: str) -> bool:
    """True if char may appear in a digest line: one of ALLOWED_SPACES or
    ALLOWED_PUNCTUATION, a letter or digit, or a mark that isn't an overlay or
    enclosing one."""
    if char in ALLOWED_SPACES or char in ALLOWED_PUNCTUATION:
        return True
    if unicodedata.combining(char) == OVERLAY_COMBINING_CLASS:
        return False
    category = unicodedata.category(char)
    return category != ENCLOSING_MARK_CATEGORY and category[0] in ALLOWED_CATEGORY_GROUPS


def _has_long_mark_run(line: str) -> bool:
    """True if more than MAX_MARK_RUN marks (M*) follow one another in line."""
    runs = itertools.groupby(line, key=lambda char: unicodedata.category(char)[0] == "M")
    return any(is_mark and sum(1 for _ in run) > MAX_MARK_RUN for is_mark, run in runs)
