"""Duo host matching: duosecurity.com and its subdomains only, by parsed hostname."""

import pytest

from browser_tool.duo import is_duo_url


@pytest.mark.parametrize(
    "url",
    [
        "https://duosecurity.com/",
        "https://api-1a2b3c4d.duosecurity.com/frame/frameless/v4/auth?sid=x",
        "https://API-1A2B3C4D.DuoSecurity.COM./frame",
        "https://api-1a2b3c4d.duosecurity.com:443/",
        "blob:https://api-1a2b3c4d.duosecurity.com/5f0c-uuid",
        # Default-deny: a network URL whose host can't be parsed counts as Duo.
        "https://[not-an-ip/frame",
    ],
)
def test_duo_hosts_match(url):
    assert is_duo_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://evil-duosecurity.com/",
        "https://duosecurity.com.evil.com/",
        "https://example.com/duosecurity.com/frame",
        "https://example.com/login?next=https://api-1.duosecurity.com/",
        "https://user@example.com/",
        "about:blank",
        "data:text/html,duosecurity.com",
        "",
    ],
)
def test_lookalikes_and_hostless_urls_do_not_match(url):
    assert not is_duo_url(url)
