"""End-to-end fill_login_with tests in headless Edge: origins, frames, fields, confirm, races."""

import json
import sys

import pytest

from vault.fill import fill_login_with, safe_fill
from vault.models import FillResult
from vault.unlock import UnlockError

LOGIN_URL = "https://login.example.test/"
EVIL_URL = "https://evil.example.test/"


async def _field_values(frame) -> tuple[str, str]:
    return await frame.eval_on_selector("#user", "e => e.value"), await frame.eval_on_selector(
        "#pass", "e => e.value"
    )


def _audit_lines(env) -> list[dict]:
    return [json.loads(line) for line in env.audit_path.read_text(encoding="utf-8").splitlines()]


@pytest.mark.asyncio
async def test_fills_on_a_registered_origin(page, serve, fill_env):
    await serve({LOGIN_URL: fill_env.login_form})
    await page.goto(LOGIN_URL)

    result = await fill_login_with(fill_env.deps, page, fill_env.credential_id)

    assert result == FillResult(True, "filled")
    assert await _field_values(page.main_frame) == (fill_env.username, fill_env.password)
    assert fill_env.confirmer.requests[0].top_origin == "https://login.example.test"
    assert fill_env.signer.sign_calls == 1
    assert _audit_lines(fill_env)[-1]["result"] == "filled"


@pytest.mark.asyncio
async def test_refuses_an_unregistered_top_level_origin(page, serve, fill_env):
    await serve({EVIL_URL: fill_env.login_form})
    await page.goto(EVIL_URL)

    result = await fill_login_with(fill_env.deps, page, fill_env.credential_id)

    assert result == FillResult(False, "origin_mismatch")
    assert await _field_values(page.main_frame) == ("", "")
    assert fill_env.confirmer.requests == []
    assert fill_env.signer.sign_calls == 0


FRAME_INJECTIONS = {
    "about:blank": """<iframe id="f"></iframe><script>
        document.getElementById('f').contentDocument.body.innerHTML = '<input type=password>';
        </script>""",
    "srcdoc": '<iframe srcdoc="<input type=password>"></iframe>',
    "data:": '<iframe src="data:text/html,<input type=password>"></iframe>',
    "blob:": """<script>
        const blob = new Blob(['<input type=password>'], {type: 'text/html'});
        const frame = document.createElement('iframe');
        frame.src = URL.createObjectURL(blob);
        document.body.appendChild(frame);
        </script>""",
}


@pytest.mark.asyncio
@pytest.mark.parametrize("frame_kind", sorted(FRAME_INJECTIONS))
async def test_refuses_password_fields_in_opaque_frames(page, serve, fill_env, frame_kind):
    await serve({LOGIN_URL: f"<body>{FRAME_INJECTIONS[frame_kind]}</body>"})
    await page.goto(LOGIN_URL)
    await page.wait_for_function("() => window.frames.length === 1")
    await page.frames[1].wait_for_selector("input[type=password]")

    result = await fill_login_with(fill_env.deps, page, fill_env.credential_id)

    assert result == FillResult(False, "origin_mismatch")
    assert fill_env.signer.sign_calls == 0


@pytest.mark.asyncio
async def test_fills_a_cross_origin_iframe_on_another_registered_origin(page, serve, fill_env):
    await serve(
        {
            LOGIN_URL: '<iframe src="https://auth.example.test/form"></iframe>',
            "https://auth.example.test/form": fill_env.login_form,
        }
    )
    await page.goto(LOGIN_URL)
    await page.frames[1].wait_for_selector("#pass")

    result = await fill_login_with(fill_env.deps, page, fill_env.credential_id)

    assert result == FillResult(True, "filled")
    assert fill_env.confirmer.requests[0].frame_origin == "https://auth.example.test"
    assert await _field_values(page.frames[1]) == (fill_env.username, fill_env.password)


@pytest.mark.asyncio
async def test_refuses_an_iframe_on_an_unregistered_origin(page, serve, fill_env):
    await serve(
        {
            LOGIN_URL: f'<iframe src="{EVIL_URL}form"></iframe>',
            f"{EVIL_URL}form": fill_env.login_form,
        }
    )
    await page.goto(LOGIN_URL)
    await page.frames[1].wait_for_selector("#pass")

    result = await fill_login_with(fill_env.deps, page, fill_env.credential_id)

    assert result == FillResult(False, "origin_mismatch")


@pytest.mark.asyncio
async def test_refuses_more_than_one_visible_password_field(page, serve, fill_env):
    await serve({LOGIN_URL: fill_env.login_form + '<input type="password" id="second">'})
    await page.goto(LOGIN_URL)

    assert await fill_login_with(fill_env.deps, page, fill_env.credential_id) == FillResult(
        False, "no_fields"
    )
    assert fill_env.confirmer.requests == []


@pytest.mark.asyncio
async def test_ignores_a_hidden_second_password_field(page, serve, fill_env):
    await serve({LOGIN_URL: fill_env.login_form + '<input type="password" style="display:none">'})
    await page.goto(LOGIN_URL)

    assert await fill_login_with(fill_env.deps, page, fill_env.credential_id) == FillResult(
        True, "filled"
    )


