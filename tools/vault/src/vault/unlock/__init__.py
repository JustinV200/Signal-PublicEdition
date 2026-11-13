"""Unlockers: Windows Hello (primary) and passphrase + DPAPI (explicit fallback).

The concrete unlockers are imported lazily by `unlocker_for`, so importing this
package doesn't load WinRT or tkinter.
"""

from vault.unlock.base import (
    PROVIDER_HELLO,
    PROVIDER_PASSPHRASE,
    PROVIDERS,
    Enrollment,
    Unlocker,
    UnlockError,
)
from vault.unlock.factory import unlocker_for

__all__ = [
    "PROVIDERS",
    "PROVIDER_HELLO",
    "PROVIDER_PASSPHRASE",
    "Enrollment",
    "UnlockError",
    "Unlocker",
    "unlocker_for",
]
