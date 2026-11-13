"""Origin parsing and matching: the rules that bind a credential to its sites."""

import pytest

from vault.origin import (
    OriginError,
    describe_origin,
    origin_of_url,
    parse_registered_origin,
    url_matches_origins,
)


@pytest.mark.parametrize(
    ("url", "origin"),
    [
        ("https://GitHub.com/login?x=1", "https://github.com"),
        ("https://github.com:443/", "https://github.com"),
        ("https://example.test:8443/a", "https://example.test:8443"),
        ("https://xn--fa-hia.de/", "https://xn--fa-hia.de"),
    ],
)
def test_origin_of_url_canonicalises(url, origin):
    assert origin_of_url(url) == origin


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/",
        "https://github.com@evil.test/",
        "https://user:pw@github.com/",
        "https://exa_mple.test/",
        "https://*.github.com/",
        "https://github.com:99999/",
    ],
)
def test_origin_of_url_rejects_unsafe_urls(url):
    with pytest.raises(OriginError):
        origin_of_url(url)


def test_registered_origins_must_not_carry_a_path():
    with pytest.raises(OriginError):
        parse_registered_origin("https://github.com/login")


def test_non_ascii_hosts_must_be_entered_as_punycode():
    # Python's idna codec is IDNA2003 and would turn this into fass.de, another site.
    with pytest.raises(OriginError, match="punycode"):
        parse_registered_origin("https://faß.de")


@pytest.mark.parametrize(
    "url",
    [
        "about:blank",
        "about:srcdoc",
        "data:text/html,<input type=password>",
        "blob:https://github.com/0b5c8e5e-0000-4000-8000-000000000000",
        "https://github.com.evil.test/",
        "https://sub.github.com/",
        "https://github.com:8443/",
    ],
)
def test_only_exact_https_origins_match(url):
    assert not url_matches_origins(url, ["https://github.com"])


def test_describe_origin_drops_paths_queries_and_content():
    assert describe_origin("https://a.test/cb?token=secret") == "https://a.test"
    assert describe_origin("data:text/html,secret") == "data:"
    assert describe_origin("blob:https://a.test/uuid") == "blob:"
