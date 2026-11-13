"""The Playwright debug-environment scrub, which runs before every backend."""

from browser_tool.session import DEBUG_ENV_VARS, clear_debug_env


def test_debug_variables_are_removed():
    environ = {"DEBUG": "pw:api", "PWDEBUG": "1", "PATH": "x"}
    assert sorted(clear_debug_env(environ)) == ["DEBUG", "PWDEBUG"]
    assert environ == {"PATH": "x"}
    assert "DEBUG_FILE" in DEBUG_ENV_VARS
