"""CLI fixtures: a CliContext with a fake terminal, scripted prompts and captured output."""

import io
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from vault.audit import AuditLog
from vault.cli import terminal
from vault.cli.context import CliContext
from vault.unlock.hello import HelloUnlocker


class FakeTty(io.StringIO):
    """A stdin that claims to be an interactive terminal."""

    def isatty(self) -> bool:
        return True


@dataclass
class CliHarness:
    """Builds a CliContext and records what the command printed and asked."""

    store_path: Path
    audit_path: Path
    signer: object
    secrets: list[str] = field(default_factory=list)
    answers: list[str] = field(default_factory=list)
    output: list[str] = field(default_factory=list)
    secret_prompts: list[str] = field(default_factory=list)

    def context(self, stdin: io.StringIO | None = None) -> CliContext:
        def read_secret(prompt: str) -> str:
            self.secret_prompts.append(prompt)
            return self.secrets.pop(0)

        return CliContext(
            store_path=self.store_path,
            audit=AuditLog(self.audit_path),
            unlocker_for=lambda _provider: HelloUnlocker(self.signer),
            stdin=stdin if stdin is not None else FakeTty(),
            read_secret=read_secret,
            ask_line=lambda _prompt: self.answers.pop(0),
            out=self.output.append,
        )


@pytest.fixture
def cli(tmp_path: Path, make_store, monkeypatch) -> CliHarness:
    """A harness over a vault holding one credential, unlocked by a fake Hello signer.

    FakeTty has no OS handle, so the Windows console check is replaced by
    "is it a FakeTty"; tests/cli/test_terminal.py covers the real check.
    """
    monkeypatch.setattr(terminal, "has_console_mode", lambda stream: isinstance(stream, FakeTty))
    store_path = tmp_path / "store.json"
    signer = make_store(store_path)
    return CliHarness(store_path, tmp_path / "audit.jsonl", signer)
