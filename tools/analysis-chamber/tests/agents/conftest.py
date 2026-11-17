"""Shared fixture for the agents tests: a run context in tmp_path."""

from dataclasses import replace
from pathlib import Path

import pytest

from analysis_chamber.agents import RunContext
from analysis_chamber.config import load_config
from analysis_chamber.runs import Manifest, create_run_dir


@pytest.fixture
def ctx(tmp_path: Path) -> RunContext:
    repo = tmp_path / "Signal"
    repo.mkdir()
    config = replace(
        load_config(tmp_path / "missing.toml"),
        repo_root=repo,
        private_root=tmp_path / "private",
        kit_venv=tmp_path / "kit",
        playbook_path=repo / "playbook",
        signup_mail_account="signup@example.test",
    )
    run_dir = create_run_dir(config.private_root, "2026-11-16-q")
    return RunContext(run_dir, Manifest(id="2026-11-16-q", question="q?"), config)
