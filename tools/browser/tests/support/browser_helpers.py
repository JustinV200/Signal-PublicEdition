"""Helpers for browser tests: settings for a headless run, and ref lookup in snapshots."""

import re
from dataclasses import replace
from pathlib import Path

from browser_tool.config import (
    BrowserSettings,
    DownloadSettings,
    DuoSettings,
    PolicySettings,
    Settings,
    resolve_tool_path,
)

ALLOWED_HOST = "allowed.localhost"
BLOCKED_HOST = "blocked.localhost"
OTHER_HOST = "other.localhost"
MISSING_HUB_TOKEN = "no-hub-token"


def headless_settings(
    tmp_path: Path,
    allow: tuple[str, ...] = (ALLOWED_HOST,),
    deny: tuple[str, ...] = (),
    allow_all: bool = False,
    duo: DuoSettings | None = None,
) -> Settings:
    """Settings for a fast headless Edge with a throwaway profile under tmp_path.

    The [duo] settings are `duo` (default DuoSettings()) passed through
    hub_token_inside, so no test can read the real hub token or reach a running hub.
    """
    browser = BrowserSettings(
        headless=True,
        profile_dir=str(tmp_path / "profile"),
        screenshot_dir=str(tmp_path / "screenshots"),
        # Never the real tools/browser/.state, even with a cookie mode.
        cookie_file=str(tmp_path / "cookies.bin"),
        navigation_timeout_s=10,
        action_timeout_s=5,
    )
    return Settings(
        browser=browser,
        policy=PolicySettings(allow=allow, deny=deny, allow_all=allow_all),
        duo=hub_token_inside(tmp_path, duo or DuoSettings()),
        # Never the real tools/browser/.downloads.
        downloads=DownloadSettings(folder=str(tmp_path / "downloads")),
    )


def hub_token_inside(tmp_path: Path, duo: DuoSettings) -> DuoSettings:
    """`duo`, with its hub token file forced inside tmp_path.

    A token file anywhere else, the real hub's default included, becomes a
    missing file under tmp_path, so the notifier finds no token and never
    connects. A test that fakes a hub opts in by writing its token under tmp_path.
    """
    token_file = resolve_tool_path(duo.hub_token_file).resolve()
    if token_file.is_relative_to(tmp_path.resolve()):
        return duo
    return replace(duo, hub_token_file=str(tmp_path / MISSING_HUB_TOKEN))


def ref_for(snapshot_text: str, label: str) -> str:
    """Return the ref on the first snapshot line containing `label`.

    Raises:
        AssertionError: If no line contains the label.
    """
    for line in snapshot_text.splitlines():
        if label in line:
            match = re.search(r"\[ref=([a-z0-9]+)\]", line)
            if match:
                return match.group(1)
    raise AssertionError(f"no ref for {label!r} in snapshot:\n{snapshot_text}")
