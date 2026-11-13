"""Tests for Lighting: which backends run, overrun and broken-config handling, on fakes."""

import threading
from collections.abc import Sequence
from pathlib import Path

import pytest
from support.openrgb_fakes import FakeDevice, FakeMode, FakeOpenRgb, FakeProfile, make_server

from sleepmode.config import DAY_PROFILE
from sleepmode.lighting import Lighting

OFF_ARGV = ("vendor-cli", "--lights", "off")
RESTORE_ARGV = ("vendor-cli", "--lights", "on")
COMMANDS = '[lighting]\noff_commands = [["vendor-cli", "--lights", "off"]]\n'
COMMANDS += 'restore_commands = [["vendor-cli", "--lights", "on"]]\n'
DISABLED = COMMANDS + "enabled = false\n"
OPENRGB_LINE = "OpenRGB turned off 2 of 2 devices"
COMMANDS_LINE = "Ran 1 of 1 lighting commands"


@pytest.mark.parametrize(
    ("has_openrgb", "config", "expected_lines", "expected_runs"),
    [
        (True, "", [OPENRGB_LINE], []),
        (False, COMMANDS, [COMMANDS_LINE], [OFF_ARGV, RESTORE_ARGV]),
        (True, COMMANDS, [OPENRGB_LINE, COMMANDS_LINE], [OFF_ARGV, RESTORE_ARGV]),
        (True, DISABLED, [], []),  # leaves everything alone
    ],
    ids=["openrgb only", "commands only", "both", "disabled"],
)
def test_each_backend_runs_only_when_it_has_something(
    tmp_path: Path,
    has_openrgb: bool,
    config: str,
    expected_lines: list[str],
    expected_runs: list[tuple[str, ...]],
) -> None:
    config_path = tmp_path / "sleepmode.toml"
    config_path.write_text(config, encoding="utf-8")
    server = make_server()
    server.profiles.append(FakeProfile(DAY_PROFILE))
    runs: list[tuple[str, ...]] = []

    def run(argv: Sequence[str], timeout_s: float) -> None:
        runs.append(tuple(argv))

    # Absent OpenRGB: open_openrgb answers None when there's no server and no OpenRGB.exe.
    opener = server.opener() if has_openrgb else (lambda exe_path: None)
    lighting = Lighting(config_path, open_session=opener, run=run)

    off = lighting.off(may_snapshot=True)
    restore = lighting.restore()

    assert [line.split(",")[0] for line in off.lines] == expected_lines
    assert off.notes == () and restore.notes == ()
    assert runs == expected_runs
    is_openrgb_used = has_openrgb and config != DISABLED
    assert all(device.is_dark for device in server.devices) == is_openrgb_used
    assert server.loaded == ([DAY_PROFILE] if is_openrgb_used else [])


class StuckDevice(FakeDevice):
    """A device whose change hangs until released, then fails like a closed socket."""

    def __init__(self, name: str, released: threading.Event) -> None:
        super().__init__(name)
        self._released = released

    def set_mode(self, mode: FakeMode) -> None:
        self._released.wait(timeout=5)
        raise ConnectionError("the socket was closed")


def test_an_overrun_off_step_is_abandoned_and_changes_nothing_after(tmp_path: Path) -> None:
    released = threading.Event()
    later = FakeDevice("Mouse")
    server = FakeOpenRgb([StuckDevice("Keyboard", released), later], [FakeProfile(DAY_PROFILE)])
    lighting = Lighting(tmp_path / "sleepmode.toml", server.opener(), step_timeout_s=0.2)

    off = lighting.off(may_snapshot=True)
    assert any("OpenRGB couldn't turn the lights off" in note for note in off.notes)
    # Closed at the deadline, so a read stuck on it would raise instead of spinning.
    assert server.disconnects == 1
    lighting.restore()  # the wake
    released.set()
    for thread in threading.enumerate():
        if thread.name == "lighting-OpenRGB off":
            thread.join(timeout=5)
    # The abandoned step went on after the wake, but turned nothing else off.
    assert not later.is_dark and server.loaded == [DAY_PROFILE]


def test_a_broken_config_leaves_the_lights_at_sleep_but_wake_restores(tmp_path: Path) -> None:
    config_path = tmp_path / "sleepmode.toml"
    config_path.write_text("[lighting]\nenabeld = true\n", encoding="utf-8")
    server = make_server()
    server.profiles.append(FakeProfile(DAY_PROFILE))
    lighting = Lighting(config_path, open_session=server.opener())

    off = lighting.off(may_snapshot=True)
    restore = lighting.restore()

    assert not any(device.is_dark for device in server.devices)
    # Lights dark all day are the worse mistake, so wake falls back to the defaults.
    assert server.loaded == [DAY_PROFILE]
    assert "left alone" in off.notes[0] and "default settings" in restore.notes[0]
