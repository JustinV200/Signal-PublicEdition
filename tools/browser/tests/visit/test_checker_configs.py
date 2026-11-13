"""The shipped checker example configs are the checker's security policy: check them by matching.

Policy matches, not strings: a wildcard such as "*.edu" or "*.com" would pass a
string test but undo the block (checker-v2.md section 3.1, hard rules).
"""

import pytest

from browser_tool.config import TOOL_ROOT, load_settings
from browser_tool.policy import HostPolicy

CONFIGS = ("classroom", "moodle")


def _settings(name: str):
    return load_settings(TOOL_ROOT / f"browser-checker-{name}.example.toml")


def _policy(name: str) -> HostPolicy:
    policy = _settings(name).policy
    return HostPolicy.from_strings(policy.allow, policy.deny, is_allow_all=policy.allow_all)


@pytest.mark.parametrize(
    ("config", "host"),
    [
        # Google's SAML hop for the school account must never reach SSO.
        ("classroom", "sso.example.edu"),
        ("classroom", "login.example.edu"),
        ("classroom", "www.google.com"),
        ("classroom", "x.google.com"),
        # No Google host at all, so no Moodle hop can sign in to Google.
        ("moodle", "accounts.google.com"),
        ("moodle", "www.google.com"),
        ("moodle", "classroom.google.com"),
    ],
)
def test_a_checker_config_denies_the_other_sites_hosts(config, host):
    assert not _policy(config).check_host(host).is_allowed


@pytest.mark.parametrize("config", CONFIGS)
def test_a_checker_config_pins_its_launch(config):
    settings = _settings(config)
    assert settings.policy.allow_all is False
    assert settings.policy.deny == ()
    assert settings.browser.use_system_proxy is False
    assert settings.browser.profile_dir == ".profile-checker"
    # Only the Moodle launch has a fill path, and its login host is on its own allowlist.
    # Only the Classroom launch treats a host as a Google sign-in page.
    if config == "moodle":
        assert _policy(config).check_host(settings.visit.login_host).is_allowed
        assert settings.visit.signin_hosts == ()
    else:
        assert settings.visit.login_host == ""
        assert settings.visit.signin_hosts == ("accounts.google.com",)
        # The SSO host is only matched, never allowed.
        assert not _policy(config).check_host(settings.visit.sso_host).is_allowed
