"""Shared fixtures: fake Hello signer, fake confirmer, a ready-made vault, a headless browser.

The browser is Playwright's Chromium driven through the installed Microsoft
Edge (channel "msedge"), so no browser download is needed. Pages are served by
`page.route`, which lets tests use real https origins with no server.
"""

import asyncio
import hashlib
import hmac
import re
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path

import pytest
import pytest_asyncio
from playwright.async_api import Page, Route, async_playwright

from vault.audit import AuditLog
from vault.confirm import ConfirmRequest
from vault.fill import FillDeps, FilledRegistry
from vault.store import (
    DEFAULT_POLICY,
    CredentialMeta,
    create_vault_data,
    save_vault,
    seal_credential,
    unlocked_dek,
    username_hint,
)
from vault.unlock import UnlockError
from vault.unlock.hello import HelloUnlocker

USERNAME = "owner@example.test"
PASSWORD = "S3cret-Pa55word!"
CREDENTIAL_ID = "example"
CREDENTIAL_NAME = "Example"
REGISTERED_ORIGINS = ("https://login.example.test", "https://auth.example.test")
FAKE_SIGNING_KEY = b"fake-hello-key-for-tests"
# Edge's SmartScreen/typosquatting checks on the fake .test hosts make every
# browser.close() take about 6 s; tests don't need them.
EDGE_TEST_ARGS = [
    "--disable-features=msSmartScreenProtection,msEdgeTyposquattingChecker",
    "--disable-background-networking",
]
# Every http(s) request, including iframes and form posts.
HTTP_URL_PATTERN = re.compile(r"^https?://")

LOGIN_FORM = """<form action="/done" method="post">
  <input id="user" name="user" autocomplete="username">
  <input id="pass" name="pass" type="password">
  <button>Sign in</button>
</form>"""


class FakeSigner:
    """HelloSigner stand-in: a deterministic HMAC "signature", with optional failure."""

    def __init__(self) -> None:
        self.sign_calls = 0
        self.fail_with: UnlockError | None = None

    async def create_key(self, key_name: str) -> None:
        pass

    async def sign(self, key_name: str, challenge: bytes) -> bytearray:
        self.sign_calls += 1
        if self.fail_with is not None:
            raise self.fail_with
        return bytearray(hmac.new(FAKE_SIGNING_KEY, challenge, hashlib.sha256).digest())


@dataclass
class FakeConfirmer:
    """Confirmer stand-in: records requests, optionally runs a hook, then answers."""

    answer: bool = True
    before_answer: Callable[[], Awaitable[None]] | None = None
    requests: list[ConfirmRequest] = field(default_factory=list)

    async def confirm(self, request: ConfirmRequest) -> bool:
        self.requests.append(request)
        if self.before_answer is not None:
            await self.before_answer()
        return self.answer


@dataclass
class FillEnv:
    """A vault with one credential plus fakes for everything the fill sequence talks to."""

    deps: FillDeps
    confirmer: FakeConfirmer
    signer: FakeSigner
    store_path: Path
    audit_path: Path
    registry: FilledRegistry
    credential_id: str = CREDENTIAL_ID
    username: str = USERNAME
    password: str = PASSWORD
    login_form: str = LOGIN_FORM


async def build_store(store_path: Path, signer: FakeSigner) -> None:
    """Create a Hello-style vault (fake signer) holding the Example credential."""
    unlocker = HelloUnlocker(signer)
    data = await create_vault_data(unlocker)
    meta = CredentialMeta(
        CREDENTIAL_ID, CREDENTIAL_NAME, REGISTERED_ORIGINS, username_hint(USERNAME), DEFAULT_POLICY
    )
    async with unlocked_dek(data.header, unlocker) as dek:
        record = seal_credential(dek, data.header, meta, USERNAME, PASSWORD)
    save_vault(store_path, data.with_record(record))


@pytest.fixture
def make_store() -> Callable[[Path], FakeSigner]:
    """Return a sync factory: build the Example vault at a path, return its fake signer.

    For tests of code that calls asyncio.run itself (the CLI), which can't run
    inside an async test.
    """

    def build(store_path: Path) -> FakeSigner:
        signer = FakeSigner()
        asyncio.run(build_store(store_path, signer))
        return signer

    return build


@pytest_asyncio.fixture
async def fill_env(tmp_path: Path) -> FillEnv:
    """A fresh vault and fakes; the signer's call count starts at zero."""
    signer = FakeSigner()
    store_path = tmp_path / "store.json"
    await build_store(store_path, signer)
    signer.sign_calls = 0
    confirmer = FakeConfirmer()
    registry = FilledRegistry()
    audit_path = tmp_path / "audit.jsonl"
    deps = FillDeps(
        store_path=store_path,
        audit=AuditLog(audit_path),
        confirmer=confirmer,
        unlocker_for=lambda _provider: HelloUnlocker(signer),
        registry=registry,
    )
    return FillEnv(deps, confirmer, signer, store_path, audit_path, registry)


@pytest_asyncio.fixture
async def page() -> AsyncIterator[Page]:
    """A headless Edge page; skips the test if Edge can't be launched."""
    async with async_playwright() as playwright:
        try:
            browser = await playwright.chromium.launch(
                channel="msedge", headless=True, args=EDGE_TEST_ARGS
            )
        except Exception:
            pytest.skip("Microsoft Edge is not available to Playwright")
        context = await browser.new_context()
        yield await context.new_page()
        await browser.close()


SiteServer = Callable[[dict[str, str]], Awaitable[None]]


@pytest.fixture
def serve(page: Page) -> SiteServer:
    """Return a function that serves {url: html} on `page` for https and http URLs; others 404."""

    async def install(pages_by_url: dict[str, str]) -> None:
        async def handle(route: Route) -> None:
            url = route.request.url.split("?")[0]
            if route.request.method == "POST":
                await route.fulfill(body="<p>done</p>", content_type="text/html")
            elif url in pages_by_url:
                await route.fulfill(body=pages_by_url[url], content_type="text/html")
            else:
                await route.fulfill(status=404, body="not found")

        await page.route(HTTP_URL_PATTERN, handle)

    return install
