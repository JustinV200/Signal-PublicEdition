"""Shared fixtures for the setup tool's tests: the real repo files some tests read.

A few registry files exist only in the public edition (other tools' example configs, the
root README, AGENTS.md's setting marker). Outside the public edition, a test that reads one
skips when it's missing instead of failing. In the public edition nothing skips: a missing
file or marker there is real drift, so the test fails as it always did.
"""

from collections.abc import Callable
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
# Only the public edition ships it; there a missing file or marker is real drift, so let
# the test fail.
IS_PUBLIC_EDITION = (REPO / "COMMERCIAL.md").is_file()
# Files that only count as present when they hold this marker (the private edition's
# AGENTS.md has the rule's prose but not setup's marker).
REQUIRED_MARKERS = {"AGENTS.md": "<!-- setting:context-handoff-percent -->"}


@pytest.fixture
def repo_file() -> Callable[[str], Path]:
    """A function giving the real repo file at a relative path, or skipping the test.

    Outside the public edition the function skips when the file is missing, or lacks its
    REQUIRED_MARKERS entry. In the public edition it never skips.
    """

    def find(relative: str) -> Path:
        path = REPO / relative
        if IS_PUBLIC_EDITION:
            return path
        if not path.is_file():
            pytest.skip(f"public-edition file not in this checkout: {relative}")
        marker = REQUIRED_MARKERS.get(relative)
        if marker and marker not in path.read_text("utf-8"):
            pytest.skip(f"public-edition marker not in this checkout: {marker} in {relative}")
        return path

    return find
