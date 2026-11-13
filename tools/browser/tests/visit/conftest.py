"""Visit-mode fixtures: the relaxed login scheme and a visit factory (support/visit_support.py)."""

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from support.fakes import FakeLoginFiller
from support.visit_support import VisitFactory, VisitRun, visit_context

from browser_tool.actions import ActionContext
from browser_tool.config import VisitSettings
from browser_tool.visit import Target, run_visit
from browser_tool.visit import login as visit_login


@pytest.fixture(autouse=True)
def stand_in_login_scheme(monkeypatch: pytest.MonkeyPatch) -> None:
    """Allow the stand-ins' plain-http services on a port."""
    monkeypatch.setattr(visit_login, "SERVICE_SCHEME", "http")
    monkeypatch.setattr(visit_login, "ALLOW_SERVICE_PORT", True)


@pytest_asyncio.fixture
async def visit(tmp_path: Path) -> AsyncIterator[VisitFactory]:
    """Run one visit on headless Edge with a throwaway profile, never relaunching.

    Call as `await visit(targets, allow=..., settings=VisitSettings(...), filler=...)`;
    it returns a VisitRun. Every browser started this way is closed after the test.
    """
    created: list[ActionContext] = []

    async def factory(
        targets: tuple[Target, ...],
        allow: tuple[str, ...],
        settings: VisitSettings,
        filler: FakeLoginFiller | None = None,
    ) -> VisitRun:
        ctx, backend = visit_context(tmp_path, allow, settings, filler)
        created.append(ctx)
        return VisitRun(await run_visit(ctx, targets, settings), ctx, backend)

    yield factory
    for ctx in created:
        await ctx.session.close()
