"""DockerBackend.is_job_stale with a fake address lookup and open job (no Docker)."""

from types import SimpleNamespace

import pytest
from support.browser_helpers import headless_settings

from browser_tool.backends.docker_backend import DockerBackend, _OpenJob
from browser_tool.backends.host_addresses import HostAddresses


@pytest.mark.asyncio
async def test_a_new_host_address_makes_the_open_job_stale(tmp_path):
    addresses = ["192.168.1.5"]
    backend = DockerBackend(headless_settings(tmp_path), HostAddresses(lambda: addresses))
    assert not await backend.is_job_stale()  # no job open

    # A job whose firewall was started blocking .5.
    backend._open = _OpenJob(SimpleNamespace(job_id="abc123"), frozenset(addresses))
    assert not await backend.is_job_stale()

    addresses = ["10.20.0.9"]  # the PC moved networks; the job's firewall doesn't block it
    assert await backend.is_job_stale()
