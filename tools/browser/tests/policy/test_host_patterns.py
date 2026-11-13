"""Host pattern parsing and matching."""

import pytest

from browser_tool.policy import parse_host_pattern


def test_exact_pattern_matches_only_that_host():
    pattern = parse_host_pattern("Example.COM")
    assert pattern.matches("example.com")
    assert not pattern.matches("www.example.com")


def test_wildcard_matches_subdomains_but_not_apex_or_lookalikes():
    pattern = parse_host_pattern("*.example.com")
    assert pattern.matches("a.b.example.com")
    assert not pattern.matches("example.com")
    assert not pattern.matches("evilexample.com")


def test_unicode_hosts_are_idna_normalized():
    assert parse_host_pattern("bücher.de").matches("xn--bcher-kva.de")


@pytest.mark.parametrize("text", ["https://a.com", "a.com:443", "a.*.com", "user@a.com"])
def test_malformed_patterns_are_rejected(text):
    with pytest.raises(ValueError):
        parse_host_pattern(text)
