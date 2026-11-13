"""read_checked_file's path rules: which local files upload_file and read_download read.

Pure, on tmp_path.
"""

import _winapi
import os
from collections.abc import Callable
from pathlib import Path

import pytest
from support.local_files import no_disk

from browser_tool.actions import ActionError
from browser_tool.actions.local_files import read_checked_file

MAX_BYTES = 1024


def plain(root: Path) -> Path:
    """A small text file in the root."""
    path = root / "notes.txt"
    path.write_text("hello")
    return path


def named(*parts: str) -> Callable[[Path], Path]:
    """A small file at root/parts..., folders made as needed."""

    def make(root: Path) -> Path:
        path = root.joinpath(*parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x")
        return path

    return make


def through_junction(root: Path) -> Path:
    """A file reached through a junction inside the root that points inside it."""
    real = root / "real"
    real.mkdir()
    (real / "a.txt").write_text("x")
    _winapi.CreateJunction(str(real), str(root / "jump"))
    return root / "jump" / "a.txt"


def junction_to_outside(root: Path) -> Path:
    """A junction inside the root to a folder outside it."""
    outside = root.parent / "outside"
    outside.mkdir()
    (outside / "a.txt").write_text("x")
    _winapi.CreateJunction(str(outside), str(root / "out"))
    return root / "out" / "a.txt"


def hard_link(root: Path) -> Path:
    """A second name for a file outside the root."""
    outside = root.parent / "secret.txt"
    outside.write_text("x")
    os.link(outside, root / "linked.txt")
    return root / "linked.txt"


def too_big(root: Path) -> Path:
    path = root / "big.bin"
    path.write_bytes(b"x" * (MAX_BYTES + 1))
    return path


ROWS = {
    "plain_file": (plain, None),
    "relative_path": (lambda root: Path("notes.txt"), "full path"),
    "missing": (lambda root: root / "nope.txt", "no such file"),
    "outside_the_roots": (lambda root: named("..", "elsewhere.txt")(root), "must come from"),
    "a_folder": (lambda root: root, "single name"),
    "junction_inside": (through_junction, "link, junction"),
    "junction_outside": (junction_to_outside, "link, junction"),
    "hard_link": (hard_link, "single name"),
    "dot_env": (named(".env"), "never read"),
    "dot_env_local": (named(".env.local"), "never read"),
    "dot_env_suffix": (named("prod.env"), "never read"),
    "browser_profile": (named(".profile-checker", "Cookies"), "never read"),
    "saved_cookies": (named(".State", "cookies.bin"), "never read"),
    "vault_folder": (named("Signal-Vault", "vault.bin"), "never read"),
    "pem_key": (named("server.PEM"), "never read"),
    "ssh_key": (named("id_ed25519"), "never read"),
    "over_the_cap": (too_big, "MB limit"),
}
# Refused before any filesystem call: a UNC path would open an SMB connection.
LEXICAL_ROWS = {
    "unc_share": (lambda root: r"\\attacker.example\share\notes.txt", "on a drive"),
    "forward_slash_unc": (lambda root: "//attacker.example/share/x.txt", "on a drive"),
    "verbatim_prefix": (lambda root: rf"\\?\{plain(root)}", "on a drive"),
    "device_namespace": (lambda root: r"\\.\PhysicalDrive0", "on a drive"),
    "drive_then_unc": (lambda root: r"C:\\attacker.example\share\x.txt", "on a drive"),
    "con_in_the_root": (lambda root: root / "CON", "Windows device"),
    "nul_with_extension": (lambda root: root / "nul.txt", "Windows device"),
    "com_with_trailing_dot": (lambda root: root / "com1 .log.", "Windows device"),
    "data_stream": (lambda root: Path(f"{plain(root)}:hidden"), "data stream"),
    "outside_the_roots_lexically": (lambda root: root / ".." / "x.txt", "must come from"),
}


@pytest.mark.parametrize(("make", "refused"), ROWS.values(), ids=ROWS.keys())
def test_only_plain_files_under_the_roots_are_read(tmp_path, make, refused):
    root = tmp_path / "life"
    root.mkdir()
    path = make(root)
    if refused is None:
        upload = read_checked_file(str(path), [root], MAX_BYTES)
        assert (upload.name, upload.data, upload.mime) == ("notes.txt", b"hello", "text/plain")
        return
    with pytest.raises(ActionError, match=refused) as refusal:
        read_checked_file(str(path), [root], MAX_BYTES)
    assert str(refusal.value).startswith("refused")


@pytest.mark.parametrize(("make", "refused"), LEXICAL_ROWS.values(), ids=LEXICAL_ROWS.keys())
def test_network_device_and_outside_paths_are_refused_without_touching_disk(
    tmp_path, monkeypatch, make, refused
):
    root = tmp_path / "life"
    root.mkdir()
    path = make(root)

    with no_disk(monkeypatch), pytest.raises(ActionError, match=refused):
        read_checked_file(str(path), [root], MAX_BYTES)


def test_a_link_is_refused_before_anything_follows_it(tmp_path, monkeypatch):
    # resolve() would follow a link to a network share; the lstat walk must stop it first.
    root = tmp_path / "life"
    root.mkdir()
    path = junction_to_outside(root)

    def no_follow(*args, **kwargs):
        raise AssertionError("followed a link")

    monkeypatch.setattr(os.path, "realpath", no_follow)
    with pytest.raises(ActionError, match="link, junction"):
        read_checked_file(str(path), [root], MAX_BYTES)
