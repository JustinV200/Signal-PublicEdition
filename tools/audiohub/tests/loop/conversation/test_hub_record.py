"""The hub's pid record: written only after the IPC bind, removed on exit only while it's ours."""

import json
import os
import socket

import pytest

from audiohub.loop import HubStartError

HOST = "127.0.0.1"
OTHER_HUB = {"pid": 4, "create_time": 1.0}


@pytest.mark.asyncio
async def test_a_hub_that_cant_bind_leaves_the_running_hubs_record_alone(make_hub, tmp_path):
    record_path = tmp_path / "hub.json"
    record_path.write_text(json.dumps(OTHER_HUB), encoding="utf-8")
    before = record_path.read_bytes()
    with socket.socket() as holder:
        holder.bind((HOST, 0))
        holder.listen()
        hub = make_hub(listen=False, port=holder.getsockname()[1], record_path=record_path)
        with pytest.raises(HubStartError):
            await hub.conversation.run()

    assert record_path.read_bytes() == before


@pytest.mark.parametrize("is_replaced", [False, True])
@pytest.mark.asyncio
async def test_exit_removes_the_record_only_while_it_names_this_hub(
    make_hub, tmp_path, is_replaced
):
    record_path = tmp_path / "hub.json"
    async with make_hub(listen=False, record_path=record_path):
        assert json.loads(record_path.read_text(encoding="utf-8"))["pid"] == os.getpid()
        if is_replaced:  # another hub started meanwhile and wrote its own
            record_path.write_text(json.dumps(OTHER_HUB), encoding="utf-8")

    assert record_path.exists() is is_replaced
