"""The terminal UI: prompts, the tool checklist, and the full interactive setup flow.

Public API: run_setup, and run_one_step (`setup step`). (Prompts live in signal_setup.terminal.)
"""

from signal_setup.ui.flow import run_one_step, run_setup

__all__ = ["run_one_step", "run_setup"]
