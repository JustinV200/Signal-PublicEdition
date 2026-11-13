"""Tests for the OpenRGB backend's snapshot and restore rules, on a fake SDK server."""

from pathlib import Path

from support.openrgb_fakes import FakeProfile, make_server

from sleepmode.config import DAY_PROFILE, SNAPSHOT_PROFILE
from sleepmode.lighting import Lighting


def test_one_snapshot_per_sleep_and_wake_prefers_the_day_profile(tmp_path: Path) -> None:
    server = make_server()
    lighting = Lighting(tmp_path / "sleepmode.toml", open_session=server.opener())

    first = lighting.off(may_snapshot=True)
    assert server.saved == [SNAPSHOT_PROFILE]
    assert all(device.is_dark for device in server.devices)
    assert any(f"no `{DAY_PROFILE}` profile" in note for note in first.notes)

    # A sleep that replaces this one mustn't save over the snapshot, even when a light
    # came back on in between; nor may a new sleep that finds the lights already off.
    server.devices[0].light_up()
    lighting.off(may_snapshot=False)
    lighting.off(may_snapshot=True)
    assert server.saved == [SNAPSHOT_PROFILE]

    lighting.restore()
    server.profiles.append(FakeProfile(DAY_PROFILE))
    lighting.restore()
    assert server.loaded == [SNAPSHOT_PROFILE, DAY_PROFILE]

    # With a day profile, wake never loads the snapshot, so sleep doesn't save one.
    for device in server.devices:
        device.light_up()
    assert lighting.off(may_snapshot=True).notes == ()
    assert server.saved == [SNAPSHOT_PROFILE]
    # Every session is closed, and the snapshot's CLI save closed one more connection.
    assert server.disconnects == 7
