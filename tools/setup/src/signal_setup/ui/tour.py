"""The guided tour: GUIDE.md shown one section at a time, or one topic on its own.

GUIDE.md (repo root) is the single source, for people and for the setup skill.
"""

from pathlib import Path

from signal_setup.terminal import BOLD, pause, style

GUIDE_FILE = "GUIDE.md"


def sections(root: Path) -> list[tuple[str, str]]:
    """GUIDE.md split at its '## ' headings into (heading, body) pairs."""
    parts = (root / GUIDE_FILE).read_text("utf-8").split("\n## ")[1:]
    return [(p.split("\n", 1)[0].strip(), p.split("\n", 1)[1].strip()) for p in parts]


def run(root: Path, topic: str = "") -> None:
    """Show the sections matching `topic` (all of them when empty), pausing between each."""
    chosen = [s for s in sections(root) if topic.lower() in s[0].lower()]
    if not chosen:
        print(
            f"No tour section matches {topic!r}. Sections: "
            + ", ".join(h for h, _ in sections(root))
        )
        return
    for number, (heading, body) in enumerate(chosen, 1):
        print(style(f"\n{heading}", BOLD) + f"  ({number}/{len(chosen)})\n\n{body}\n")
        if number < len(chosen) and not pause():
            return
