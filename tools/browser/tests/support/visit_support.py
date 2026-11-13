"""Visit-mode test support: *.localhost stand-ins for Moodle, CAS and Google, fakes, and
an ActionContext built the way browser-tool-visit builds one.

The stand-ins are plain-http hosts on the fixture server; tests/visit/conftest.py
relaxes login.SERVICE_SCHEME to http; CLASSROOM_VISIT points the SSO patterns at them.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from browser_tool.actions import ActionContext
from browser_tool.backends import LocalBackend
from browser_tool.config import VisitSettings
from browser_tool.cookie_store import CookieMode
from browser_tool.credentials import FillResult
from browser_tool.visit import Target, VisitResult
from support.browser_helpers import headless_settings
from support.fakes import FakeConfirmer, FakeLoginFiller

PARENT = "example.localhost"
CAS = f"cas.{PARENT}"
MOODLE = f"moodle.{PARENT}"
GOOGLE_SIGNIN = "accounts.google.localhost"
CLASSROOM = "classroom.google.localhost"
CREDENTIAL = "school"
SESSION_COOKIE = "visit-session"

MOODLE_ALLOW = (MOODLE, CAS, "other.localhost")
CLASSROOM_ALLOW = (CLASSROOM, GOOGLE_SIGNIN)
MOODLE_VISIT = VisitSettings(
    login_host=CAS,
    login_from_hosts=(MOODLE,),
    login_credential=CREDENTIAL,
    login_wait_s=5,
    settle_s=1,
)
CLASSROOM_VISIT = VisitSettings(
    signin_hosts=(GOOGLE_SIGNIN,), sso_host=CAS, school_domain=PARENT, settle_s=1
)

VisitFactory = Callable[..., Awaitable["VisitRun"]]


class CountingBackend(LocalBackend):
    """The local backend, counting launches, so a test can prove nothing relaunched."""

    launches = 0

    async def open_context(self, playwright: Any, policy: Any) -> Any:
        self.launches += 1
        return await super().open_context(playwright, policy)


class SubmittingFiller(FakeLoginFiller):
    """A fake vault that "submits": it records each call, then sets the stand-in
    session cookie and goes to the login URL's service, as CAS would.

    reason: a FillResult reason other than "filled" makes the fill fail with it.
    closes: close the whole browser instead of submitting (and report ok).
    """

    def __init__(self, reason: str = "filled", closes: bool = False, **kwargs: Any):
        super().__init__(**kwargs)
        self.reason = reason
        self.closes = closes
        self.calls: list[tuple[str, bool]] = []

    async def fill_login(self, page: Any, credential_id: str, *, submit: bool = False) -> Any:
        self.calls.append((credential_id, submit))
        if self.error is not None:
            raise self.error
        if self.reason != "filled":
            return FillResult(ok=False, reason=self.reason)
        if self.closes:
            await page.context.close()
            return FillResult(ok=True, reason="filled")
        service = parse_qs(urlsplit(page.url).query)["service"][0]
        await page.context.add_cookies([{"name": SESSION_COOKIE, "value": "1", "url": service}])
        await page.goto(service)
        return FillResult(ok=True, reason="filled")


@dataclass
class VisitRun:
    """One finished visit: its result, its context and the backend that counted launches."""

    result: VisitResult
    ctx: ActionContext
    backend: CountingBackend


def visit_context(
    tmp_path: Path,
    allow: tuple[str, ...],
    settings: VisitSettings,
    filler: FakeLoginFiller | None = None,
) -> tuple[ActionContext, CountingBackend]:
    """An ActionContext like the CLI builds (no relaunch), on headless Edge and fakes."""
    base = replace(headless_settings(tmp_path, allow), visit=settings)
    backend = CountingBackend(base)
    ctx = ActionContext.create(
        base,
        FakeConfirmer(),
        filler or FakeLoginFiller(),
        backend,
        allow_relaunch=False,
        holds_dialogs=False,
        # Borrows tmp_path/cookies.bin (headless_settings), never the real one.
        cookie_mode=CookieMode.BORROW,
    )
    return ctx, backend


def target(key: str, url: str, site: str = "moodle") -> Target:
    """A plan target (fixture URLs are http, so they skip parse_plan's https check)."""
    return Target(key=key, url=url, site=site)
