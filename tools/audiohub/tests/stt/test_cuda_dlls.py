"""Tests for audiohub.stt.cuda_dlls: finding and registering NVIDIA wheel DLLs.

Registration is tested with a fake `os.add_dll_directory`, a scratch PATH and
an empty registry, so the real process DLL search path is never touched.
"""

import importlib.util
import logging
import os
from pathlib import Path

import pytest

from audiohub.stt import cuda_dlls


def make_lib(root: Path, name: str, dll: str | None = "lib64_12.dll") -> Path:
    bin_dir = root / name / "bin"
    bin_dir.mkdir(parents=True)
    if dll:
        (bin_dir / dll).write_bytes(b"")
    return bin_dir.resolve()


@pytest.fixture
def windows(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Pretend to be on Windows; return the list of directories passed to add_dll_directory."""
    added: list[str] = []
    monkeypatch.setattr(cuda_dlls.sys, "platform", "win32")
    monkeypatch.setattr(cuda_dlls, "_registered", {})
    monkeypatch.setattr(os, "add_dll_directory", added.append, raising=False)
    monkeypatch.setenv("PATH", "original")
    return added


def test_finds_bin_dirs_that_hold_dlls(tmp_path: Path) -> None:
    cublas = make_lib(tmp_path, "cublas")
    cudnn = make_lib(tmp_path, "cudnn")
    assert cuda_dlls.find_nvidia_bin_dirs([tmp_path]) == sorted([cublas, cudnn])


def test_ignores_bin_dirs_without_dlls(tmp_path: Path) -> None:
    make_lib(tmp_path, "headers_only", dll=None)
    (tmp_path / "not_a_lib").write_text("")
    assert cuda_dlls.find_nvidia_bin_dirs([tmp_path]) == []


@pytest.mark.skipif(
    importlib.util.find_spec("nvidia") is None, reason="nvidia wheels not installed"
)
def test_default_roots_find_the_installed_cublas_and_cudnn() -> None:
    names = {path.parent.name for path in cuda_dlls.find_nvidia_bin_dirs()}
    assert {"cublas", "cudnn"} <= names


def test_registers_with_add_dll_directory_and_path(tmp_path: Path, windows: list[str]) -> None:
    cublas = make_lib(tmp_path, "cublas")
    assert cuda_dlls.register_nvidia_dll_dirs([tmp_path]) == [cublas]
    assert windows == [str(cublas)]
    assert os.environ["PATH"] == f"{cublas}{os.pathsep}original"


def test_second_registration_is_a_no_op(tmp_path: Path, windows: list[str]) -> None:
    make_lib(tmp_path, "cublas")
    cuda_dlls.register_nvidia_dll_dirs([tmp_path])
    path_after_first = os.environ["PATH"]
    assert cuda_dlls.register_nvidia_dll_dirs([tmp_path]) == []
    assert len(windows) == 1
    assert os.environ["PATH"] == path_after_first


def test_warns_when_no_dlls_are_found(
    tmp_path: Path, windows: list[str], caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger=cuda_dlls.__name__):
        assert cuda_dlls.register_nvidia_dll_dirs([tmp_path]) == []
    assert "no NVIDIA DLL directories found" in caplog.text


def test_does_nothing_off_windows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    make_lib(tmp_path, "cublas")
    monkeypatch.setattr(cuda_dlls.sys, "platform", "linux")
    monkeypatch.setenv("PATH", "original")
    assert cuda_dlls.register_nvidia_dll_dirs([tmp_path]) == []
    assert os.environ["PATH"] == "original"
