"""Snapshot pages, subtrees, find and wait_for on headless Edge.

The security test reads fixture pages with secrets through every way the cached
snapshot can be served (pages, subtrees, find) and through wait_for's text
match, with the actions called directly (no ToolRunner scrub to hide a leak),
and checks no secret value ever comes out or can be confirmed by a match.
"""

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace

import pytest
from support.browser_helpers import ALLOWED_HOST, ref_for
from support.page_secrets import BYPASS_SECRETS, LOGIN_SECRETS, MIRROR_SECRETS, PATH_SECRETS

from browser_tool.actions import (
    FILLED_CREDENTIALS_MESSAGE,
    UNTRUSTED_CLOSE,
    ActionError,
    click,
    fill_login,
    find,
    navigate,
    snapshot,
    wait_for,
)
from browser_tool.redaction import REDACTED_VALUE

PAGE_COUNT_RE = re.compile(r"page 1 of (\d+)")
# Short enough for one poll: a probe that would match does so at once.
PROBE_TIMEOUT_S = 0.1


async def _open_cross_tab(ctx, server) -> None:
    """Login secrets in one tab; the current tab shows one of them as plain text."""
    await navigate(ctx, server.url(ALLOWED_HOST, "/login.html"))
    page = await ctx.session.current_page()
    async with page.expect_popup() as popup_info:
        await page.evaluate(f"window.open('{server.url(ALLOWED_HOST, '/cross_tab.html')}')")
    popup = await popup_info.value
    await popup.wait_for_load_state()
    await ctx.session.select_page(ctx.session.pages().index(popup))


async def _change_mirrored_value(ctx, _server) -> None:
    """The page changes its password and the text mirroring it; the title keeps the old one."""
    page = await ctx.session.current_page()
    await page.evaluate(
        "() => { const pw = document.getElementById('pw'); pw.value = 'changed-secret-17';"
        " document.getElementById('mirror').textContent = 'Your password is ' + pw.value; }"
    )


async def _mirror_value_into_path(ctx, _server) -> None:
    """The page holds passwords Edge encodes in a path (a space, an ä) or that hold
    their own %XX (valid or not), and a script puts them all in the URL path.

    pushState makes no request. Each stays live in its own password field.
    """
    page = await ctx.session.current_page()
    await page.evaluate(
        """(secrets) => {
            for (const secret of secrets) {
                const field = document.createElement("input");
                field.type = "password";
                field.value = secret;
                document.body.append(field);
            }
            history.pushState({}, "", "/mirror/" + secrets.join("/"));
        }""",
        list(PATH_SECRETS),
    )


Hook = Callable[..., Awaitable[None]]


@dataclass(frozen=True)
class Case:
    """One fixture page read every way (see the module docstring)."""

    path: str
    secrets: tuple[str, ...]
    page_chars: int
    probes: tuple[str, ...] = ()  # more texts wait_for must not find (secret prefixes)
    url_probes: tuple[str, ...] = ()  # what wait_for(url_contains=...) must not find
    before_url_probes: Hook | None = None  # after the cached reads: it drops the cache
    redacted_count: int | None = None  # REDACTED_VALUE markers across all pages
    open_page: Hook | None = None  # instead of navigating to path
    after_first_snapshot: Hook | None = None
    checks_filled_refusal: bool = False


CASES = [
    Case("/login.html", LOGIN_SECRETS, 200, redacted_count=len(LOGIN_SECRETS),
         checks_filled_refusal=True),
    Case("/bypass.html", BYPASS_SECRETS, 500),
    # A value mirrored into text and the title, then changed: the cached title
    # and pages must not hold the old value, and wait_for can't confirm a prefix.
    Case("/mirror.html", (*MIRROR_SECRETS, *PATH_SECRETS), 200,
         probes=("mirror-secr", "changed-sec"),
         url_probes=("changed-sec", "path secret", "path%20secret", "ä-42", "%C3%A4-42",
                     "Pa%55wo", "PaUwo", "ab%C3", "ab\ufffd"),
         after_first_snapshot=_change_mirrored_value,
         before_url_probes=_mirror_value_into_path),
    # A secret filled in another tab, shown as text in this one.
    Case("/cross_tab.html", LOGIN_SECRETS[:1], 200, probes=("prefilled-pw",),
         open_page=_open_cross_tab),
]  # fmt: skip


