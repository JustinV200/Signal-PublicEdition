"""End to end on a real container (marker `docker`: needs Docker Desktop, the image and internet).

Run with `pytest -m docker`. One job goes through the real tool: it browses a
public page, its iptables refuses the host and private ranges from inside the
guest, and closing the session removes the container. Then a bad block list
must stop a container before its relay comes up.
"""

import json
import secrets
import subprocess
import time

import pytest
from support.browser_helpers import headless_settings
from support.fakes import FakeConfirmer

from browser_tool import actions
from browser_tool.backends import IMAGE, JobSpec, run_arguments, run_docker
from browser_tool.backends.docker_box import CONTAINER_PREFIX, job_environment
from browser_tool.backends.host_addresses import lookup_host_ipv4s
from browser_tool.config import resolve_tool_path
from browser_tool.server import BACKEND_DOCKER, build_context

pytestmark = pytest.mark.docker

CONNECT_SCRIPT = resolve_tool_path("docker/probes/guest_connect.py").read_text("utf-8")
BLOCKED = ["host.docker.internal:8770", "10.0.0.1:80", "100.64.0.1:80", "169.254.169.254:80"]
OPEN = ["example.com:443"]
# The close hook's `docker rm -f` runs in the background.
GONE_TIMEOUT_S = 20.0


def guest_connects(container: str, targets: list[str]) -> dict[str, str]:
    """TCP connects from inside the container, as user edge: target -> result."""
    command = ["docker", "exec", "-i", "-u", "edge", container, "python3", "-I", "-", *targets]
    result = subprocess.run(command, input=CONNECT_SCRIPT, capture_output=True, text=True)
    rows = [json.loads(line) for line in result.stdout.splitlines()]
    return {row["target"]: row["result"] for row in rows}


def is_gone(container: str) -> bool:
    """Poll until no container has this name, for up to GONE_TIMEOUT_S."""
    deadline = time.monotonic() + GONE_TIMEOUT_S
    while time.monotonic() < deadline:
        listed = run_docker("ps", "-a", "--filter", f"name=^{container}$", "--format", "{{.Names}}")
        if container not in listed.stdout.split():
            return True
        time.sleep(0.5)
    return False


@pytest.mark.asyncio
async def test_docker_job_end_to_end(tmp_path):
    ctx = build_context(
        BACKEND_DOCKER, headless_settings(tmp_path, allow_all=True), FakeConfirmer()
    )
    try:
        assert (await actions.navigate(ctx, "https://example.com/")).startswith("navigated")
        container = CONTAINER_PREFIX + ctx.session.job_label.split()[-1]
        host_targets = [f"{address}:1234" for address in lookup_host_ipv4s()]
        results = guest_connects(container, [*BLOCKED, *host_targets, *OPEN])
    finally:
        await ctx.session.close()
    assert {results[target] for target in [*BLOCKED, *host_targets]} == {"refused"}
    assert results["example.com:443"] == "connected"
    assert is_gone(container)

    # A CIDR with host bits set must end the container before the relay starts.
    spec = JobSpec(secrets.token_hex(3), secrets.token_urlsafe(32), "10.0.0.1/8", "")
    seccomp = resolve_tool_path("docker/seccomp.json")
    run = run_docker("run", *run_arguments(spec, IMAGE, seccomp), env=job_environment(spec))
    assert run.returncode != 0
    assert "relay listening" not in run.stdout + run.stderr
