"""The `FrameSource` protocol: where the voice loop gets its 16 kHz audio frames.

`audiohub.audio.Microphone` is the real source. `WavFrameSource` stands in
for it in tests and hands-off runs (`audiohub run --input-wav FILE`), which is
why the conversation takes a source rather than opening the mic itself.
"""

from collections.abc import AsyncIterator
from types import TracebackType
from typing import Protocol, Self

import numpy as np


class FrameSource(Protocol):
    """An async context manager that streams float32 mono 16 kHz frames of 512 samples.

    While `paused` is True the source drops audio, so nothing heard during
    that time is ever yielded.
    """

    paused: bool

    async def __aenter__(self) -> Self:
        """Start capturing."""
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Stop capturing and end any `frames()` iteration."""
        ...

    def frames(self) -> AsyncIterator[np.ndarray]:
        """Yield frames until the source is closed."""
        ...
