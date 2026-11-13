"""Any debug logging setting blocks fills, because Playwright's wildcards log fill values."""

import pytest

from vault.fill.environment import playwright_debug_enabled


@pytest.mark.parametrize(
    "environ",
    [
        {"DEBUG": "*"},
        {"DEBUG": "pw*"},
        {"DEBUG": "pw:api"},
        {"DEBUG_FILE": "x.log"},
        {"PWDEBUG": "1"},
    ],
)
def test_any_debug_setting_is_unsafe(environ):
    assert playwright_debug_enabled(environ)


def test_clean_environment_is_safe():
    assert not playwright_debug_enabled({"DEBUG": "", "PATH": "x"})
