"""Tests for image path checks: the /files boundary must reject remote and escaping paths early."""

import _winapi
import json
import os
from pathlib import Path

import pytest

from whiteboard.display.scene import SceneError, SceneStore, resolve_image_path

STATE = "tools/whiteboard/.state"

BAD_PATHS = [
    r"\\attacker\share\x.png",  # UNC: resolving it would open an SMB connection
    "//attacker/share/x.png",  # UNC with forward slashes
    r"/\attacker\share\x.png",  # mixed-slash UNC
    r"\\?\C:\Windows\x.png",  # device path
    "C:/Windows/x.png",  # drive-absolute
    "/Windows/x.png",  # rooted
    f"{STATE}/notes.txt:x.png",  # alternate data stream
    f"{STATE}/../../../secret.png",  # parent escape
    f"{STATE}/snapshots/CON.png",  # Windows device name
    f"{STATE}/x.png.",  # trailing dot Windows would strip
    f"{STATE}/x.gif",  # not an image type we serve
    "tools/other/x.png",  # outside the allowed folders
]


@pytest.mark.parametrize("raw_path", BAD_PATHS)
def test_bad_paths_are_rejected_before_any_filesystem_call(
    raw_path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    touched: list[str] = []

    def spy(name: str):
        def record(*args: object, **kwargs: object) -> None:
            touched.append(name)
            raise AssertionError(f"{name} called for {raw_path!r}")

        return record

    monkeypatch.setattr(Path, "resolve", spy("resolve"))
    monkeypatch.setattr(Path, "stat", spy("stat"))
    monkeypatch.setattr(os.path, "realpath", spy("realpath"))
    with pytest.raises(SceneError):
        resolve_image_path(raw_path)
    assert touched == []


def test_junction_out_of_the_state_folder_is_rejected(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    state = repo / STATE
    state.mkdir(parents=True)
    (state / "ok.png").write_bytes(b"png")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.png").write_bytes(b"png")
    # A junction needs no admin rights, unlike a symlink. CPython's own tests use this helper.
    _winapi.CreateJunction(str(outside), str(state / "link"))

    assert resolve_image_path(f"{STATE}/ok.png", repo_root=repo) == (state / "ok.png").resolve()
    with pytest.raises(SceneError, match="outside"):
        resolve_image_path(f"{STATE}/link/secret.png", repo_root=repo)


def test_saved_scene_with_a_pruned_snapshot_still_loads(tmp_path: Path) -> None:
    # Regression: loading used to check the file existed, so one rotated-out
    # snapshot moved the whole scene to scene.json.bad on restart.
    item = {"id": "snap", "kind": "image", "x": 0, "y": 0, "w": 10, "h": 10}
    item["content"] = f"{STATE}/snapshots/long-gone.png"
    path = tmp_path / "scene.json"
    path.write_text(json.dumps({"items": [item]}), encoding="utf-8")
    assert [loaded.id for loaded in SceneStore(path).load().items] == ["snap"]
