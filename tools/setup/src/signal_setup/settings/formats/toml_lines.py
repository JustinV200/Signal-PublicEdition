"""TOML settings: read with tomllib, write by replacing one `key = ...` line (or block).

Keys are dotted, "table.name" (or just "name" for a top-level key). Writing keeps every
comment: it replaces the live key (a multi-line array included), else a commented-out
`# name = ...` example line in that table, else appends the key to its table (adding
the table at the end if it's missing).
"""

import json
import re
import tomllib
from typing import Any

_HEADER = re.compile(r"^\s*\[([^\[\]]+)\]\s*(#.*)?$")


def entries(text: str) -> list[tuple[str, Any]]:
    """Every leaf (dotted key, value); tables are walked, arrays are one value."""
    found: list[tuple[str, Any]] = []

    def walk(prefix: str, table: dict[str, Any]) -> None:
        for name, value in table.items():
            if isinstance(value, dict):
                walk(f"{prefix}{name}.", value)
            else:
                found.append((f"{prefix}{name}", value))

    walk("", tomllib.loads(text))
    return found


def read(text: str, key: str) -> Any:
    """The key's value, or None."""
    return dict(entries(text)).get(key)


def _section(lines: list[str], table: str) -> tuple[int, int] | None:
    """(first line, end line) of `table`'s body; table "" is the top level."""
    start = 0 if table == "" else None
    for i, line in enumerate(lines):
        match = _HEADER.match(line)
        if not match:
            continue
        if start is not None:
            return start, i
        if match.group(1).strip() == table:
            start = i + 1
    return None if start is None else (start, len(lines))


def _value_end(lines: list[str], i: int) -> int:
    """The last line of the value that starts on line i (multi-line arrays span lines)."""
    depth, quote = 0, ""
    for j in range(i, len(lines)):
        line = lines[j].split("=", 1)[1] if j == i else lines[j]
        k = 0
        while k < len(line):
            ch = line[k]
            if quote:
                if ch == "\\" and quote == '"':
                    k += 1
                elif ch == quote:
                    quote = ""
            elif ch in "\"'":
                quote = ch
            elif ch == "#":
                break
            elif ch in "[{":
                depth += 1
            elif ch in "]}":
                depth -= 1
            k += 1
        if depth <= 0:
            return j
    return len(lines) - 1


def write(text: str, key: str, literal: str) -> str:
    """`text` with `key = literal`; see the module docstring for where it goes."""
    table, _, name = key.rpartition(".")
    lines = text.split("\n")
    span = _section(lines, table)
    if span is None:
        return text.rstrip("\n") + f"\n\n[{table}]\n{name} = {literal}\n"
    start, end = span
    live = re.compile(rf"^(\s*){re.escape(name)}\s*=")
    commented = re.compile(rf"^(\s*)#\s*{re.escape(name)}\s*=")
    for pattern in (live, commented):
        for i in range(start, end):
            match = pattern.match(lines[i])
            if match:
                last = _value_end(lines, i) if pattern is live else i
                lines[i : last + 1] = [f"{match.group(1)}{name} = {literal}"]
                return "\n".join(lines)
    while end > start and not lines[end - 1].strip():
        end -= 1
    lines.insert(end, f"{name} = {literal}")
    return "\n".join(lines)


def literal(value: Any) -> str:
    """A TOML literal: "string", true/false, a number, or ["a", "b"]."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return "[" + ", ".join(literal(v) for v in value) + "]"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    return str(value)
