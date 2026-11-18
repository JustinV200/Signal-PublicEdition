"""`setup doc <tool> <step>`: print the guide the registry names for one step.

Read-only. The setup window shows the guide inline (collapsed, as Markdown). It takes
only registry ids, never a path: the file is the step's `doc` in data/tools.json, and
even that must stay inside the repo root (no absolute path, no `..`, no symlink out).
"""

from pathlib import Path

from signal_setup import registry

# Exit code when the step names a guide this copy of Signal doesn't have (e.g. the
# copytone skill, which only the public edition ships).
EXIT_NO_GUIDE = 1


def guide_path(root: Path, tool_id: str, step_id: str) -> Path | None:
    """The guide file for one step, or None when the step names no guide.

    Raises:
        KeyError: An unknown tool or step id, or a guide path that leaves the repo root
            (main() turns either into exit 2).
    """
    doc = registry.by_id(tool_id).step(step_id).doc
    if not doc:
        return None
    relative = Path(doc)
    if relative.is_absolute() or relative.drive or ".." in relative.parts:
        raise KeyError(f"{tool_id}.{step_id}: guide {doc!r} isn't a path inside the repo")
    path = (root / relative).resolve()
    # resolve() follows symlinks, so a link that points out of the repo is caught here too.
    if not path.is_relative_to(root.resolve()):
        raise KeyError(f"{tool_id}.{step_id}: guide {doc!r} is outside the repo")
    return path


def show_guide(root: Path, tool_id: str, step_id: str) -> int:
    """Print the step's guide. Returns 0, or EXIT_NO_GUIDE with a plain sentence.

    Raises:
        KeyError: As guide_path().
    """
    path = guide_path(root, tool_id, step_id)
    if path is None:
        print("This step has no guide.")
        return EXIT_NO_GUIDE
    if not path.is_file():
        rel = path.relative_to(root.resolve()).as_posix()
        print(f"The guide for this step ({rel}) isn't in this copy of Signal.")
        return EXIT_NO_GUIDE
    print(path.read_text("utf-8"))
    return 0
