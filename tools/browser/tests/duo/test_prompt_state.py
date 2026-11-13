"""The once-per-prompt rule and the site a prompt is announced for (pure, fake clock)."""

from dataclasses import dataclass, field

import pytest

from browser_tool.duo import TabDuoState, heads_up_note

WINDOW_S = 10.0
SITE = "https://portal.example.edu/login"
DUO_A = "https://api-1a2b3c4d.duosecurity.com/oauth/v1/authorize"
DUO_B = "https://api-1a2b3c4d.duosecurity.com/frame/frameless/v4/auth"


def show(state: TabDuoState, url: str, now: float, iframe: str | None = None) -> bool:
    """Feed one top-level page (plus an optional iframe) to the state."""
    frames = [url, iframe] if iframe else [url]
    return state.update(url, frames, now)


def test_a_redirect_chain_through_duo_is_one_prompt_for_the_site_before_it():
    state = TabDuoState(WINDOW_S)
    starts = [
        show(state, SITE, 0.0),
        show(state, DUO_A, 1.0),
        show(state, DUO_B, 1.5),
        show(state, DUO_B, 30.0),
    ]
    assert starts == [False, True, False, False]
    assert state.site == "portal.example.edu"
    assert heads_up_note(state.site).text == (
        "Duo push for portal.example.edu, approve on your phone."
    )


def test_leaving_and_coming_back_later_is_a_new_prompt_but_a_quick_bounce_is_not():
    state = TabDuoState(WINDOW_S)
    show(state, SITE, 0.0)
    assert show(state, DUO_A, 1.0)
    # Out to the site's login and straight back: the same prompt.
    assert not show(state, SITE, 2.0)
    assert not show(state, DUO_B, 3.0)
    # Done, then a new login long after: a new prompt.
    assert not show(state, SITE, 4.0)
    assert show(state, DUO_A, 4.0 + WINDOW_S + 1)


def test_an_embedded_duo_iframe_is_a_prompt_for_the_page_around_it():
    state = TabDuoState(WINDOW_S)
    assert show(state, SITE, 0.0, iframe=DUO_B)
    assert state.site == "portal.example.edu"
    assert not show(state, SITE, 1.0)  # iframe gone: left Duo
    assert state.is_in_duo is False


def test_a_tab_that_opened_on_duo_falls_back_to_a_login():
    state = TabDuoState(WINDOW_S)
    assert show(state, DUO_A, 0.0)
    assert state.site is None
    assert heads_up_note(state.site).text == "Duo push for a login, approve on your phone."
    assert heads_up_note(state.site).priority == "urgent"
    assert heads_up_note(state.site).source == "browser"


@dataclass
class Hop:
    """A fake navigation request hop (Playwright's Request has the same three fields)."""

    url: str
    redirected_from: "Hop | None" = None
    headers: dict[str, str] = field(default_factory=dict)


def _chain(referer: str | None, *urls: str) -> Hop:
    """The last hop of a redirect chain through `urls`; only its first request has `referer`.

    Later hops get none, as when a redirect's Referrer-Policy strips it.
    """
    hop = None
    for url in urls:
        headers = {"referer": referer} if hop is None and referer else {}
        hop = Hop(url, hop, headers)
    assert hop is not None
    return hop


@pytest.mark.parametrize(
    ("referer", "hops", "site_after"),
    [
        # Regression: site -> evil.example -> 302 -> the attacker's Duo kept the site,
        # because the evil hop never commits.
        (SITE, ("https://evil.example/go", DUO_A), None),
        (SITE, (SITE, DUO_A, DUO_B), "portal.example.edu"),  # the site's own redirect to Duo
        # Regression: an opener, a popup or a third-party frame sending the tab to Duo
        # kept the site, because the chain is just Duo.
        ("https://evil.example/", (DUO_A,), None),
        (None, (DUO_A,), None),  # no Referer: Claude's navigate, or a no-referrer page
    ],
)
def test_a_navigation_to_duo_keeps_the_site_only_if_the_site_started_it(referer, hops, site_after):
    state = TabDuoState(WINDOW_S)
    show(state, SITE, 0.0)
    state.vet_duo_navigation(_chain(referer, *hops))
    assert state.site == site_after


def test_a_referer_on_duo_keeps_the_site_only_once_the_tab_is_on_duo():
    hop_within_duo = _chain(DUO_A, DUO_B)
    state = TabDuoState(WINDOW_S)
    # A Duo iframe on the site's page moving the whole tab: not a hop inside a prompt.
    show(state, SITE, 0.0, iframe=DUO_A)
    state.vet_duo_navigation(hop_within_duo)
    assert state.site is None

    show(state, SITE, 1.0)
    state.vet_duo_navigation(_chain(SITE, DUO_A))
    show(state, DUO_A, 2.0)
    state.vet_duo_navigation(hop_within_duo)
    assert state.site == "portal.example.edu"
