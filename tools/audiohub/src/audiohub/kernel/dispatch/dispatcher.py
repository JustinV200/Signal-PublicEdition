"""The Sonnet dispatcher: decides what is spoken, in which order, and what waits.

It renders the pending messages into a request, asks the backend (Sonnet),
strictly validates the reply and enforces the kernel's fixed rules on it (see
safeguards.py). Any timeout, bad reply or SDK error falls back to the
deterministic `fallback_policy`, so a message is never lost.
"""

import asyncio
import logging
import time
from collections.abc import Callable, Sequence

from audiohub.config import KernelSettings

from ..messages import Decision, DeliveredRecord, OutboundMessage
from .backend import DispatcherBackend, SonnetBackend
from .decisions import DecisionError, parse_decisions
from .fallback import fallback_policy
from .prompt import DISPATCHER_PROMPT, DecisionRequest, render_request
from .safeguards import fast_path_decisions

logger = logging.getLogger(__name__)

# How much of a rejected reply to show in the log.
LOGGED_REPLY_CHARS = 500


class Dispatcher:
    """Orders, condenses, holds or drops pending messages with Sonnet's help."""

    def __init__(
        self,
        kernel_settings: KernelSettings,
        backend: DispatcherBackend | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        """Create a dispatcher.

        Args:
            kernel_settings: Model, word limit and decision timeout.
            backend: Where requests go; defaults to a persistent Sonnet session.
                Tests pass a fake.
            clock: Returns the current Unix time, used for message ages.
        """
        self._settings = kernel_settings
        self._backend = backend or SonnetBackend(kernel_settings.model, DISPATCHER_PROMPT)
        self._clock = clock

    async def start(self) -> None:
        """Connect the backend ahead of the first decision (optional; it also connects lazily).

        Raises:
            Exception: Whatever the backend raises when it can't connect.
        """
        await self._backend.start()

    async def close(self) -> None:
        """Release the backend's session."""
        await self._backend.close()

    async def decide(
        self,
        pending: Sequence[OutboundMessage],
        recent_delivered: Sequence[DeliveredRecord],
    ) -> list[Decision]:
        """Decide what to do with every pending message.

        Args:
            pending: Messages waiting to be spoken, oldest arrival first.
            recent_delivered: What the user already heard, oldest first.

        Returns:
            One decision per pending message, in speaking order. Empty if
            nothing is pending. Short direct replies, urgent messages and a
            lone short, fresh notification are delivered verbatim without
            asking Sonnet (the fast path in safeguards.py).
        """
        if not pending:
            return []
        max_words = self._settings.max_spoken_words
        fast = fast_path_decisions(pending, recent_delivered, max_words)
        if fast is not None:
            logger.info(
                "dispatcher fast path: %s delivered without Sonnet",
                ", ".join(d.message_id for d in fast),
            )
            return fast
        request = DecisionRequest(
            pending=tuple(pending),
            recent_delivered=tuple(recent_delivered),
            max_spoken_words=self._settings.max_spoken_words,
            now=self._clock(),
        )
        started = time.perf_counter()
        decisions = await self._ask_or_fall_back(request)
        logger.info(
            "dispatcher decided %d message(s) in %.2fs: %s",
            len(decisions),
            time.perf_counter() - started,
            ", ".join(f"{d.message_id}={d.action}" for d in decisions),
        )
        return decisions

    async def _ask_or_fall_back(self, request: DecisionRequest) -> list[Decision]:
        """Ask the backend and validate its reply; on any failure use the fallback policy."""
        timeout_s = self._settings.decision_timeout_s
        reply = ""
        try:
            reply = await asyncio.wait_for(
                self._backend.complete(render_request(request)), timeout_s
            )
            return parse_decisions(reply, request)
        except TimeoutError:
            logger.warning("dispatcher timed out after %.1fs; using the fallback policy", timeout_s)
        except DecisionError as error:
            logger.warning(
                "dispatcher reply rejected (%s); using the fallback policy. Reply: %r",
                error,
                reply[:LOGGED_REPLY_CHARS],
            )
        except Exception:
            # Any SDK or transport failure: the fallback still delivers everything.
            logger.exception("dispatcher backend failed; using the fallback policy")
        return fallback_policy(request.pending)
