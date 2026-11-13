"""Fixtures shared by every test folder."""

import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture
def short_tmp() -> Iterator[Path]:
    """A temporary folder with a short path.

    Claude Code names a transcript folder after the full working-directory
    path, so a fake transcript for a folder under pytest's long tmp_path
    passes Windows' 260-character path limit.
    """
    folder = Path(tempfile.mkdtemp(prefix="cs")).resolve()
    yield folder
    shutil.rmtree(folder, ignore_errors=True)
