# analysis-chamber

Takes a question, drafts a plan for the user to check, then collects data (web, Signal's tools, files, public APIs), analyses it, has a fresh critic check the work, and leaves a report, a writeup and an agent you can ask follow-up questions. Runs happen in a local daemon on the Claude Agent SDK.

- Package contract: [DESIGN.md](DESIGN.md)
- Settings: [config.example.toml](config.example.toml). Put overrides in `config.toml` here (gitignored).

**Status (2026-11-16):** each package's README gives its status.

## Setup

`register.ps1` sets up everything (venv, analysis kit, at-login daemon task, `.mcp.json` entry, private folder); `-TaskOnly` registers just the scheduled task, which is what the setup tool uses. Undo with `unregister.ps1`.

## Tests

From this folder: `uv run --frozen pytest`, `uv run --frozen ruff check .` and `uv run --frozen ruff format --check .`.

From the repo root, pass the tests folder: `uv run --project tools/analysis-chamber --frozen pytest tools/analysis-chamber/tests`.
