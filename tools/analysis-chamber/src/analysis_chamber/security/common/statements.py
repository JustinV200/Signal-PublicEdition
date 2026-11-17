"""Split shell commands and script text into statements, and find where one starts.

personal_write_hook and raw_read_hook judge one statement at a time, so a read in one
command and a write in the next aren't mistaken for one command doing both.
"""

import re

# Statement breaks: lines, `;`, pipes and `&&` / `||`.
_STATEMENT_BREAK = re.compile(r"\n|;|&&|\|\|?")


# Where a Python statement starts in a shell command or script: a line start, `;`, or
# the opening quote of `python -c "..."`. Import rules use it so the English word
# "from" in a comment or string isn't read as an import. Compile with re.MULTILINE.
STATEMENT_START = r"(?:^|[;\"'])\s*"


def split_statements(text: str) -> list[str]:
    """The statements of a command or script: split on lines, `;`, `|`, `&&` and `||`.

    Args:
        text: A shell command or script text.

    Returns:
        The statements in order, untrimmed; empty ones stay in.
    """
    return _STATEMENT_BREAK.split(text)


def split_with_breaks(text: str) -> list[tuple[str, str]]:
    """Like split_statements, each paired with the break before it ("" for the first).

    raw_read_hook uses the break to tell a piped command (`| grep x`, reading stdin)
    from one that reads files.

    Args:
        text: A shell command or script text.

    Returns:
        (break, statement) pairs in order; break is "" for the first,
        then a newline, ";", "|", "||" or "&&".
    """
    parts = re.split(f"({_STATEMENT_BREAK.pattern})", text)
    return list(zip(["", *parts[1::2]], parts[::2], strict=True))
