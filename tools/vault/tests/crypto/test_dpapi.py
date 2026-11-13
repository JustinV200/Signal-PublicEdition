"""DPAPI via ctypes, against the real Windows API for the current user."""

import sys

import pytest

from vault.crypto.dpapi import DpapiError, protect, unprotect

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="DPAPI is Windows-only")


def test_protect_round_trips_and_needs_the_same_entropy():
    blob = protect(b"dpapi secret", b"entropy-a")

    assert b"dpapi secret" not in blob
    assert unprotect(blob, b"entropy-a") == bytearray(b"dpapi secret")
    with pytest.raises(DpapiError):
        unprotect(blob, b"entropy-b")
