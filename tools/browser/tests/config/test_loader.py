"""Config loading: the example file matches the defaults, and bad values are rejected."""

import pytest

from browser_tool.config import (
    TOOL_ROOT,
    ConfigError,
    Settings,
    load_settings,
    paths,
    settings_from_dict,
)


def test_example_config_documents_exactly_the_defaults():
    assert load_settings(TOOL_ROOT / "browser.example.toml") == Settings()


def test_overrides_are_applied_and_lists_become_tuples():
    settings = settings_from_dict(
        {"browser": {"headless": True, "action_timeout_s": 3}, "policy": {"allow": ["a.com"]}}
    )
    assert settings.browser.headless is True
    assert settings.browser.action_timeout_s == 3.0
    assert settings.policy.allow == ("a.com",)


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ({"browser": {"colour": "red"}}, "unknown key"),
        ({"browser": {"action_timeout_s": True}}, "positive float"),
        ({"gates": {"patterns": ["(unclosed"]}}, "bad pattern"),
        # A misspelt category would silently stop asking.
        ({"gates": {"always_confirm": ["purchases"]}}, "unknown categories purchases"),
        # The hub's token goes with every note, so it must stay on this machine.
        ({"duo": {"hub_host": "192.168.1.5"}}, "loopback"),
        # Site names are spoken and shown to the model: plain, short, exact hosts only.
        ({"duo": {"site_names": {"cas.example.edu": "<b>approve</b>"}}}, "site_names"),
        ({"duo": {"site_names": {"cas.example.edu": "x" * 41}}}, "site_names"),
        ({"duo": {"site_names": {"*.example.edu": "Example"}}}, "exact hostname"),
        ({"duo": {"site_names": {"cas.example.edu": 3}}}, "table of strings"),
        # Files are read from these folders: never over SMB.
        ({"uploads": {"roots": ["//fileserver/share"]}}, "network share"),
        ({"downloads": {"folder": "//fileserver/share"}}, "network share"),
        # Outside .state, upload_file and read_download could read live cookies.
        ({"browser": {"cookie_file": "../../life/cookies.bin"}}, "inside a .state folder"),
        # ".." after .state climbs back out, so the lexical parents must be folded first.
        ({"browser": {"cookie_file": "a/.state/../../x/c.bin"}}, "inside a .state folder"),
    ],
)
def test_invalid_values_raise_config_error(data, message):
    with pytest.raises(ConfigError, match=message):
        settings_from_dict(data)


def test_retired_categories_still_load_with_a_warning(caplog):
    # Older local browser.toml files list them; they must keep loading.
    settings = settings_from_dict(
        {"gates": {"always_confirm": ["purchase", "password_submit", "grant_access"]}}
    )
    assert settings.gates.always_confirm == ("purchase",)
    assert caplog.text.count("retired") == 2


def test_an_upload_root_on_a_mapped_network_drive_is_refused(monkeypatch):
    monkeypatch.setattr(paths, "_drive_type", lambda root: paths.DRIVE_REMOTE)
    with pytest.raises(ConfigError, match="network share or drive"):
        settings_from_dict({"uploads": {"roots": ["Z:/team"]}})
