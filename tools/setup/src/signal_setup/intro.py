"""The intro paragraph: the first screen of setup and the top of the README.

data/intro.txt is its single source; a test checks the README still matches it.
"""

from importlib import resources


def intro_text() -> str:
    """The intro paragraph, without a trailing newline."""
    return resources.files("signal_setup").joinpath("data/intro.txt").read_text("utf-8").strip()
