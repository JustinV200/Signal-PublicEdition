"""Tests for find_repos and resolve_repo on a temporary folder tree."""

from pathlib import Path

import pytest
from support.transcripts import write_transcript

from claude_sessions.repos import RepoNotFoundError, find_repos, resolve_repo


def _make_repo(path: Path, as_file: bool = False) -> Path:
    path.mkdir(parents=True)
    marker = path / ".git"
    if as_file:
        # Worktrees and submodules have a .git file instead of a folder.
        marker.write_text("gitdir: elsewhere", encoding="utf-8")
    else:
        marker.mkdir()
    return path


def test_finds_repos_within_depth_and_skips_dependency_folders(tmp_path: Path) -> None:
    root = tmp_path / "the owner"
    _make_repo(root / "Signal")
    _make_repo(root / "Projects" / "KeyForge" / "inner")
    _make_repo(root / "Projects" / "worktree", as_file=True)
    _make_repo(root / "Signal" / "vendored")  # nested inside another repo
    _make_repo(root / "web" / "node_modules" / "pkg")
    _make_repo(root / "tool" / ".venv" / "lib")
    _make_repo(root / "a" / "b" / "c" / "d" / "too-deep")

    repos = find_repos([root], max_depth=4, claude_projects_dir=tmp_path / "none")

    assert [repo.name for repo in repos] == ["inner", "Signal", "vendored", "worktree"]
    assert all(repo.is_git and repo.path.is_absolute() for repo in repos)


def test_adds_folders_claude_ran_in_but_only_under_the_roots(short_tmp: Path) -> None:
    root = short_tmp / "the owner"
    project = root / "Projects" / "OtherRepo"
    _make_repo(project / "Otherrepo")
    outside = short_tmp / "scratch"
    outside.mkdir()
    config_dir = short_tmp / "claude"
    write_transcript(config_dir, project, "11111111-1111-4111-8111-111111111111", "hi")
    write_transcript(config_dir, outside, "22222222-2222-4222-8222-222222222222", "hi")

    repos = find_repos([root], max_depth=4, claude_projects_dir=config_dir / "projects")

    assert [(repo.name, repo.is_git) for repo in repos] == [("OtherRepo", False), ("Otherrepo", True)]
    # The exact spelling picks the folder the owner works in over its inner repo.
    assert resolve_repo("OtherRepo", repos, [root]) == project.resolve()


def test_resolve_repo_accepts_paths_and_unique_names_and_reports_ambiguity(tmp_path: Path) -> None:
    first = _make_repo(tmp_path / "x" / "docs-site")
    second = _make_repo(tmp_path / "y" / "docs-api")
    repos = find_repos([tmp_path], max_depth=2, claude_projects_dir=tmp_path / "none")

    assert resolve_repo(str(first), repos, [tmp_path]) == first.resolve()
    assert resolve_repo("site", repos, [tmp_path]) == first.resolve()
    with pytest.raises(RepoNotFoundError, match="matches 2 repos"):
        resolve_repo("docs", repos, [tmp_path])
    with pytest.raises(RepoNotFoundError, match="No repo name matches"):
        resolve_repo("nothing", repos, [tmp_path])
    with pytest.raises(RepoNotFoundError, match="isn't an existing folder"):
        resolve_repo(str(second / "missing"), repos, [tmp_path])
