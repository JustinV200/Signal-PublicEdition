"""Checks for the programs Signal's tools need (uv, Edge, Node, Docker, Claude Code).

Each check only looks; nothing is installed. A failed check comes with a hint saying
where to get the program, which setup shows before the tool's steps run.
"""

import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

# Where Edge installs on Windows (the browser tool drives the installed Edge, not Playwright's).
EDGE_PATHS = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
)


@dataclass(frozen=True)
class Prereq:
    """A program a tool needs: how to find it and where to get it."""

    name: str
    is_present: Callable[[], bool]
    hint: str


def _on_path(*names: str) -> Callable[[], bool]:
    """A check that passes when any of `names` is on PATH."""
    return lambda: any(shutil.which(n) for n in names)


def _has_edge() -> bool:
    """True if Edge is installed (Windows paths, or microsoft-edge on PATH elsewhere)."""
    return any(Path(p).exists() for p in EDGE_PATHS) or bool(
        shutil.which("microsoft-edge") or shutil.which("msedge")
    )


def _has_claude() -> bool:
    """True if the Claude Code CLI is on PATH or in npm's global folder."""
    appdata = os.environ.get("APPDATA", "")
    return bool(shutil.which("claude")) or Path(appdata, "npm", "claude.cmd").exists()


PREREQS: dict[str, Prereq] = {
    "uv": Prereq("uv", _on_path("uv"), "https://docs.astral.sh/uv/ (it brings Python 3.12)"),
    "edge": Prereq("Microsoft Edge", _has_edge, "https://www.microsoft.com/edge"),
    "node": Prereq("Node.js (npm)", _on_path("npm"), "https://nodejs.org (LTS)"),
    "docker": Prereq(
        "Docker Desktop", _on_path("docker"), "https://www.docker.com/products/docker-desktop/"
    ),
    "claude": Prereq(
        "Claude Code CLI", _has_claude, "https://docs.anthropic.com/en/docs/claude-code"
    ),
}


def missing(names: tuple[str, ...] | list[str]) -> list[Prereq]:
    """The prerequisites in `names` that aren't installed. Raises KeyError on an unknown name."""
    return [PREREQS[n] for n in dict.fromkeys(names) if not PREREQS[n].is_present()]
