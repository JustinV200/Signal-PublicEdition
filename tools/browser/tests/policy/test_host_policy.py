"""Allow/deny decisions for URLs."""

import pytest

from browser_tool.policy import (
    REASON_ALLOW_ALL,
    REASON_ALLOWLISTED,
    REASON_DENYLISTED,
    REASON_NOT_ALLOWLISTED,
    REASON_OPAQUE_ORIGIN,
    REASON_UNSUPPORTED_SCHEME,
    HostPolicy,
)


def test_empty_allowlist_blocks_everything():
    assert HostPolicy().check_url("https://good.com/x").reason == REASON_NOT_ALLOWLISTED


def test_explicit_allow_all_allows_everything_not_denied():
    policy = HostPolicy.from_strings([], ["bad.com"], is_allow_all=True)
    assert policy.check_url("https://good.com/x").reason == REASON_ALLOW_ALL
    assert policy.check_url("https://bad.com/").reason == REASON_DENYLISTED


def test_allowlist_limits_hosts_and_deny_wins():
    policy = HostPolicy.from_strings(["*.shop.com", "shop.com"], ["admin.shop.com"])
    assert policy.check_url("https://shop.com").reason == REASON_ALLOWLISTED
    assert policy.check_url("https://cdn.shop.com/a.js").is_allowed
    assert policy.check_url("https://admin.shop.com").reason == REASON_DENYLISTED
    assert policy.check_url("https://other.com").reason == REASON_NOT_ALLOWLISTED


def test_userinfo_decoy_is_checked_against_the_real_host():
    policy = HostPolicy.from_strings(["good.com"], [])
    decision = policy.check_url("https://good.com@evil.com/login")
    assert not decision.is_allowed
    assert decision.host == "evil.com"


@pytest.mark.parametrize(
    "url", ["about:blank", "about:srcdoc", "data:text/html,hi", "blob:https://good.com/uuid"]
)
def test_opaque_origins_are_mismatches_even_in_allow_all_mode(url):
    policy = HostPolicy(is_allow_all=True)
    assert policy.check_url(url).reason == REASON_OPAQUE_ORIGIN


@pytest.mark.parametrize(
    "url", ["file:///C:/x", "edge://settings", "chrome-error://chromewebdata/"]
)
def test_non_web_schemes_are_refused(url):
    assert HostPolicy().check_url(url).reason == REASON_UNSUPPORTED_SCHEME
