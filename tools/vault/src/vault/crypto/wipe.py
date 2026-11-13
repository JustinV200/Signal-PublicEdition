"""Best-effort zeroing of key material held in bytearrays.

Keys are kept in bytearrays (not bytes) so they can be overwritten as soon as
they are no longer needed. Copies made inside `cryptography` or OpenSSL can't
be reached from here, so this narrows the window rather than closing it.
"""


def wipe(buffer: bytearray | None) -> None:
    """Overwrite every byte of `buffer` with zero, in place. None is ignored."""
    if buffer is None:
        return
    # Slice assignment of the same length writes into the existing storage.
    buffer[:] = bytes(len(buffer))
