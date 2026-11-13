"""The real terminal guard: Windows says isatty() for NUL, so the console check must catch it."""

import os
import sys

import pytest

from vault.cli.terminal import CliError, require_interactive_stdin


@pytest.mark.skipif(sys.platform != "win32", reason="the NUL quirk is Windows-only")
def test_stdin_redirected_from_nul_is_refused_although_isatty_is_true():
    with open(os.devnull) as nul:
        assert nul.isatty()  # the Windows quirk this guards against

        with pytest.raises(CliError, match="not an interactive terminal"):
            require_interactive_stdin(nul)
