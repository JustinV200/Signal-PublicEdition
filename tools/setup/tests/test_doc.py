"""`setup doc <tool> <step>`: prints only a guide the registry names, inside the repo."""

from dataclasses import replace
from pathlib import Path

import pytest

from signal_setup import registry
from signal_setup.cli import main

# A guide reached through `tools/out`, a folder link inside the fake repo that points out
# of it (made in the test).
LINK_OUT = "tools/out/outside.md"


def _link_folder(link: Path, target: Path) -> None:
    """Make `link` a folder link to `target`, or skip the test where none can be made.

    A symlink needs admin or Developer Mode on Windows; a junction needs neither and
    resolve() follows it the same way. `_winapi` is CPython's own Windows module.
    """
    try:
        link.symlink_to(target, target_is_directory=True)
        return
    except OSError:
        pass  # try a junction below
    try:
        import _winapi

        _winapi.CreateJunction(str(target), str(link))
    except (ImportError, OSError):
        pytest.skip("no folder link can be made here")


def _vault_add_doc(doc: str) -> tuple[registry.Tool, ...]:
    """The registry with vault's `add` step naming `doc` as its guide."""
    tools = registry.load()
    vault = registry.by_id("vault")
    steps = tuple(replace(s, doc=doc) if s.id == "add" else s for s in vault.steps)
    return tuple(replace(t, steps=steps) if t.id == "vault" else t for t in tools)


@pytest.mark.parametrize(
    ("tool", "step", "doc", "exit_code", "printed"),
    [
        ("nope", "add", None, 2, ""),
        ("vault", "nope", None, 2, ""),
        # A registry entry that points out of the repo is refused even though the file exists.
        ("vault", "add", "../outside.md", 2, ""),
        # Passes the path checks, but resolves outside the repo.
        ("vault", "add", LINK_OUT, 2, ""),
        ("vault", "add", "tools/vault/README.md", 0, "# A guide"),
        # A guide this copy doesn't ship (copytone in the private edition): a sentence, no crash.
        ("vault", "add", "tools/gone.md", 1, "isn't in this copy of Signal"),
    ],
)
def test_doc_prints_only_a_registry_guide_inside_the_repo(
    tmp_path: Path, monkeypatch, capsys, tool, step, doc, exit_code, printed
) -> None:
    root = tmp_path / "repo"
    (root / "tools" / "vault").mkdir(parents=True)
    (root / "tools" / "vault" / "README.md").write_text("# A guide\n", "utf-8")
    outside = tmp_path / "outside.md"
    outside.write_text("# Not for the page\n", "utf-8")
    monkeypatch.setattr(main, "REPO_ROOT", root)
    if doc == LINK_OUT:
        _link_folder(root / "tools" / "out", tmp_path)
    if doc is not None:
        tools = _vault_add_doc(doc)
        monkeypatch.setattr(registry, "load", lambda: tools)

    assert main.main(["doc", tool, step]) == exit_code

    out = capsys.readouterr().out
    assert printed in out
    assert "Not for the page" not in out
