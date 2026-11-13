"""Tests for audiohub.cli.main: argument parsing, settings hand-off, and error exits."""

from pathlib import Path

import pytest

from audiohub.audio import DeviceNotFoundError
from audiohub.cli.command import Command
from audiohub.cli.main import EXIT_USER_ERROR, build_parser, main


def recording_command(calls: list, exit_code: int = 0, error: Exception | None = None) -> Command:
    def add_arguments(parser):
        parser.add_argument("--flag", action="store_true")

    def run(args, settings):
        calls.append((args, settings))
        if error is not None:
            raise error
        return exit_code

    return Command(name="probe", help="test command", add_arguments=add_arguments, run=run)


def test_global_options_work_before_the_command():
    args = build_parser().parse_args(["--config", "x.toml", "--input-device", "3", "devices"])
    assert args.config == Path("x.toml")
    assert args.input_device == 3


def test_global_options_work_after_the_command():
    args = build_parser().parse_args(["devices", "--output-device", "Hands-Free"])
    assert args.output_device == "Hands-Free"
    assert args.config is None


def test_unknown_command_is_a_usage_error():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["dance"])


def test_main_runs_the_command_with_device_overrides_applied(tmp_path):
    config = tmp_path / "a.toml"
    config.write_text("[audio]\ninput_device = 'mic'\noutput_device = 'speakers'\n")
    calls: list = []
    commands = (recording_command(calls, exit_code=5),)
    argv = ["--config", str(config), "probe", "--flag", "--output-device", "4"]
    assert main(argv, commands=commands) == 5
    args, settings = calls[0]
    assert args.flag is True
    assert settings.audio.input_device == "mic"
    assert settings.audio.output_device == 4


def test_main_reports_config_errors_without_running(tmp_path, capsys):
    calls: list = []
    argv = ["--config", str(tmp_path / "missing.toml"), "probe"]
    assert main(argv, commands=(recording_command(calls),)) == EXIT_USER_ERROR
    assert calls == []
    assert "config file not found" in capsys.readouterr().err


def test_main_turns_device_errors_into_a_clean_message(capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    error = DeviceNotFoundError("no input device named 'x'")
    commands = (recording_command([], error=error),)
    assert main(["probe"], commands=commands) == EXIT_USER_ERROR
    assert "audiohub: error: no input device named 'x'" in capsys.readouterr().err
