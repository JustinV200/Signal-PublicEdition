"""Check that a field's page and frames are on the credential's registered origins.

Runs twice per fill: once before asking the owner, and again immediately
before filling (the page may have navigated during the confirmation). Both the
top-level page and every frame from the field up to the top must match, so a
login form in a frame nested inside a foreign frame is refused too.
"""

from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from vault.fill.page_protocol import ElementLike, FrameLike, PageLike
from vault.origin import describe_origin, url_matches_origins

DETACHED_LABEL = "<detached>"


@dataclass(frozen=True)
class OriginCheck:
    """Result of an origin check, with token-free labels for the dialog and audit log."""

    ok: bool
    top_origin: str
    frame_origin: str


def _frame_chain(frame: FrameLike) -> Iterator[FrameLike]:
    """Yield `frame` and each of its ancestors up to the main frame."""
    current: FrameLike | None = frame
    while current is not None:
        yield current
        current = current.parent_frame


async def check_field_origins(
    page: PageLike, field: ElementLike, allowed_origins: Sequence[str]
) -> OriginCheck:
    """Check the top-level page and the field's frame chain against `allowed_origins`.

    about:blank, about:srcdoc, data: and blob: frames have no https origin, so
    they fail even when they inherit a registered origin in the browser.

    Args:
        page: The page holding the field.
        field: The ElementHandle about to be filled.
        allowed_origins: The credential's registered origins (AAD-bound).

    Returns:
        ok=True only if every URL in the chain has an exactly matching origin.

    Raises:
        Exception: Playwright errors propagate (the fill sequence makes them "error").
    """
    top_url = page.url
    frame = await field.owner_frame()
    if frame is None:
        return OriginCheck(
            ok=False, top_origin=describe_origin(top_url), frame_origin=DETACHED_LABEL
        )
    chain_matches = all(
        url_matches_origins(link.url, allowed_origins) for link in _frame_chain(frame)
    )
    is_ok = chain_matches and url_matches_origins(top_url, allowed_origins)
    return OriginCheck(
        ok=is_ok, top_origin=describe_origin(top_url), frame_origin=describe_origin(frame.url)
    )
