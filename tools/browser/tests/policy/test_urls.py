"""Model-facing and logged URLs never expose queries, fragments or userinfo."""

from browser_tool.policy import display_url, origin_of


def test_tokens_in_urls_are_not_exposed():
    assert origin_of("https://user:pw@Example.com:8443/a?token=x#f") == "https://example.com:8443"
    assert display_url("https://a.com/cb?code=secret#x") == "https://a.com/cb"


def test_ipv6_origins_keep_their_brackets_so_port_and_address_stay_apart():
    # Regression: both used to read http://::1:8080, so the approved-origin check matched them.
    assert origin_of("http://[::1]:8080/a") == "http://[::1]:8080"
    assert origin_of("http://[::1:8080]/a") == "http://[::1:8080]"
