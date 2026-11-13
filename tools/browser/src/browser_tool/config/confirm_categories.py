"""The [gates] always_confirm categories and the button-text patterns of each.

An action whose target text matches a category's patterns is in that category.
Some rules in browser_tool.actions add to a category without a pattern: a submit
button in a form that isn't a search, GET or sign-in (password) form, Enter that
submits one, Control+Enter, and Enter in a message box (send); the Delete key
(delete). Actions in a category listed in [gates] always_confirm wait for the
owner's Allow; the rest run and are logged. The owner asks for approval only on
purchases, sends and deletes; RETIRED_CATEGORIES are names older configs may
still list, which the loader ignores with a warning. SIGN_IN_WORDING_RE is the
wording a sign-in form's submit button needs to skip the send rule.
"""

import re

CATEGORY_PURCHASE = "purchase"
CATEGORY_SEND = "send"
CATEGORY_DELETE = "delete"

# Case-insensitive regexes, matched against an element's accessible name and live
# text (and its ancestors', see actions/gating/confirmation.py). Insertion order is the
# order rules are tried in, and the default always_confirm order.
CATEGORY_PATTERNS: dict[str, tuple[str, ...]] = {
    CATEGORY_PURCHASE: (
        r"\bbuy\b",
        r"\bpurchase\b",
        r"\bpay\b",
        r"\bcheck ?out\b",
        r"\bplace (your )?order\b",
        r"\b(confirm|complete|submit) (your )?(order|purchase|payment)\b",
        r"\bsubscribe\b",
        r"\bdonate\b",
        r"\btransfer\b",
        r"\bwithdraw\b",
    ),
    CATEGORY_SEND: (
        r"\bsend\b",
        r"\bpost\b",
        r"\breply\b",
        r"\bpublish\b",
        r"\bcomment\b",
        # Handing in work or a form is outward-facing too.
        r"\bsubmit\b",
        r"\bunsubmit\b",
        r"\b(turn|hand) in\b",  # Google Classroom's "Turn in"
        r"\bmark as done\b",  # Classroom hands in an assignment with no attachment
        r"\bshare\b",
        r"\bupload\b",
        # GitHub. Broad on purpose: asking about a "commit" link beats a silent merge.
        r"\bmerge\b",
        r"\bcommit\b",
        r"\bclose (issue|pull request|as)\b",
        # Drive emails the file's owner; Gmail's Unsubscribe can send mail for you.
        r"\brequest (edit )?access\b",
        r"\bunsubscribe\b",
    ),
    CATEGORY_DELETE: (
        r"\bdelete\b",
        r"\bremove\b",
        r"\btrash\b",
    ),
}

ALL_CATEGORIES: tuple[str, ...] = tuple(CATEGORY_PATTERNS)

# The whole label of a sign-in submit, any case: one or more of these phrases
# with optional trailing arrows or punctuation ("Sign in", "Next >", "Log in Log
# in" when aria-label and text repeat). Anything else, such as "Save changes",
# "Post", "Update" or "Go", keeps the send rule even in a sign-in form.
SIGN_IN_WORDING_RE = re.compile(
    r"\s*(?:(?:log ?in|sign ?in|sign on|log on|next|continue|verify)\b[\W_]*)+",
    re.IGNORECASE,
)

# Categories earlier versions had (signing in and OAuth consent asked too).
RETIRED_CATEGORIES: tuple[str, ...] = ("password_submit", "grant_access")
