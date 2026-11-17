"""Shared fixtures for the security tests: a run context with a fixed repo root."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from analysis_chamber.agents.context import RunContext
from analysis_chamber.config import load_config
from analysis_chamber.runs import Manifest

# The tables use real-looking Windows paths, so the repo root is pinned to a sample root.
REPO_ROOT = Path(r"C:\work\Signal")

# Scripts already in the run folder, so the tables can check an Edit against the whole
# file after it (each edit's new text alone would pass).
_NOTEBOOK = {
    "cells": [
        {"id": "c1", "cell_type": "code", "source": ["import requests\n", "r = requests.get(URL)"]},
        {"id": "c2", "cell_type": "code", "source": "URL = 'https://example.org/x.csv'"},
    ]
}
EXISTING_FILES = {
    "code/old_fetch.py": "import requests\nr = requests.get('https://example.org/x.csv')\n",
    "code/old_send.py": "import subprocess\nsubprocess.run(['echo', 'x'])\n",
    "code/old_write.py": "df.to_csv('data/clean/t.csv')\n",
    "code/old.ipynb": json.dumps(_NOTEBOOK),
}


@pytest.fixture
def make_ctx(tmp_path: Path):
    """Build a RunContext whose run folder is outside the repo, with a given personal flag.

    The run folder holds EXISTING_FILES.
    """

    def build(personal: bool | None = True) -> RunContext:
        config = replace(
            load_config(tmp_path / "missing.toml"),
            repo_root=REPO_ROOT,
            analyses_root=REPO_ROOT / "life" / "analyses",
            private_root=tmp_path / "chamber-private",
        )
        run_dir = tmp_path / "chamber-private" / "2026-11-16-q"
        for name, text in EXISTING_FILES.items():
            (run_dir / name).parent.mkdir(parents=True, exist_ok=True)
            (run_dir / name).write_text(text, encoding="utf-8")
        manifest = Manifest(id="2026-11-16-q", question="q", personal=personal)
        return RunContext(run_dir=run_dir, manifest=manifest, config=config)

    return build
