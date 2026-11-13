"""Tests for browser-tool-visit's CLI: the out file is written on every exit it controls."""

import json

import pytest

from browser_tool.backends import BackendError
from browser_tool.visit import cli, launch

PLAN = {"targets": [{"key": "a", "url": "https://lms.example.localhost/", "site": "moodle"}]}


class FailingBackend:
    """A backend whose Edge never starts, as when another Edge holds the profile."""

    guest_block = None
    idle_close_s = None
    downloads_incoming = None
    job_label = None

    def __init__(self, settings):
        self.settings = settings

    async def open_context(self, playwright, policy):
        raise BackendError("the profile is in use")

    async def is_job_stale(self):
        return False

    def close(self):
        pass


def _config(tmp_path, allow_all: bool) -> str:
    profile = (tmp_path / "profile").as_posix()
    return (
        f'[browser]\nprofile_dir = "{profile}"\nheadless = true\n'
        f'[policy]\nallow = ["lms.example.localhost"]\nallow_all = {str(allow_all).lower()}\n'
        f'[duo]\nhub_token_file = "{(tmp_path / "no-hub-token").as_posix()}"\n'
    )


@pytest.mark.parametrize(
    ("allow_all", "is_locked", "status"),
    [
        # The profile's lock file is there and the launch keeps failing: busy.
        (False, True, "busy"),
        # The same failure with no lock file is some other launch problem.
        (False, False, "error"),
        # A config that allows every host could be the desktop one: refused unlaunched.
        (True, True, "error"),
    ],
    ids=["busy", "launch-error", "allow-all-refused"],
)
def test_the_out_file_is_written_on_a_failed_launch(
    tmp_path, monkeypatch, allow_all, is_locked, status
):
    monkeypatch.setattr(cli, "LocalBackend", FailingBackend)
    monkeypatch.setattr(launch, "PROFILE_LOCK_WAIT_S", 0.05)
    monkeypatch.setattr(launch, "PROFILE_LOCK_POLL_S", 0.01)
    (tmp_path / "profile").mkdir()
    if is_locked:
        (tmp_path / "profile" / launch.PROFILE_LOCKFILE).write_text("")
    config, plan, out = tmp_path / "c.toml", tmp_path / "plan.json", tmp_path / "out.json"
    config.write_text(_config(tmp_path, allow_all), encoding="utf-8")
    plan.write_text(json.dumps(PLAN), encoding="utf-8")

    with pytest.raises(SystemExit) as exit_info:
        cli.main(["--config", str(config), "--plan", str(plan), "--out", str(out)])

    assert exit_info.value.code == 1
    assert json.loads(out.read_text(encoding="utf-8")) == {"status": status, "pages": []}
