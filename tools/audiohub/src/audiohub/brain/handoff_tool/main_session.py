"""MainSessionHandoff: send a voice job, with the owner's own recent words, to the main Signal
session.

ClaudeBrain notes each request the hub sends voice (note_request): that is
The owner's speech as the hub transcribed it, never text the model wrote. The
hand-off tool's handler (hand_off) reads the orchestrator's claim and sends
one message through the shared signal_orchestrator sender, the same one the
console uses. The permission gate lets it run without a question, so the
orchestrator judges each job against the owner's own words. It never raises:
every failure becomes a short result telling voice the main session isn't
reachable.
"""

import logging
from collections import deque
from collections.abc import Awaitable, Callable
from pathlib import Path

from signal_orchestrator import Claim, InboxError, read_claim_file, send_to_inbox

from audiohub.brain.handoff_tool.message import compose_handoff, spoken_job

logger = logging.getLogger(__name__)

# How many of the owner's latest requests go with a hand-off. A job is usually
# asked in one or two, plus one for context.
MAX_RECENT_REQUESTS = 3

# Tool results, read by the voice agent (which speaks to the owner).
SENT_RESULT = (
    "Sent to the main Signal session. Tell the owner briefly that it's passed on and the "
    "main session will tell the owner by voice when it's done or if it needs the owner."
)
UNREACHABLE_RESULT = (
    "Nothing was sent: the main Signal session isn't reachable right now. Tell the owner, "
    "and that the owner can type the job into the main session the owner."
)
NO_JOB_RESULT = (
    "Nothing was sent: the job summary had no plain words left to read out. Call it "
    "again with one or two plain sentences saying what the job is."
)

HandOff = Callable[[str], Awaitable[str]]
"""The tool's handler: takes the job summary, returns the result text for Claude."""

SendToInbox = Callable[[Claim, str], Awaitable[None]]


class MainSessionHandoff:
    """Remembers the owner's latest requests and hands jobs to the claimed orchestrator."""

    def __init__(self, claim_path: Path, *, send: SendToInbox = send_to_inbox) -> None:
        """Prepare the hand-off. Nothing is read or sent until hand_off().

        Args:
            claim_path: The claim `console claim` writes (config.ORCHESTRATOR_CLAIM_PATH).
                It's read at each hand-off, so a new claim applies at once.
            send: Delivers the message; tests may pass a fake.
        """
        self._claim_path = claim_path
        self._send = send
        self._recent_requests: deque[str] = deque(maxlen=MAX_RECENT_REQUESTS)

    def note_request(self, text: str) -> None:
        """Remember one request the hub sent voice, the owner's transcribed words."""
        self._recent_requests.append(text)

    async def hand_off(self, job: str) -> str:
        """Send the job and the owner's recent words to the main session. Matches HandOff.

        Args:
            job: The voice agent's summary of the job.

        Returns:
            SENT_RESULT; NO_JOB_RESULT when spoken_job leaves nothing; UNREACHABLE_RESULT
            when there is no usable claim or the inbox can't be reached. The
            reason for a failure is logged, never shown to Claude.
        """
        if not spoken_job(job):
            return NO_JOB_RESULT
        claim = read_claim_file(self._claim_path)
        if claim is None:
            logger.warning("hand-off not sent: no usable claim at %s", self._claim_path)
            return UNREACHABLE_RESULT
        try:
            await self._send(claim, compose_handoff(job, list(self._recent_requests)))
        except InboxError as error:
            logger.warning("hand-off not sent: %s", error)
            return UNREACHABLE_RESULT
        except Exception:
            # Broad on purpose: a bug here must reach the owner as "not sent", not
            # as an error inside the voice session's tool call.
            logger.exception("hand-off failed unexpectedly")
            return UNREACHABLE_RESULT
        logger.info("handed a job to the main session %s: %r", claim.label, spoken_job(job))
        # These words went with this job; the next hand-off carries only newer ones.
        self._recent_requests.clear()
        return SENT_RESULT
