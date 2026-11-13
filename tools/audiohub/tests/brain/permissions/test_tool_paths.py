"""Tests for finding a tool call's paths and resolving them against the project."""

from pathlib import Path

import pytest

from audiohub.brain.permissions.tool_paths import relative_parts, target_paths

PROJECT = Path(r"C:\src\Signal")


def is_outside(path: str, root: Path) -> bool:
    """Outside root once resolved: untrusted (None) or starting with "..".

    secret_paths relies on relative_parts reading paths this way.
    """
    parts = relative_parts(path, root)
    return parts is None or parts[:1] == ("..",)


@pytest.mark.parametrize(
    ("tool_name", "tool_input", "expected"),
    [
        (
            "Edit",
            {"file_path": "a.py", "notebook_path": "b.ipynb", "path": "src", "other": "x"},
            ["a.py", "b.ipynb", "src"],
        ),
        ("Glob", {"pattern": "**/*.py"}, ["**/*.py"]),  # Glob's pattern is a path
        ("Grep", {"pattern": r"C:\\Users"}, []),  # Grep's is a regex
        ("Read", {"file_path": "", "path": 3}, []),  # empty and non-string fields
    ],
)
def test_target_paths(tool_name: str, tool_input: dict[str, object], expected: list[str]) -> None:
    assert target_paths(tool_name, tool_input) == expected


@pytest.mark.parametrize(
    "path",
    [
        r"C:\src\Signal",
        r"C:\src\Signal\tools\audiohub\README.md",
        "tools/audiohub",
        "**/*.py",
        r"C:\src\signal\AGENTS.md",  # Windows paths ignore case
        "tools/../AGENTS.md",
    ],
)
def test_paths_inside_the_project(path: str) -> None:
    assert not is_outside(path, PROJECT)


@pytest.fixture
def linked_project(tmp_path: Path, make_junction) -> Path:
    """A project folder whose "link" subfolder is a junction to a folder outside it."""
    project = tmp_path / "Signal"
    project.mkdir()
    make_junction(project / "link", tmp_path / "elsewhere")
    return project


@pytest.mark.parametrize(
    "path",
    [
        r"C:\Users\owner\.ssh\id_ed25519",
        "~/.ssh/id_ed25519",  # "~" is expanded, not taken as a folder in the project
        "../other-repo/secrets.txt",
        "{project}Secrets/key.txt",  # a sibling that shares the prefix
        "/etc/passwd",  # rooted path on the project's drive
        r"D:\backup",  # another drive
        "C:/Users/**/*.pem",
        "link/evil.txt",  # a junction inside the project that leads out of it
    ],
)
def test_paths_outside_the_project(linked_project: Path, path: str) -> None:
    assert is_outside(path.format(project=linked_project), linked_project)