@pytest.mark.asyncio
async def test_refuses_a_new_password_field(page, serve, fill_env):
    await serve({LOGIN_URL: '<input id="pass" type="password" autocomplete="new-password">'})
    await page.goto(LOGIN_URL)

    assert await fill_login_with(fill_env.deps, page, fill_env.credential_id) == FillResult(
        False, "no_fields"
    )


@pytest.mark.asyncio
async def test_denied_confirmation_fills_nothing_and_never_unlocks(page, serve, fill_env):
    await serve({LOGIN_URL: fill_env.login_form})
    await page.goto(LOGIN_URL)
    fill_env.confirmer.answer = False

    assert await fill_login_with(fill_env.deps, page, fill_env.credential_id) == FillResult(
        False, "denied"
    )
    assert fill_env.signer.sign_calls == 0
    assert await _field_values(page.main_frame) == ("", "")


@pytest.mark.asyncio
async def test_unlock_failure_is_reported_as_locked(page, serve, fill_env):
    await serve({LOGIN_URL: fill_env.login_form})
    await page.goto(LOGIN_URL)
    fill_env.signer.fail_with = UnlockError("Windows Hello was cancelled")

    assert await fill_login_with(fill_env.deps, page, fill_env.credential_id) == FillResult(
        False, "locked"
    )


@pytest.mark.asyncio
async def test_navigation_to_another_origin_during_confirmation_fills_nothing(
    page, serve, fill_env
):
    await serve({LOGIN_URL: fill_env.login_form, EVIL_URL: fill_env.login_form})
    await page.goto(LOGIN_URL)

    async def navigate_away() -> None:
        await page.goto(EVIL_URL)

    fill_env.confirmer.before_answer = navigate_away
    result = await fill_login_with(fill_env.deps, page, fill_env.credential_id)

    assert not result.ok
    assert page.url == EVIL_URL
    assert await _field_values(page.main_frame) == ("", "")


@pytest.mark.asyncio
async def test_same_origin_navigation_during_confirmation_does_not_fill_the_new_page(
    page, serve, fill_env
):
    second_url = f"{LOGIN_URL}second"
    await serve({LOGIN_URL: fill_env.login_form, second_url: fill_env.login_form})
    await page.goto(LOGIN_URL)

    async def navigate_same_origin() -> None:
        await page.goto(second_url)

    fill_env.confirmer.before_answer = navigate_same_origin
    result = await fill_login_with(fill_env.deps, page, fill_env.credential_id)

    # The ElementHandle belonged to the old document, so the fill fails instead of
    # landing on the new page (a Locator would have re-resolved there).
    assert not result.ok
    assert await _field_values(page.main_frame) == ("", "")


@pytest.mark.asyncio
async def test_a_failing_fill_leaks_nothing(page, serve, fill_env, monkeypatch, caplog, capsys):
    await serve({LOGIN_URL: '<input id="user"><input id="pass" type="password" readonly>'})
    await page.goto(LOGIN_URL)
    # A readonly field makes Playwright time out, and its timeout error quotes fill("<value>").
    monkeypatch.setattr(safe_fill, "FILL_TIMEOUT_MS", 300)

    result = await fill_login_with(fill_env.deps, page, fill_env.credential_id)

    assert result == FillResult(False, "error")
    assert sys.exc_info() == (None, None, None)
    captured = capsys.readouterr()
    for place in (
        repr(result),
        fill_env.audit_path.read_text(encoding="utf-8"),
        caplog.text,
        captured.out,
        captured.err,
    ):
        assert fill_env.password not in place
        assert fill_env.username not in place


@pytest.mark.asyncio
async def test_submit_presses_enter_after_filling(page, serve, fill_env):
    await serve({LOGIN_URL: fill_env.login_form})
    await page.goto(LOGIN_URL)

    async with page.expect_navigation():
        result = await fill_login_with(fill_env.deps, page, fill_env.credential_id, submit=True)

    assert result == FillResult(True, "filled")
    assert page.url == f"{LOGIN_URL}done"


@pytest.mark.asyncio
async def test_playwright_debug_logging_blocks_filling(page, serve, fill_env, monkeypatch):
    await serve({LOGIN_URL: fill_env.login_form})
    await page.goto(LOGIN_URL)
    monkeypatch.setenv("DEBUG", "pw:api")

    result = await fill_login_with(fill_env.deps, page, fill_env.credential_id)

    assert result == FillResult(False, "unsafe_environment")
    assert fill_env.confirmer.requests == []


@pytest.mark.asyncio
async def test_origins_added_by_editing_the_store_break_decryption(page, serve, fill_env):
    document = json.loads(fill_env.store_path.read_text(encoding="utf-8"))
    document["credentials"][0]["origins"].append(EVIL_URL.rstrip("/"))
    fill_env.store_path.write_text(json.dumps(document), encoding="utf-8")
    await serve({EVIL_URL: fill_env.login_form})
    await page.goto(EVIL_URL)

    result = await fill_login_with(fill_env.deps, page, fill_env.credential_id)

    # The edited metadata passes the first check, but the AAD no longer verifies.
    assert result == FillResult(False, "tampered")
    assert await _field_values(page.main_frame) == ("", "")
