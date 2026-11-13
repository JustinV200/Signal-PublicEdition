"""The `brain_kit` fixture: a scripted fake BrainSession and a ClaudeBrain harness (no SDK).

Test modules can't import each other (pytest runs with --import-mode=importlib),
so the fakes are handed out as one namespace fixture, like tests/loop's `fakes`.
"""

import asyncio
from collections import deque
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from types import SimpleNamespace

import pytest

from audiohub.brain import ClaudeBrain, ReplyText, SessionEvent, TurnDone
from audiohub.brain.handoff_tool import HandOff, MainSessionHandoff
from audiohub.brain.permissions import PermissionDecider
from audiohub.config import BrainSettings

CWD = Path(r"C:\src\Signal")
END_OF_STREAM = object()
MAX_LOOP_TURNS = 100


class FakeSession:
    """A BrainSession whose stream plays back one scripted turn per send().

    `decide_permission` and `hand_off` are what the real session would hand the
    CLI, so a test can call them the way the CLI would.
    """

    def __init__(
        self,
        turns: deque[list[SessionEvent]],
        decide_permission: PermissionDecider,
        hand_off: HandOff,
        settings: BrainSettings,
    ) -> None:
        # Shared with the harness, so a reconnected session plays the next turn.
        self.scripted_turns = turns
        self.settings = settings
        self.decide_permission = decide_permission
        self.hand_off = hand_off
        self.sent: list[str] = []
        self.disconnect_count = 0
        self.interrupt_count = 0
        self.models_set: list[str] = []
        self.resumed: str | None = None
        self.connect_error: Exception | None = None
        self.session_id: str | None = None
        self.mcp_statuses: dict[str, str] = {}
        self.mcp_reconnected: list[str] = []
        self.stream: asyncio.Queue[object] = asyncio.Queue()

    async def connect(self, resume: str | None = None) -> None:
        if self.connect_error is not None:
            raise self.connect_error
        self.resumed = resume

    async def set_model(self, model: str) -> None:
        self.models_set.append(model)

    async def mcp_server_statuses(self) -> dict[str, str]:
        return self.mcp_statuses

    async def reconnect_mcp_server(self, name: str) -> None:
        self.mcp_reconnected.append(name)

    async def disconnect(self) -> None:
        self.disconnect_count += 1
        self.stream.put_nowait(END_OF_STREAM)

    async def send(self, text: str) -> None:
        self.sent.append(text)
        self.inject(*self.scripted_turns.popleft())

    def inject(self, *items: object) -> None:
        """Put events (or an exception, or END_OF_STREAM) on the wire."""
        for item in items:
            self.stream.put_nowait(item)

    async def events(self) -> AsyncIterator[SessionEvent]:
        while True:
            item = await self.stream.get()
            if item is END_OF_STREAM:
                return
            if isinstance(item, Exception):
                raise item
            yield item  # type: ignore[misc]

    async def interrupt(self) -> None:
        self.interrupt_count += 1


class Harness:
    """Builds a ClaudeBrain wired to a FakeSession and records what reaches the loop."""

    def __init__(
        self,
        turns: list[list[SessionEvent]],
        settings: BrainSettings | None = None,
        main_session: MainSessionHandoff | None = None,
        choice_path: Path | None = None,
        cwd: Path = CWD,
    ) -> None:
        self.turns = deque(turns)
        self.background: list[str] = []
        self.tool_calls: list[str] = []
        self.sessions: list[FakeSession] = []
        # How many of the next sessions fail to connect.
        self.failing_connects = 0
        self.brain = ClaudeBrain(
            settings or BrainSettings(),
            cwd,
            session_factory=self.make_session,
            on_background_text=self.background.append,
            on_tool_call=self.tool_calls.append,
            # A claim path that never exists, unless a test brings its own sender.
            main_session=main_session or MainSessionHandoff(CWD / "no-claim-in-tests.json"),
            # A pick file that never exists, unless a test brings its own.
            choice_path=choice_path or CWD / "no-brain-choice-in-tests.json",
        )

    def make_session(
        self,
        settings: BrainSettings,
        cwd: Path,
        decide_permission: PermissionDecider,
        hand_off: HandOff,
    ) -> FakeSession:
        self.sessions.append(FakeSession(self.turns, decide_permission, hand_off, settings))
        if self.failing_connects:
            self.failing_connects -= 1
            self.sessions[-1].connect_error = RuntimeError("the CLI didn't start")
        return self.sessions[-1]

    @property
    def session(self) -> FakeSession:
        return self.sessions[-1]


async def collect(events: AsyncIterator[ReplyText | TurnDone]) -> list[ReplyText | TurnDone]:
    return [event async for event in events]


async def wait_until(condition: Callable[[], bool]) -> None:
    """Let the reader task run until condition holds."""
    for _ in range(MAX_LOOP_TURNS):
        if condition():
            return
        await asyncio.sleep(0)
    raise AssertionError("condition never became true")


@pytest.fixture
def brain_kit() -> SimpleNamespace:
    """The harness class and the helpers the ClaudeBrain tests use."""
    return SimpleNamespace(Harness=Harness, collect=collect, wait_until=wait_until)
