"""Fixtures shared by the permission tests.

- `make_junction`: Windows directory junctions for the path-resolution tests.

Test modules can't import each other (pytest runs with --import-mode=importlib),
so helpers are handed out as fixtures.
"""

from collections.abc import Callable
from pathlib import Path

import pytest


@pytest.fixture
def make_junction() -> Callable[[Path, Path], None]:
    """Return a function that makes `link` a junction to the folder `target` (skips off Windows)."""
    winapi = pytest.importorskip("_winapi")

    def make(link: Path, target: Path) -> None:
        target.mkdir(parents=True, exist_ok=True)
        winapi.CreateJunction(str(target), str(link))

    return make
