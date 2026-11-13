"""Shared fixtures: the local web server and an ActionContext factory with fakes."""

from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from dataclasses import replace
from pathlib import Path

import pytest
import pytest_asyncio
from support.browser_helpers import ALLOWED_HOST, headless_settings
from support.fakes import FakeConfirmer, FakeLoginFiller
from support.web_server import FixtureServer

from browser_tool.actions import ActionContext
from browser_tool.config import DownloadSettings, DuoSettings, GateSettings

ContextFactory = Callable[..., Awaitable[ActionContext]]


@pytest.fixture(scope="session")
def web() -> Iterator[FixtureServer]:
    """One fixture HTTP server for the whole test run."""
    server = FixtureServer()
    server.start()
    yield server
    server.stop()


@pytest.fixture
def fixture_server(web: FixtureServer) -> FixtureServer:
    """The shared server with its hit log cleared for this test."""
    web.hits.clear()
    web.posts.clear()
    return web


@pytest_asyncio.fixture
async def make_ctx(tmp_path: Path) -> AsyncIterator[ContextFactory]:
    """Build ActionContexts on headless Edge with a FakeConfirmer and FakeLoginFiller.

    Call as `await make_ctx(allow=(...), deny=(...), allow_all=True, answer=True, filler=...,
    duo=DuoSettings(...), gates=GateSettings(...), downloads=DownloadSettings(...))`.
    The default allowlist is just allowed.localhost. The hub token file is always
    inside tmp_path (see headless_settings), so the real hub is never reached.
    Every browser started this way is closed after the test.
    """
    created: list[ActionContext] = []

    async def factory(
        allow: tuple[str, ...] = (ALLOWED_HOST,),
        deny: tuple[str, ...] = (),
        allow_all: bool = False,
        answer: bool = False,
        filler: FakeLoginFiller | None = None,
        duo: DuoSettings | None = None,
        gates: GateSettings | None = None,
        downloads: DownloadSettings | None = None,
    ) -> ActionContext:
        settings = headless_settings(tmp_path, allow, deny, allow_all, duo)
        gates = gates or settings.gates
        settings = replace(settings, gates=gates, downloads=downloads or settings.downloads)
        ctx = ActionContext.create(settings, FakeConfirmer(answer), filler or FakeLoginFiller())
        created.append(ctx)
        return ctx

    yield factory
    for ctx in created:
        await ctx.session.close()
