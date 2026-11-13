"""The docker backend: each job is one throwaway container running Edge, driven over CDP.

A job starts on the first tool call that needs the browser (so registering the
browser-docker server never touches Docker) and ends when the server exits,
after [browser] idle_close_min without a tool call (the server's IdleClose),
when the host gets a new IPv4 address (is_job_stale), or when its browser
goes away. The next tool call starts a fresh job with a new id and token.
Before each job: `docker info` (Docker Desktop must be running), the image must
exist, and its Edge must be current (edge_version). Every safety control in
the tool runs here on the host, on the context this returns. See
refdocs/research/docker-browser.md.
"""

import asyncio
import logging
import secrets
from dataclasses import dataclass
from pathlib import Path

from playwright.async_api import BrowserContext, Playwright

from browser_tool.backends import docker_box
from browser_tool.backends.edge_version import REBUILD_COMMAND, EdgeVersionCheck
from browser_tool.backends.host_addresses import HostAddresses, block_cidrs
from browser_tool.backends.remote_cdp import connect_context
from browser_tool.backends.types import BackendError
from browser_tool.config import Settings, resolve_tool_path
from browser_tool.policy import GuestBlock, HostPolicy, build_host_resolver_rules

logger = logging.getLogger(__name__)

IMAGE = "signal-browser:latest"
# Relative to tools/browser. Absolute on the command line: docker reads it from its own cwd.
SECCOMP_FILE = "docker/seccomp.json"
JOB_ID_BYTES = 3
TOKEN_BYTES = 32
SECONDS_PER_MINUTE = 60
JOB_LABEL_PREFIX = "docker job"
IMAGE_MISSING = f"the browser image {IMAGE} isn't built. Ask the owner to run: {REBUILD_COMMAND}"


@dataclass(frozen=True)
class _OpenJob:
    """The running job and the host addresses its firewall was started with."""

    job: docker_box.Job
    host_ips: frozenset[str]


class DockerBackend:
    """Runs each browser job in its own container (refdocs/research/docker-browser.md section 2)."""

    # Docker jobs deny every download over CDP (remote_cdp), whatever [downloads] says.
    downloads_incoming: Path | None = None

    def __init__(self, settings: Settings, addresses: HostAddresses | None = None):
        """Create an idle backend; nothing touches Docker until open_context.

        Args:
            settings: Read for [browser] idle_close_min.
            addresses: The host's addresses (default: looked up live).
        """
        self._addresses = addresses or HostAddresses()
        # Read once now, so the first navigate's policy check already knows them.
        self._addresses.refresh()
        self.guest_block: GuestBlock | None = GuestBlock(self._addresses.seen)
        self.idle_close_s: float | None = settings.browser.idle_close_min * SECONDS_PER_MINUTE
        self._seccomp_path = resolve_tool_path(SECCOMP_FILE)
        self._edge_check = EdgeVersionCheck(docker_box.image_edge_version)
        self._open: _OpenJob | None = None

    @property
    def job_label(self) -> str | None:
        """ "docker job <id>" while a job is open, else None."""
        return f"{JOB_LABEL_PREFIX} {self._open.job.job_id}" if self._open else None

    async def open_context(self, playwright: Playwright, policy: HostPolicy) -> BrowserContext:
        """Start a job's container, wait for its relay, and connect to its Edge.

        Raises:
            BackendError: Docker isn't running, the image is missing or stale, or
                the container didn't start.
            playwright.async_api.Error: If connecting fails.
        """
        await asyncio.to_thread(self._check_image)
        host_ips = await asyncio.to_thread(self._addresses.refresh)
        spec = docker_box.JobSpec(
            job_id=secrets.token_hex(JOB_ID_BYTES),
            token=secrets.token_urlsafe(TOKEN_BYTES),
            block_cidrs=block_cidrs(host_ips),
            # After the refresh, so Edge's resolver rules hold the same host IPs.
            resolver_rules=build_host_resolver_rules(policy) or "",
        )
        job = await asyncio.to_thread(docker_box.start_job, spec, IMAGE, self._seccomp_path)
        self._open = _OpenJob(job, host_ips)
        logger.info("started %s", self.job_label)
        try:
            await asyncio.to_thread(docker_box.wait_ready, job)
            return await connect_context(playwright, job.endpoint, job.auth_headers)
        except BaseException:
            self.close()
            raise

    async def is_job_stale(self) -> bool:
        """True when the host has an address the open job's firewall doesn't block."""
        if self._open is None:
            return False
        seen = await asyncio.to_thread(self._addresses.refresh)
        if seen <= self._open.host_ips:
            return False
        logger.info("the host has a new IPv4 address; ending %s", self.job_label)
        return True

    def close(self) -> None:
        """Start `docker rm -f` for the open job, without waiting. A second call does nothing."""
        open_job, self._open = self._open, None
        if open_job is not None:
            logger.info("ending docker job %s", open_job.job.job_id)
            docker_box.remove_job_async(open_job.job.name)

    def _check_image(self) -> None:
        """The lazy start checks: Docker answers, the image exists and its Edge is current."""
        docker_box.ensure_docker_running()
        image_id = docker_box.image_id(IMAGE)
        if image_id is None:
            raise BackendError(IMAGE_MISSING)
        self._edge_check.ensure_current(IMAGE, image_id)
