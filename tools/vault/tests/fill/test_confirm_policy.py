"""policy.confirm: only exactly "never" skips the Allow/Deny dialog; anything else asks."""

import dataclasses
import json

import pytest

from vault.fill import fill_login_with
from vault.models import FillResult
from vault.store import (
    load_vault,
    rotate_records,
    save_vault,
)
from vault.unlock.hello import HelloUnlocker

LOGIN_URL = "https://login.example.test/"


async def _set_policy(env, policy: dict[str, str]) -> None:
    """Re-seal the one credential with `policy` (it is AAD-bound, so a file edit won't do)."""
    data = load_vault(env.store_path)

    def edit(meta):
        return dataclasses.replace(meta, policy=policy)

    save_vault(
        env.store_path,
        await rotate_records(data, data.records, HelloUnlocker(env.signer), edit),
    )
    env.signer.sign_calls = 0


@pytest.mark.parametrize(
    ("policy", "asked", "audit_confirm"),
    [
        ({"confirm": "always"}, True, None),
        ({"confirm": "never"}, False, "auto"),
        ({"confirm": "sometimes"}, True, None),
        ({}, True, None),
    ],
)
@pytest.mark.asyncio
async def test_policy_decides_whether_the_dialog_shows(
    page, serve, fill_env, policy, asked, audit_confirm
):
    await _set_policy(fill_env, policy)
    await serve({LOGIN_URL: fill_env.login_form})
    await page.goto(LOGIN_URL)

    result = await fill_login_with(fill_env.deps, page, fill_env.credential_id)

    assert result == FillResult(True, "filled")
    assert bool(fill_env.confirmer.requests) is asked
    assert fill_env.signer.sign_calls == 1
    last = json.loads(fill_env.audit_path.read_text(encoding="utf-8").splitlines()[-1])
    assert last["result"] == "filled" and last.get("confirm") == audit_confirm


async def _fill(page, serve, env):
    await serve({LOGIN_URL: env.login_form})
    await page.goto(LOGIN_URL)
    return await fill_login_with(env.deps, page, env.credential_id)


@pytest.mark.asyncio
async def test_editing_the_policy_in_the_store_breaks_decryption(page, serve, fill_env):
    document = json.loads(fill_env.store_path.read_text(encoding="utf-8"))
    document["credentials"][0]["policy"] = {"confirm": "never"}
    fill_env.store_path.write_text(json.dumps(document), encoding="utf-8")

    assert await _fill(page, serve, fill_env) == FillResult(False, "tampered")
    assert fill_env.confirmer.requests == []
    assert await page.eval_on_selector("#pass", "e => e.value") == ""


@pytest.mark.asyncio
async def test_a_record_saved_while_never_cannot_be_pasted_back(page, serve, fill_env):
    await _set_policy(fill_env, {"confirm": "never"})
    old = json.loads(fill_env.store_path.read_text(encoding="utf-8"))["credentials"][0]
    # What `vault policy --confirm always` does: rotate the data key.
    data = load_vault(fill_env.store_path)

    def always(meta):
        return dataclasses.replace(meta, policy={"confirm": "always"})

    rotated = await rotate_records(data, data.records, HelloUnlocker(fill_env.signer), always)
    save_vault(fill_env.store_path, rotated)
    document = json.loads(fill_env.store_path.read_text(encoding="utf-8"))
    document["credentials"][0] = old
    fill_env.store_path.write_text(json.dumps(document), encoding="utf-8")

    assert await _fill(page, serve, fill_env) == FillResult(False, "tampered")
    assert fill_env.confirmer.requests == []
