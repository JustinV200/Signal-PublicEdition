"""Parse lines of a Playwright "ai" aria snapshot.

Each element line is a YAML list item whose key is `role "name" [attr] [ref=eN]`
and whose optional inline value follows ": ". Verified output from 1.64 includes:

    - textbox "User" [ref=e5]: alice
    - textbox "focused" [active] [ref=e5]: foc-secret
    - 'textbox "Pass \"word\" [ref=e99]: x" [ref=e3]': "a\"b: c"
    - link "link" [ref=e8] [cursor=pointer]:
      - /url: https://example.com/x

The key is YAML-quoted (single or double) when the accessible name contains
characters like ": ". The name inside the key is a JSON-style quoted string, so a
page can't fake a `[ref=...]` by putting one in an element's name.
"""

import json
import re
from dataclasses import dataclass

_ITEM_RE = re.compile(r"^(?P<indent> *)- (?P<body>.*)$")
_ROLE_RE = re.compile(r'^(?P<role>[^\s"\[]+)')
_ATTR_RE = re.compile(r"\[([^\]]*)\]")
_REF_PREFIX = "ref="


@dataclass(frozen=True)
class SnapshotLine:
    """One parsed element line. `raw_key` is the key exactly as printed."""

    indent: int
    raw_key: str
    role: str
    name: str | None
    ref: str | None
    has_value: bool
    opens_children: bool


def is_item_line(line: str) -> bool:
    """True if the line is a YAML list item ("  - ...")."""
    return _ITEM_RE.match(line) is not None


def indent_of(line: str) -> int:
    """Number of leading spaces."""
    return len(line) - len(line.lstrip(" "))


def parse_line(line: str) -> SnapshotLine | None:
    """Parse one snapshot line.

    Returns:
        The parsed line, or None if it isn't an item line or can't be parsed
        (for example an unterminated quote).
    """
    match = _ITEM_RE.match(line)
    if match is None:
        return None
    split = _split_key(match["body"])
    if split is None:
        return None
    raw_key, key, rest = split
    role_match = _ROLE_RE.match(key)
    if role_match is None:
        return None
    name, attrs_text = _split_name(key[role_match.end() :])
    refs = [
        attr[len(_REF_PREFIX) :]
        for attr in _ATTR_RE.findall(attrs_text)
        if attr.startswith(_REF_PREFIX)
    ]
    return SnapshotLine(
        indent=len(match["indent"]),
        raw_key=raw_key,
        role=role_match["role"],
        name=name,
        ref=refs[-1] if refs else None,
        # Anything after the key other than a bare ":" counts as a value (conservative).
        has_value=rest not in ("", ":"),
        opens_children=rest == ":",
    )


def label_of(line: SnapshotLine) -> str:
    """A short label for the element, like 'button "Buy now"', or just its role."""
    return f'{line.role} "{line.name}"' if line.name else line.role


def build_ref_labels(lines: list[SnapshotLine | None]) -> dict[str, str]:
    """Map each ref to a short label like 'button "Buy now"' for confirmation dialogs."""
    labels = {}
    for line in lines:
        if line is not None and line.ref is not None:
            labels[line.ref] = label_of(line)
    return labels


def _split_key(body: str) -> tuple[str, str, str] | None:
    """Split an item body into (raw_key, unquoted_key, rest_after_key)."""
    if body[:1] in ("'", '"'):
        end = _closing_quote(body)
        if end is None:
            return None
        raw_key = body[: end + 1]
        return raw_key, _unquote_yaml(raw_key), body[end + 1 :]
    separator = body.find(": ")
    if separator != -1:
        return body[:separator], body[:separator], body[separator:]
    if body.endswith(":"):
        return body[:-1], body[:-1], ":"
    return body, body, ""


def _closing_quote(text: str) -> int | None:
    """Index of the quote closing text[0] ('' escapes in single, \\ in double quotes)."""
    quote = text[0]
    index = 1
    while index < len(text):
        char = text[index]
        if quote == '"' and char == "\\":
            index += 2
            continue
        if char == quote:
            if quote == "'" and text[index + 1 : index + 2] == "'":
                index += 2
                continue
            return index
        index += 1
    return None


def _unquote_yaml(raw_key: str) -> str:
    if raw_key[0] == "'":
        return raw_key[1:-1].replace("''", "'")
    try:
        return json.loads(raw_key)
    except json.JSONDecodeError:
        return raw_key[1:-1]


def _split_name(after_role: str) -> tuple[str | None, str]:
    """Split ' "name" [a] [ref=e1]' into ("name", ' [a] [ref=e1]')."""
    stripped = after_role.lstrip(" ")
    if not stripped.startswith('"'):
        return None, after_role
    end = _closing_quote(stripped)
    if end is None:
        return None, ""
    quoted = stripped[: end + 1]
    try:
        name = json.loads(quoted)
    except json.JSONDecodeError:
        name = quoted[1:-1]
    return name, stripped[end + 1 :]
