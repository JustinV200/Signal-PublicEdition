"""What the parent sends the dialog child on stdin (DialogRequest JSON) and what it prints back.

Both sides validate through DialogRequest, so a bad request is refused before
any window appears.
"""

import json
import math
from dataclasses import asdict, dataclass

# The child prints exactly one of these on stdout; anything else means deny.
ALLOW_TOKEN = "allow"
DENY_TOKEN = "deny"
# Upper bound for both timings, so a bad caller can't park a dialog on screen for days.
MAX_SECONDS = 3600.0


@dataclass(frozen=True)
class DialogRequest:
    """One Allow/Deny question.

    Attributes:
        title: Window title (untrusted; the dialog sanitizes it).
        message: Body text, lines separated by "\\n" (untrusted; sanitized too).
        timeout_s: Seconds after which the dialog denies by itself.
        arm_delay_s: Seconds Allow stays disabled after the window appears.

    Raises:
        TypeError: If a field has the wrong type.
        ValueError: If a timing is not finite or is outside 0..MAX_SECONDS.
    """

    title: str
    message: str
    timeout_s: float
    arm_delay_s: float

    def __post_init__(self) -> None:
        """Validate the fields (see the class docstring for what is raised)."""
        if not isinstance(self.title, str) or not isinstance(self.message, str):
            raise TypeError("title and message must be strings")
        _check_seconds("timeout_s", self.timeout_s)
        _check_seconds("arm_delay_s", self.arm_delay_s)

    def to_json(self) -> bytes:
        """Encode for the child's stdin (ASCII-only JSON)."""
        return json.dumps(asdict(self)).encode("ascii")

    @classmethod
    def from_json(cls, raw: bytes) -> "DialogRequest":
        """Decode and validate what the parent sent.

        Raises:
            ValueError: If `raw` isn't a JSON object or a timing is invalid.
            TypeError: If fields are missing, unknown or of the wrong type.
        """
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("the request must be a JSON object")
        return cls(**data)


def _check_seconds(name: str, value: object) -> None:
    """Raise unless `value` is a finite number of seconds in 0..MAX_SECONDS."""
    # bool is an int subclass, but True seconds is a bug, not a timing.
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"{name} must be a number")
    if not math.isfinite(value) or not 0 <= value <= MAX_SECONDS:
        raise ValueError(f"{name} must be between 0 and {MAX_SECONDS:.0f} seconds")
