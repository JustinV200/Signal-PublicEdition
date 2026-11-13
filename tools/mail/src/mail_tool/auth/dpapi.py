"""Windows DPAPI (CryptProtectData / CryptUnprotectData, CurrentUser scope) through ctypes.

Encrypts each account's refresh token at rest so a copied file, or another
Windows account, can't use it. Same-user code can still decrypt; that's the
DPAPI limit. Copied from tools/vault/src/vault/crypto/dpapi.py, because the
tools are separate uv projects that don't share code.
"""

import ctypes
import functools
from collections.abc import Callable
from ctypes import wintypes

# Never show DPAPI's own (deprecated) prompt UI.
CRYPTPROTECT_UI_FORBIDDEN = 0x1


class DpapiError(Exception):
    """DPAPI refused to protect or unprotect (wrong user, corrupt blob, wrong entropy)."""


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


@functools.cache
def _crypt32() -> ctypes.WinDLL:
    """Load crypt32 lazily so importing this module never fails off Windows."""
    library = ctypes.WinDLL("crypt32", use_last_error=True)
    for name in ("CryptProtectData", "CryptUnprotectData"):
        function = getattr(library, name)
        function.restype = wintypes.BOOL
    return library


@functools.cache
def _local_free() -> Callable[[ctypes.c_void_p], ctypes.c_void_p]:
    """Return kernel32!LocalFree, which releases DPAPI's output buffer."""
    function = ctypes.WinDLL("kernel32", use_last_error=True).LocalFree
    function.argtypes = [ctypes.c_void_p]
    function.restype = ctypes.c_void_p
    return function


def _blob_for(buffer: ctypes.Array) -> _DataBlob:
    """Point a DATA_BLOB at an existing ctypes buffer (no copy)."""
    return _DataBlob(len(buffer), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))


def _take_output(blob: _DataBlob) -> bytes:
    """Copy DPAPI's output, then zero and free the original buffer."""
    size = blob.cbData
    result = ctypes.string_at(blob.pbData, size)
    ctypes.memset(blob.pbData, 0, size)
    _local_free()(ctypes.cast(blob.pbData, ctypes.c_void_p))
    return result


def _call(function_name: str, data: bytes, entropy: bytes) -> bytes:
    """Run CryptProtectData or CryptUnprotectData over `data` and return the output."""
    data_buffer = (ctypes.c_char * len(data)).from_buffer_copy(data)
    entropy_buffer = (ctypes.c_char * len(entropy)).from_buffer_copy(entropy)
    data_in, entropy_in, data_out = _blob_for(data_buffer), _blob_for(entropy_buffer), _DataBlob()
    function = getattr(_crypt32(), function_name)
    try:
        succeeded = function(
            ctypes.byref(data_in),
            None,
            ctypes.byref(entropy_in),
            None,
            None,
            CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(data_out),
        )
    finally:
        # The input copy may be a secret; zero it whatever happened.
        ctypes.memset(data_buffer, 0, len(data_buffer))
    if not succeeded:
        raise DpapiError(f"{function_name} failed (Windows error {ctypes.get_last_error()})")
    return _take_output(data_out)


def protect(secret: bytes, entropy: bytes) -> bytes:
    """Encrypt `secret` so only this Windows user can decrypt it.

    Args:
        secret: The bytes to protect.
        entropy: Extra application-specific bytes that must match on unprotect.

    Returns:
        The opaque DPAPI blob (safe to store on disk).

    Raises:
        DpapiError: DPAPI failed.
    """
    return _call("CryptProtectData", secret, entropy)


def unprotect(blob: bytes, entropy: bytes) -> bytes:
    """Decrypt a blob made by `protect` for the current Windows user.

    Args:
        blob: The DPAPI blob.
        entropy: The same entropy given to `protect`.

    Returns:
        The secret.

    Raises:
        DpapiError: Wrong user, corrupt blob or different entropy.
    """
    return _call("CryptUnprotectData", blob, entropy)