@pytest.mark.asyncio
@pytest.mark.parametrize("case", CASES, ids=[case.path.strip("/") for case in CASES])
async def test_no_read_ever_shows_or_confirms_a_secret(make_ctx, fixture_server, case):
    ctx = await make_ctx()
    browser = replace(ctx.settings.browser, max_snapshot_chars=case.page_chars)
    ctx.settings = replace(ctx.settings, browser=browser)
    if case.open_page:
        await case.open_page(ctx, fixture_server)
    else:
        await navigate(ctx, fixture_server.url(ALLOWED_HOST, case.path))
    first = await snapshot(ctx)
    if case.after_first_snapshot:
        await case.after_first_snapshot(ctx, fixture_server)
    page_count = int(PAGE_COUNT_RE.search(first).group(1))
    pages = [first] + [await snapshot(ctx, page=n) for n in range(2, page_count + 1)]
    # Refs from inside the wrapper only: the usage note after it names an example ref.
    bodies = "".join(page.split(UNTRUSTED_CLOSE)[0] for page in pages)
    subtrees = [await snapshot(ctx, ref=ref) for ref in re.findall(r"\[ref=(\w+)\]", bodies)]
    finds = [await find(ctx, secret) for secret in case.secrets]
    waits = [
        await wait_for(ctx, text=probe, timeout_s=PROBE_TIMEOUT_S)
        for probe in case.secrets + case.probes
    ]
    if case.before_url_probes:
        await case.before_url_probes(ctx, fixture_server)
    waits += [
        await wait_for(ctx, url_contains=probe, timeout_s=PROBE_TIMEOUT_S)
        for probe in case.url_probes
    ]

    for text in pages + subtrees + finds + waits:
        assert [secret for secret in case.secrets if secret in text] == []
    assert all(text.startswith("no matches") for text in finds)
    assert all(text.startswith("still waiting") for text in waits)
    if case.redacted_count is not None:
        assert sum(page.count(REDACTED_VALUE) for page in pages) == case.redacted_count
        assert "ordinary search" in "".join(pages)  # non-secret values stay visible
        assert 'textbox "Password"' in "".join(pages)  # names and refs stay, only values go
    if case.checks_filled_refusal:
        # Every read refuses while the vault reports filled fields.
        assert await fill_login(ctx, "demo", False) == "ok"
        reads = (snapshot(ctx), snapshot(ctx, page=2), find(ctx, "Password"))
        for read in (*reads, wait_for(ctx, text="Sign")):
            with pytest.raises(ActionError) as refusal:
                await read
            assert str(refusal.value) == FILLED_CREDENTIALS_MESSAGE


@pytest.mark.asyncio
async def test_the_cached_snapshot_is_dropped_when_the_tab_navigates(make_ctx, fixture_server):
    ctx = await make_ctx()
    await navigate(ctx, fixture_server.url(ALLOWED_HOST, "/login.html"))
    await snapshot(ctx)
    assert "matching line" in await find(ctx, "Password")
    await navigate(ctx, fixture_server.url(ALLOWED_HOST, "/plain.html"))
    # find takes a fresh snapshot of the new page instead of reading the login one.
    assert (await find(ctx, "Password")).startswith("no matches")


@pytest.mark.asyncio
async def test_wait_for_text_a_gone_ref_and_the_url(make_ctx, fixture_server):
    ctx = await make_ctx()
    await navigate(ctx, fixture_server.url(ALLOWED_HOST, "/waits.html"))
    text = await snapshot(ctx)
    spinner = ref_for(text, ": Loading results")
    timed_out = await wait_for(ctx, text="Results ready", timeout_s=0.2)
    assert timed_out.startswith("still waiting after 0.2 s for: text")

    await click(ctx, ref_for(text, 'button "Load results"'))  # shows it 300 ms later
    met = await wait_for(ctx, text="Results ready", gone_ref=spinner, url_contains="/waits")
    assert "for: text, gone_ref, url_contains; now at" in met
    with pytest.raises(ActionError, match="bad wait"):
        await wait_for(ctx)

    # The URL is matched without its query, so a query can't be probed.
    await navigate(ctx, fixture_server.url(ALLOWED_HOST, "/slow?ms=1"))
    probe = await wait_for(ctx, url_contains="ms=", timeout_s=0.2)
    assert probe.startswith("still waiting after 0.2 s for: url_contains")
