"""The local backend's launch options."""

from dataclasses import replace
from pathlib import Path

from browser_tool.backends import LocalBackend, build_launch_options
from browser_tool.config import BrowserSettings, DownloadSettings, Settings


def test_launch_options_keep_the_sandbox_and_never_record():
    options = build_launch_options(BrowserSettings(), ["--x"])
    assert not any(key.startswith("record_") or "trace" in key for key in options)
    # Playwright adds --no-sandbox unless chromium_sandbox is exactly True.
    assert options["chromium_sandbox"] is True
    assert "ignore_default_args" not in options
    assert options["channel"] == "msedge"
    assert options["headless"] is False
    assert options["service_workers"] == "block"
    assert options["accept_downloads"] is False
    assert "downloads_path" not in options
    assert options["args"] == ["--x", "--no-proxy-server"]
    proxied = build_launch_options(BrowserSettings(use_system_proxy=True), [])
    assert proxied["args"] == []


def test_downloads_land_in_the_profile_only_when_enabled(tmp_path):
    settings = replace(Settings(), browser=BrowserSettings(profile_dir=str(tmp_path)))
    incoming = LocalBackend(settings).downloads_incoming
    assert incoming is not None and incoming.parent == tmp_path
    options = build_launch_options(settings.browser, [], incoming)
    assert options["accept_downloads"] is True
    assert Path(options["downloads_path"]) == incoming
    disabled = replace(settings, downloads=DownloadSettings(enabled=False))
    assert LocalBackend(disabled).downloads_incoming is None
