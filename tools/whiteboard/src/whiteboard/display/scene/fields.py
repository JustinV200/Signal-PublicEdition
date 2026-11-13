"""Small validators for untrusted JSON fields (API bodies and scene.json).

Shared by the scene parsers here and by the server's request parsing, so every
boundary rejects bad input the same way, with a SceneError naming the field.
"""

import math
from typing import Any

from whiteboard.display.scene.model import SceneError


def require_object(data: Any, label: str) -> dict[str, Any]:
    """Check that a value is a JSON object.

    Args:
        data: The parsed JSON value.
        label: What the value is, for the error message.

    Returns:
        The same value, typed as a dict.

    Raises:
        SceneError: If it isn't a dict.
    """
    if not isinstance(data, dict):
        raise SceneError(f"{label} must be a JSON object, got {type(data).__name__}")
    return data


def check_keys(data: dict[str, Any], allowed: tuple[str, ...], label: str) -> None:
    """Reject keys that aren't in `allowed`, so typos fail loudly instead of being ignored.

    Raises:
        SceneError: Naming the unknown keys and the valid ones.
    """
    unknown = sorted(set(data) - set(allowed))
    if unknown:
        raise SceneError(
            f"{label}: unknown key(s) {', '.join(unknown)}; valid: {', '.join(allowed)}"
        )


def require_number(
    value: Any, label: str, *, minimum: float | None = None, maximum: float | None = None
) -> float:
    """Check that a value is a finite number (not a bool), optionally within inclusive bounds.

    Args:
        value: The raw value.
        label: The field name, for the error message.
        minimum: Smallest allowed value, or None for no lower bound.
        maximum: Largest allowed value, or None for no upper bound.

    Returns:
        The value as a float.

    Raises:
        SceneError: If it isn't a finite number, or is out of bounds.
    """
    # bool is a subclass of int, so it is excluded on purpose.
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise SceneError(f"{label} must be a number, got {value!r}")
    number = float(value)
    if not math.isfinite(number):
        raise SceneError(f"{label} must be finite, got {value!r}")
    if minimum is not None and number < minimum:
        raise SceneError(f"{label} must be at least {minimum}, got {value!r}")
    if maximum is not None and number > maximum:
        raise SceneError(f"{label} must be at most {maximum}, got {value!r}")
    return number


def require_positive(value: Any, label: str) -> float:
    """Check that a value is a finite number greater than zero (a width, height or duration).

    Raises:
        SceneError: If it isn't.
    """
    number = require_number(value, label)
    if number <= 0:
        raise SceneError(f"{label} must be greater than 0, got {value!r}")
    return number


def require_str(value: Any, label: str) -> str:
    """Check that a value is a string.

    Raises:
        SceneError: If it isn't.
    """
    if not isinstance(value, str):
        raise SceneError(f"{label} must be a string, got {type(value).__name__}")
    return value


def require_bool(value: Any, label: str) -> bool:
    """Check that a value is a JSON boolean.

    Raises:
        SceneError: If it isn't.
    """
    if not isinstance(value, bool):
        raise SceneError(f"{label} must be true or false, got {value!r}")
    return value
