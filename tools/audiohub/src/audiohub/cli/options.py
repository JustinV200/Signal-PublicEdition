"""Global CLI options (--config, --input-device, --output-device) and settings from them.

The options are accepted both before and after the command name
(`audiohub --config x.toml devices` and `audiohub devices --config x.toml`).
"""

import argparse
import dataclasses
from pathlib import Path

from audiohub.config import Settings, load_settings


def add_global_options(parser: argparse.ArgumentParser, *, is_subcommand: bool = False) -> None:
    """Add the global options to the top-level parser or to a command's subparser.

    Args:
        parser: The parser to extend.
        is_subcommand: True for a subparser. Its options then default to
            argparse.SUPPRESS, so an option given before the command name
            isn't overwritten by the subparser's default.
    """
    default = argparse.SUPPRESS if is_subcommand else None
    parser.add_argument(
        "--config",
        type=Path,
        metavar="PATH",
        default=default,
        help="config file (default: tools/audiohub/audiohub.toml if it exists)",
    )
    parser.add_argument(
        "--input-device",
        type=parse_device_spec,
        metavar="DEVICE",
        default=default,
        help="input device name substring or index; overrides the config",
    )
    parser.add_argument(
        "--output-device",
        type=parse_device_spec,
        metavar="DEVICE",
        default=default,
        help="output device name substring or index; overrides the config",
    )


def parse_device_spec(text: str) -> str | int:
    """Parse a --*-device value: all ASCII digits is an index, anything else a name.

    Raises:
        argparse.ArgumentTypeError: If the value is empty.
    """
    spec = text.strip()
    if not spec:
        raise argparse.ArgumentTypeError("device must not be empty")
    if spec.isascii() and spec.isdigit():
        return int(spec)
    return spec


def settings_from_args(args: argparse.Namespace) -> Settings:
    """Load settings from --config (or the default file) and apply the device flags.

    Raises:
        ConfigError: If the config file is missing or invalid.
    """
    settings = load_settings(args.config)
    return apply_device_overrides(settings, args.input_device, args.output_device)


def apply_device_overrides(
    settings: Settings, input_device: str | int | None, output_device: str | int | None
) -> Settings:
    """Return settings with the given device specs replacing the configured ones.

    A None argument keeps the configured device.
    """
    audio = settings.audio
    if input_device is not None:
        audio = dataclasses.replace(audio, input_device=input_device)
    if output_device is not None:
        audio = dataclasses.replace(audio, output_device=output_device)
    return dataclasses.replace(settings, audio=audio)
