"""Apply the console's voice pick (brain-choice.json) on top of the [brain] settings.

The console writes the owner's model and effort pick for voice; the brain calls
this at connect and before each turn. signal_modelchoice checks each value
against the fixed lists, and an unset or unlisted one keeps audiohub.toml's.
"""

from dataclasses import replace
from pathlib import Path

from signal_modelchoice import read_brain_choice

from audiohub.config.settings import BrainSettings


def with_brain_choice(settings: BrainSettings, choice_path: Path) -> BrainSettings:
    """`settings` with the pick in `choice_path` (if any) as its model and effort.

    Args:
        settings: The [brain] settings from audiohub.toml.
        choice_path: brain-choice.json; a missing or malformed file changes nothing.

    Returns:
        A copy with the picked model and effort; never raises.
    """
    choice = read_brain_choice(choice_path)
    return replace(
        settings,
        model=choice.model or settings.model,
        effort=choice.effort or settings.effort,
    )
