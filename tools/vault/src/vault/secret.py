"""`Secret`: a wrapper that keeps a plaintext value out of reprs, logs and pickles.

Decrypted usernames and passwords travel through the fill path inside this
wrapper, and the redaction registry keeps them in it. Only `reveal()` returns
the plaintext, and only the fill step and the scrubber call it.

Python strings can't be wiped, so this is hygiene against accidental printing,
not a memory-safety guarantee.
"""

REDACTED_REPR = "Secret(<redacted>)"


class Secret:
    """Holds one plaintext string. repr/str/format never show it; pickling is refused."""

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        """Wrap `value`.

        Args:
            value: The plaintext to hold.
        """
        self._value = value

    def reveal(self) -> str:
        """Return the plaintext. Call only where the value must leave the vault (a fill)."""
        return self._value

    def __repr__(self) -> str:
        return REDACTED_REPR

    __str__ = __repr__

    def __format__(self, format_spec: str) -> str:
        return REDACTED_REPR

    def __reduce__(self) -> tuple:
        # Blocks pickle and copy, so a secret can't be serialised by accident.
        raise TypeError("Secret values cannot be pickled or copied")
