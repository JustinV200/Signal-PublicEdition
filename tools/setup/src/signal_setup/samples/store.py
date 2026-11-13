"""Saves writing samples into the copytone skill's samples/ folder and counts them."""

import re
from pathlib import Path

SAMPLES_DIR = Path(".claude") / "skills" / "copytone" / "samples"
TARGET_RANGE = (5, 15)  # enough for a voice across registers, few enough to read every one
SAMPLE_KINDS = ("email", "writing", "message", "code")


def samples_dir(root: Path) -> Path:
    """The samples folder, created if missing."""
    path = root / SAMPLES_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def sample_count(root: Path) -> int:
    """How many samples there are (the folder's README doesn't count)."""
    return sum(1 for p in samples_dir(root).iterdir() if p.is_file() and p.name != "README.md")


def _slug(name: str) -> str:
    """A short file-name-safe version of `name`."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "sample"


def save_sample(root: Path, kind: str, name: str, text: str) -> Path:
    """Save `text` as `<kind>-<name>.md`, never overwriting. Raises ValueError on empty text."""
    if not text.strip():
        raise ValueError("the sample is empty")
    if kind not in SAMPLE_KINDS:
        raise ValueError(f"kind must be one of {', '.join(SAMPLE_KINDS)}")
    folder, stem = samples_dir(root), f"{kind}-{_slug(name)}"
    path, number = folder / f"{stem}.md", 2
    while path.exists():
        path, number = folder / f"{stem}-{number}.md", number + 1
    path.write_text(text.strip() + "\n", "utf-8")
    return path
