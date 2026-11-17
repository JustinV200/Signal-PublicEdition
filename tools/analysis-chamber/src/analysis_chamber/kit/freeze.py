"""Parser for `uv pip freeze` / `uv pip compile` output, shared by run_venv and install."""

from __future__ import annotations


def parse_freeze(text: str) -> dict[str, str]:
    """Map package name (lowercase) to version from `pkg==version` or `pkg @ url` lines.

    URL, git and local-wheel installs keep the url as their version. Comment and other
    lines are ignored.
    """
    pins = {}
    for line in text.splitlines():
        name, sep, version = line.strip().partition(" @ ")
        if not sep:
            name, sep, version = line.strip().partition("==")
        if sep:
            pins[name.lower()] = version
    return pins
