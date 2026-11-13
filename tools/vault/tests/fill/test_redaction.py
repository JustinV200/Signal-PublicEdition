"""The snapshot gate (has_filled_fields) and the text scrubber."""

import pytest

from vault.fill import REDACTION_MARK, FilledRegistry, fill_login_with, page_has_filled_fields
from vault.fill.redaction import scrub_text
from vault.secret import Secret

LOGIN_URL = "https://login.example.test/"
AFTER_URL = "https://login.example.test/after"


@pytest.mark.asyncio
async def test_gate_is_on_while_filled_fields_are_attached(page, serve, fill_env):
    await serve({LOGIN_URL: fill_env.login_form, AFTER_URL: "<p>welcome</p>"})
    await page.goto(LOGIN_URL)
    assert not await page_has_filled_fields(page, fill_env.registry)

    await fill_login_with(fill_env.deps, page, fill_env.credential_id)
    assert await page_has_filled_fields(page, fill_env.registry)

    await page.goto(AFTER_URL)
    assert not await page_has_filled_fields(page, fill_env.registry)


@pytest.mark.asyncio
async def test_gate_is_on_for_a_hand_typed_password(page, serve, fill_env):
    await serve({LOGIN_URL: fill_env.login_form})
    await page.goto(LOGIN_URL)

    await page.fill("#pass", "typed by hand")

    assert await page_has_filled_fields(page, FilledRegistry())


def test_scrub_removes_secrets_and_their_common_encodings():
    secret = Secret('p@ss "word"&<x>')
    text = 'raw p@ss "word"&<x> json p@ss \\"word\\"&<x> url p%40ss%20%22word%22%26%3Cx%3E'

    scrubbed = scrub_text(text, [secret])

    assert "p@ss" not in scrubbed and "p%40ss" not in scrubbed
    assert scrubbed.count(REDACTION_MARK) >= 3


@pytest.mark.asyncio
async def test_scrub_forgets_a_page_once_it_closes(page, serve, fill_env):
    await serve({LOGIN_URL: fill_env.login_form})
    await page.goto(LOGIN_URL)
    await fill_login_with(fill_env.deps, page, fill_env.credential_id)
    assert fill_env.password not in scrub_text(fill_env.password, fill_env.registry.secrets())

    await page.close()

    assert fill_env.registry.secrets() == []
