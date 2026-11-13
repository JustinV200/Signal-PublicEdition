"""`vault add`: owner-only (TTY), warns on excluded categories, stores ciphertext only."""

import contextlib
import io
import subprocess
import sys

import pytest

from vault.cli.main import EXIT_USER_ERROR, main
from vault.store import load_vault

ADD_ARGS = ["add", "forum", "--name", "Forum", "--origin", "https://forum.example.test"]


def test_add_refuses_piped_stdin_before_asking_anything(cli, capsys):
    exit_code = main(ADD_ARGS, cli.context(stdin=io.StringIO("hunter2\n")))

    assert exit_code == EXIT_USER_ERROR
    assert "not an interactive terminal" in capsys.readouterr().err
    assert cli.secret_prompts == []
    assert load_vault(cli.store_path).find("forum") is None


def test_add_refuses_piped_stdin_in_a_real_process(tmp_path):
    env = {"LOCALAPPDATA": str(tmp_path), "SYSTEMROOT": "C:\\Windows"}
    command = [sys.executable, "-c", "from vault.cli import main; raise SystemExit(main())"]

    completed = subprocess.run(
        command + ADD_ARGS,
        input="user\nhunter2\n",
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )

    assert completed.returncode == EXIT_USER_ERROR
    assert "refusing" in completed.stderr


def test_add_stores_only_ciphertext_and_prints_only_the_id(cli):
    cli.secrets = ["forum-user", "forum-user", "Forum-Pa55!", "Forum-Pa55!"]

    assert main(ADD_ARGS, cli.context()) == 0

    assert cli.output == ["added forum"]
    store_text = cli.store_path.read_text(encoding="utf-8")
    assert "Forum-Pa55!" not in store_text and "forum-user" not in store_text
    assert load_vault(cli.store_path).find("forum").meta.username_hint == "f***"


def test_add_warns_on_excluded_categories_and_stops_unless_confirmed(cli):
    cli.answers = ["no"]

    exit_code = main(
        ["add", "mail", "--name", "Gmail", "--origin", "https://mail.google.com"], cli.context()
    )

    assert exit_code == 1
    assert cli.output[0].startswith("WARNING: this looks like an excluded kind of account (email)")
    assert cli.secret_prompts == []


def test_add_username_flag_skips_the_username_prompt(cli):
    cli.secrets = ["Forum-Pa55!", "Forum-Pa55!"]

    assert main(ADD_ARGS + ["--username", "forum-user"], cli.context()) == 0

    assert len(cli.secret_prompts) == 2
    assert all("Username" not in prompt for prompt in cli.secret_prompts)
    assert load_vault(cli.store_path).find("forum").meta.username_hint == "f***"


def test_add_refuses_password_flag_without_echoing_or_reaching_argparse(cli, capsys, monkeypatch):
    def fail_parser():
        raise AssertionError("argparse reached")

    monkeypatch.setattr(sys.modules["vault.cli.main"], "build_parser", fail_parser)
    for flag in (
        ["--password", "S3cret!"],
        ["--password=S3cret!"],
        ["-p", "S3cret!"],
        ["--pw=S3cret!"],
    ):
        assert main(ADD_ARGS + flag, cli.context()) == EXIT_USER_ERROR
        captured = capsys.readouterr()
        assert "S3cret!" not in captured.out + captured.err
        assert "never accepted on the command line" in captured.err


def test_add_normalizes_a_full_url_origin(cli):
    cli.secrets = ["u", "u", "Pa55!", "Pa55!"]
    # Not a CAS host: "cas" now trips the SSO warning (exclusions.py).
    args = ["add", "portal", "--name", "Portal", "--origin", "https://portal.example.test/a/b?x=1"]

    assert main(args, cli.context()) == 0

    assert cli.output[0] == "using origin https://portal.example.test"
    origins = load_vault(cli.store_path).find("portal").meta.origins
    assert origins == ("https://portal.example.test",)


@pytest.mark.parametrize(
    "flag",
    ["--passwd", "--passw", "--pa", "--p", "--pwd", "--PASSWORD", "-P", "-pS3cret!", "/password"],
)
def test_add_never_echoes_a_password_like_option(cli, capsys, flag):
    args = ADD_ARGS + ([flag + "=S3cret!"] if flag.startswith("--") else [flag, "S3cret!"])
    with contextlib.suppress(SystemExit):
        assert main(args, cli.context()) == EXIT_USER_ERROR
    captured = capsys.readouterr()
    assert "S3cret!" not in captured.out + captured.err


def test_unknown_option_error_does_not_echo_values(cli, capsys):
    with pytest.raises(SystemExit):
        main(ADD_ARGS + ["--bogus", "S3cret!"], cli.context())
    captured = capsys.readouterr()
    assert "S3cret!" not in captured.out + captured.err
