"""Tests for list_transcripts and find_transcript_cwd against fake JSONL transcripts.

CLAUDE_CONFIG_DIR points the SDK's session listing at a temporary folder, so
the real listing code reads files shaped like the CLI's.
"""

from pathlib import Path

import pytest
from support.transcripts import write_transcript

from claude_sessions.repos import find_transcript_cwd, list_transcripts

OLD_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
NEW_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
OTHER_ID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"


@pytest.fixture
def config_dir(short_tmp: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config = short_tmp / "cfg"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config))
    return config


def test_lists_a_repos_sessions_newest_first_with_short_first_prompts(
    short_tmp: Path, config_dir: Path
) -> None:
    repo = short_tmp / "OtherRepo"
    other = short_tmp / "KeyForge"
    repo.mkdir()
    other.mkdir()
    write_transcript(config_dir, repo, OLD_ID, "Fix the login bug", mtime=1_700_000_000)
    long_prompt = "Refactor " + "very " * 60 + "much"
    write_transcript(config_dir, repo, NEW_ID, long_prompt, mtime=1_800_000_000)
    write_transcript(config_dir, other, OTHER_ID, "Unrelated")

    transcripts = list_transcripts(repo)

    assert [t.session_id for t in transcripts] == [NEW_ID, OLD_ID]
    assert transcripts[1].first_prompt == "Fix the login bug"
    assert len(transcripts[0].first_prompt) <= 120
    assert transcripts[0].first_prompt.endswith("…")
    assert transcripts[0].last_modified_ms == 1_800_000_000_000
    assert {t.session_id for t in list_transcripts(None)} == {OLD_ID, NEW_ID, OTHER_ID}


def test_finds_the_folder_a_session_ran_in(short_tmp: Path, config_dir: Path) -> None:
    repo = short_tmp / "ExampleRepo"
    repo.mkdir()
    write_transcript(config_dir, repo, OLD_ID, "hello")

    assert find_transcript_cwd(OLD_ID) == repo
    assert find_transcript_cwd(NEW_ID) is None
