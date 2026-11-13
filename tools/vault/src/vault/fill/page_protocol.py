"""Structural types for the slice of Playwright's async API the vault uses.

The vault never imports Playwright at runtime (it's a dev dependency, for tests
only); `tools/browser` passes real `playwright.async_api.Page` objects, which
satisfy these protocols.
"""

from collections.abc import Callable, Sequence
from typing import Any, Protocol


class JSHandleLike(Protocol):
    """A JS value handle; `as_element()` is None unless it points at a DOM element."""

    def as_element(self) -> "ElementLike | None": ...


class ElementLike(Protocol):
    """An ElementHandle: bound to one DOM node, never re-resolved after navigation."""

    async def is_visible(self) -> bool: ...

    async def get_attribute(self, name: str) -> str | None: ...

    async def evaluate(self, expression: str) -> Any: ...

    async def evaluate_handle(self, expression: str) -> JSHandleLike: ...

    async def owner_frame(self) -> "FrameLike | None": ...

    async def fill(self, value: str, *, timeout: float | None = None) -> None: ...

    async def press(self, key: str, *, timeout: float | None = None) -> None: ...


class FrameLike(Protocol):
    """A Frame: its current URL, its parent, and selector queries inside it."""

    @property
    def url(self) -> str: ...

    @property
    def parent_frame(self) -> "FrameLike | None": ...

    async def query_selector_all(self, selector: str) -> Sequence[ElementLike]: ...

    async def eval_on_selector_all(self, selector: str, expression: str) -> Any: ...


class PageLike(Protocol):
    """A Page: its top-level URL, all of its frames, and its close event."""

    @property
    def url(self) -> str: ...

    @property
    def frames(self) -> Sequence[FrameLike]: ...

    def once(self, event: str, callback: Callable[..., Any]) -> Any: ...
