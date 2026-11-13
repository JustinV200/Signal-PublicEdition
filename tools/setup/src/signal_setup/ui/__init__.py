"""The terminal UI: prompts, the tool checklist, and the full interactive setup flow.

Public API: run_setup. (Prompts live in signal_setup.terminal.)
"""

from signal_setup.ui.flow import run_setup

__all__ = ["run_setup"]
