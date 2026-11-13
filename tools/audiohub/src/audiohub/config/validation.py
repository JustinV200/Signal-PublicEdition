"""Type and range validation that turns raw TOML tables into settings dataclasses.

Generic over any dataclass: each field's annotation decides which TOML values
it accepts, `bounded()` field metadata adds numeric range checks, and
`one_of()` metadata restricts a field to a fixed set of values. The loader
(loader.py) calls `build_section` once per [section] table.
"""

import dataclasses
import math
import types
import typing
from typing import Any

# Field metadata keys written by `bounded()` and read by `_check_bounds()`.
MIN_KEY = "min"
MAX_KEY = "max"
# Field metadata key written by `one_of()` and read by `_check_choices()`.
CHOICES_KEY = "choices"

_NONE_TYPE = type(None)


class ConfigError(ValueError):
    """Raised for a missing or unparsable config file, or a bad key or value in it."""


def bounded(default: float, *, minimum: float | None = None, maximum: float | None = None) -> Any:
    """Declare a numeric dataclass field whose configured value must lie in a range.

    Args:
        default: The field's default value.
        minimum: Smallest allowed value (inclusive), or None for no lower bound.
        maximum: Largest allowed value (inclusive), or None for no upper bound.

    Returns:
        A `dataclasses.field` carrying the bounds in its metadata.
    """
    return dataclasses.field(default=default, metadata={MIN_KEY: minimum, MAX_KEY: maximum})


def one_of(default: str, choices: tuple[str, ...]) -> Any:
    """Declare a string dataclass field whose configured value must be one of `choices`.

    Args:
        default: The field's default value. Must itself be in `choices`.
        choices: Every allowed value.

    Returns:
        A `dataclasses.field` carrying the choices in its metadata.

    Raises:
        ValueError: If `default` isn't in `choices` (a programming error).
    """
    if default not in choices:
        raise ValueError(f"default {default!r} is not one of {choices!r}")
    return dataclasses.field(default=default, metadata={CHOICES_KEY: choices})


def build_section[T](section_cls: type[T], table: dict[str, Any], section_name: str) -> T:
    """Validate one TOML table and build the matching settings dataclass.

    Keys missing from `table` keep the dataclass defaults.

    Args:
        section_cls: The dataclass for this section, e.g. `DuckingSettings`.
        table: The raw TOML table for the section.
        section_name: The section's name, used in error messages.

    Returns:
        An instance of `section_cls`.

    Raises:
        ConfigError: On an unknown key, a wrong type, or an out-of-range number.
    """
    fields = {field.name: field for field in dataclasses.fields(section_cls)}
    unknown_keys = sorted(set(table) - set(fields))
    if unknown_keys:
        raise ConfigError(
            f"[{section_name}] unknown key(s): {', '.join(unknown_keys)}. "
            f"Valid keys: {', '.join(fields)}"
        )

    annotations = typing.get_type_hints(section_cls)
    values: dict[str, Any] = {}
    for key, raw_value in table.items():
        key_path = f"{section_name}.{key}"
        value = coerce_value(raw_value, annotations[key], key_path)
        _check_bounds(value, fields[key].metadata, key_path)
        _check_choices(value, fields[key].metadata, key_path)
        values[key] = value
    return section_cls(**values)


def coerce_value(raw_value: Any, annotation: Any, key_path: str) -> Any:
    """Check a TOML value against a field annotation and convert it if needed.

    Supported annotations: bool, int, float, str, unions of those (None members
    are skipped because TOML has no null), and `tuple[X, ...]` from a TOML array.
    An int is accepted for a float field and converted.

    Args:
        raw_value: The value as parsed by tomllib.
        annotation: The resolved field annotation.
        key_path: "section.key" for error messages.

    Returns:
        The value converted to the annotated type.

    Raises:
        ConfigError: If the value doesn't match the annotation.
        TypeError: If the annotation itself is unsupported (a programming error).
    """
    origin = typing.get_origin(annotation)
    if origin in (types.UnionType, typing.Union):
        return _coerce_union(raw_value, typing.get_args(annotation), key_path)
    if origin is tuple:
        return _coerce_tuple(raw_value, typing.get_args(annotation), key_path)
    return _coerce_scalar(raw_value, annotation, key_path)


def _coerce_scalar(raw_value: Any, expected: type, key_path: str) -> Any:
    # bool is a subclass of int in Python, so it is excluded from int/float on purpose.
    is_bool = isinstance(raw_value, bool)
    if expected is bool and is_bool:
        return raw_value
    if expected is int and isinstance(raw_value, int) and not is_bool:
        return raw_value
    if expected is float and isinstance(raw_value, int | float) and not is_bool:
        return _finite_float(raw_value, key_path)
    if expected is str and isinstance(raw_value, str):
        return raw_value
    if expected not in (bool, int, float, str):
        raise TypeError(f"unsupported settings field type {expected!r} for {key_path}")
    raise _type_error(raw_value, expected.__name__, key_path)


def _finite_float(raw_value: float, key_path: str) -> float:
    # TOML allows nan and inf. NaN slips past every range check (all
    # comparisons are False), and no setting means anything at infinity.
    value = float(raw_value)
    if not math.isfinite(value):
        raise ConfigError(f"{key_path}: expected a finite number, got {raw_value!r}")
    return value


def _coerce_union(raw_value: Any, members: tuple[Any, ...], key_path: str) -> Any:
    candidates = [member for member in members if member is not _NONE_TYPE]
    for member in candidates:
        try:
            return coerce_value(raw_value, member, key_path)
        except ConfigError:
            continue
    expected_label = " or ".join(_type_label(member) for member in candidates)
    raise _type_error(raw_value, expected_label, key_path)


def _coerce_tuple(raw_value: Any, args: tuple[Any, ...], key_path: str) -> tuple[Any, ...]:
    # Only homogeneous tuples (tuple[X, ...]) are used by the settings classes.
    if len(args) != 2 or args[1] is not Ellipsis:
        raise TypeError(f"unsupported tuple annotation {args!r} for {key_path}")
    if not isinstance(raw_value, list):
        raise _type_error(raw_value, f"array of {_type_label(args[0])}", key_path)
    return tuple(
        coerce_value(item, args[0], f"{key_path}[{position}]")
        for position, item in enumerate(raw_value)
    )


def _check_bounds(value: Any, metadata: Any, key_path: str) -> None:
    minimum = metadata.get(MIN_KEY)
    maximum = metadata.get(MAX_KEY)
    if minimum is not None and value < minimum:
        raise ConfigError(f"{key_path}: {value} is below the minimum of {minimum}")
    if maximum is not None and value > maximum:
        raise ConfigError(f"{key_path}: {value} is above the maximum of {maximum}")


def _check_choices(value: Any, metadata: Any, key_path: str) -> None:
    choices = metadata.get(CHOICES_KEY)
    if choices is not None and value not in choices:
        raise ConfigError(f"{key_path}: {value!r} is not one of {', '.join(choices)}")


def _type_label(annotation: Any) -> str:
    return getattr(annotation, "__name__", str(annotation))


def _type_error(raw_value: Any, expected_label: str, key_path: str) -> ConfigError:
    actual = type(raw_value).__name__
    return ConfigError(f"{key_path}: expected {expected_label}, got {actual} {raw_value!r}")
