"""The Chromium --host-resolver-rules flag built from a policy (blocks redirect hops)."""

from browser_tool.policy import HostPolicy, build_host_resolver_rules, build_resolver_args


def test_allow_all_maps_only_denied_hosts():
    assert build_resolver_args(HostPolicy(is_allow_all=True)) == []
    policy = HostPolicy.from_strings([], ["bad.com", "*.ads.net"], is_allow_all=True)
    assert build_host_resolver_rules(policy) == "MAP bad.com ~NOTFOUND, MAP *.ads.net ~NOTFOUND"


def test_empty_allowlist_blocks_every_host():
    assert build_host_resolver_rules(HostPolicy()) == "MAP * ~NOTFOUND"


def test_allowlist_blocks_everything_else():
    policy = HostPolicy.from_strings(["good.com", "*.good.com"], ["bad.com"])
    assert build_resolver_args(policy) == [
        "--host-resolver-rules=MAP bad.com ~NOTFOUND, MAP * ~NOTFOUND, "
        "EXCLUDE good.com, EXCLUDE *.good.com"
    ]
