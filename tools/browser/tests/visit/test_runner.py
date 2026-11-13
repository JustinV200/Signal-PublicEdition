"""Tests for browser_tool.visit.run_visit on headless Edge and *.localhost stand-ins.

The fill rules, the per-launch hop rules, the cookie clear, no relaunch after a
close, and the scrub of everything that reaches the out file or the log.
"""

import logging

import pytest
from support.fakes import SECRET_PASSWORD
from support.visit_support import (
    CAS,
    CLASSROOM,
    CLASSROOM_ALLOW,
    CLASSROOM_VISIT,
    CREDENTIAL,
    GOOGLE_SIGNIN,
    MOODLE,
    MOODLE_ALLOW,
    MOODLE_VISIT,
    PARENT,
    SubmittingFiller,
    target,
    visit_context,
)

from browser_tool.config import VisitSettings
from browser_tool.visit import run_visit, write_out

NEEDS_LOGIN = f"/needs-login?login={CAS}"
NO_LOGIN_KEYS = VisitSettings(signin_hosts=(GOOGLE_SIGNIN,), settle_s=1)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("settings", "pages", "filler", "statuses", "calls"),
    [
        # A Moodle target sent to the login host with a Moodle service: one fill.
        (MOODLE_VISIT, [(MOODLE, NEEDS_LOGIN)], SubmittingFiller(), ["ok"], [(CREDENTIAL, True)]),
        # A launch without login keys (the Classroom one) never fills, even there.
        (NO_LOGIN_KEYS, [(MOODLE, NEEDS_LOGIN)], SubmittingFiller(), ["ok"], []),
        # The target's host isn't in [visit] login_from_hosts.
        (
            MOODLE_VISIT,
            [("other.localhost", NEEDS_LOGIN)],
            SubmittingFiller(),
            ["login_needed"],
            [],
        ),
        # The login URL has no service (as after a script navigation): no fill.
        (
            MOODLE_VISIT,
            [(MOODLE, NEEDS_LOGIN + "&noservice=1")],
            SubmittingFiller(),
            ["login_needed"],
            [],
        ),
        # A denied fill: login_needed for it and every later target; earlier ones are read.
        (
            MOODLE_VISIT,
            [(MOODLE, "/plain.html"), (MOODLE, NEEDS_LOGIN), (MOODLE, "/plain.html")],
            SubmittingFiller(reason="denied"),
            ["ok", "login_needed", "login_needed"],
            [(CREDENTIAL, True)],
        ),
    ],
    ids=["fills-once", "no-login-keys", "host-not-listed", "no-service", "denied"],
)
async def test_fill_rules(visit, fixture_server, settings, pages, filler, statuses, calls):
    targets = tuple(
        target(f"p{i}", fixture_server.url(host, path)) for i, (host, path) in enumerate(pages)
    )
    run = await visit(targets, MOODLE_ALLOW, settings, filler)
    assert run.result.status == "ok"
    assert [page.status for page in run.result.pages] == statuses
    assert filler.calls == calls


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("allow", "settings", "first_host", "hop_to", "statuses"),
    [
        # Moodle launch: a Moodle page that 302s to Google is stopped on the hop.
        (MOODLE_ALLOW, MOODLE_VISIT, MOODLE, GOOGLE_SIGNIN, ["error", "ok"]),
        # Classroom launch: Google's hop to CAS is stopped, and that means sign in to
        # Google, for this target and the rest.
        (
            CLASSROOM_ALLOW,
            CLASSROOM_VISIT,
            GOOGLE_SIGNIN,
            CAS,
            ["google_signin_needed", "google_signin_needed"],
        ),
    ],
    ids=["moodle-to-google", "google-to-cas"],
)
async def test_the_other_sites_host_is_refused_on_the_hop(
    visit, fixture_server, allow, settings, first_host, hop_to, statuses
):
    targets = (
        target("hop", fixture_server.url(first_host, f"/redirect?to={hop_to}")),
        target("next", fixture_server.url(first_host, "/plain.html")),
    )
    run = await visit(targets, allow, settings)
    assert [page.status for page in run.result.pages] == statuses
    assert hop_to not in fixture_server.hosts_hit()


@pytest.mark.asyncio
async def test_a_sign_in_launch_clears_every_school_cookie_first(
    fixture_server, tmp_path, monkeypatch
):
    ctx, _backend = visit_context(tmp_path, CLASSROOM_ALLOW, CLASSROOM_VISIT)
    page = await ctx.session.current_page()
    await page.context.add_cookies(
        [
            {"name": "host-only", "value": "1", "url": fixture_server.url(CAS, "/")},
            {"name": "cas", "value": "1", "domain": f".{CAS}", "path": "/"},
            {"name": "parent", "value": "1", "domain": f".{PARENT}", "path": "/"},
            {"name": "keep", "value": "1", "domain": f".{CLASSROOM}", "path": "/"},
        ]
    )
    left: set[str] = set()
    real_close = ctx.session.close

    async def read_cookies_then_close():
        # run_visit closes the session at the end: read what's left first.
        left.update(cookie["domain"] for cookie in await page.context.cookies())
        await real_close()

    monkeypatch.setattr(ctx.session, "close", read_cookies_then_close)
    try:
        targets = (target("c", fixture_server.url(CLASSROOM, "/plain.html"), "classroom"),)
        await run_visit(ctx, targets, CLASSROOM_VISIT)
    finally:
        await real_close()
    assert left == {f".{CLASSROOM}"}


@pytest.mark.asyncio
async def test_a_close_after_the_fill_ends_the_launch_without_a_relaunch(visit, fixture_server):
    targets = (
        target("login", fixture_server.url(MOODLE, NEEDS_LOGIN)),
        target("after", fixture_server.url(MOODLE, "/plain.html")),
    )
    run = await visit(targets, MOODLE_ALLOW, MOODLE_VISIT, SubmittingFiller(closes=True))
    assert [page.status for page in run.result.pages] == ["error", "error"]
    assert run.backend.launches == 1


@pytest.mark.asyncio
async def test_a_filled_value_never_reaches_the_out_file_or_the_log(
    visit, fixture_server, tmp_path, caplog
):
    caplog.set_level(logging.DEBUG)
    # The page echoes the secret in its text, and the vault's error carries it.
    filler = SubmittingFiller(error=RuntimeError(f"could not fill {SECRET_PASSWORD}"))
    targets = (
        target("echo", fixture_server.url(MOODLE, "/visit_secret.html")),
        target("login", fixture_server.url(MOODLE, NEEDS_LOGIN)),
    )
    run = await visit(targets, MOODLE_ALLOW, MOODLE_VISIT, filler)
    out = tmp_path / "out.json"
    write_out(out, run.result)

    assert [page.status for page in run.result.pages] == ["ok", "login_needed"]
    assert "Your saved password is" in run.result.pages[0].text
    assert SECRET_PASSWORD not in out.read_text(encoding="utf-8")
    assert SECRET_PASSWORD not in caplog.text
