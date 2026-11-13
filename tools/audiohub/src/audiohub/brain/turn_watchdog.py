"""Stall watchdog for ClaudeBrain: wait for a turn's next event, or give up on a silent turn.

Used by claude_brain.ClaudeBrain.ask(). Kept apart so the brain file stays small.
"""

import asyncio
import logging

from audiohub.brain.connection import BrainSession
from audiohub.brain.turn_router import TurnEvent, TurnRouter

logger = logging.getLogger(__name__)

# Longest wait for the CLI to acknowledge stopping a stalled turn. A hung CLI
# mustn't add its own long timeout on top of the stall the user already sat through.
STALLED_INTERRUPT_TIMEOUT_S = 5.0


class TurnStalledError(RuntimeError):
    """Claude showed no activity on a request for `turn_stall_timeout_s`; ask() gave up on it."""


async def next_turn_event(
    router: TurnRouter,
    session: BrainSession | None,
    turn_events: asyncio.Queue[TurnEvent],
    stall_timeout_s: float,
) -> TurnEvent:
    """The open turn's next event, or TurnStalledError after `stall_timeout_s` without one.

    On a stall the turn is abandoned in the router and the session (if any) is
    asked to interrupt it.
    """
    try:
        return await asyncio.wait_for(turn_events.get(), stall_timeout_s)
    except TimeoutError:
        # The result may never come (e.g. the CLI merged this request into
        # another turn), so stop waiting. The turn stays marked as running
        # in the background, so its late text can't pass for the next
        # request's reply, and the CLI is asked to end it.
        router.abandon_turn()
        await interrupt_stalled_turn(session)
        raise TurnStalledError(
            f"Claude showed no activity for {stall_timeout_s:.0f} s; gave up on the request"
        ) from None


async def interrupt_stalled_turn(session: BrainSession | None) -> None:
    """Ask the CLI to stop a turn the watchdog gave up on. A failure is logged, not raised."""
    if session is None:
        return
    try:
        await asyncio.wait_for(session.interrupt(), STALLED_INTERRUPT_TIMEOUT_S)
    except TimeoutError:
        logger.warning(
            "the Claude CLI didn't confirm stopping the stalled turn within %.0f s",
            STALLED_INTERRUPT_TIMEOUT_S,
        )
    except Exception:
        # The stall is reported to the user either way. A CLI too broken to
        # interrupt surfaces as a session error on the next ask().
        logger.exception("could not interrupt the stalled Claude turn")
