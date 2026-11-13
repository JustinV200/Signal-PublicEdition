"""Run the phase 0 spike end to end and print one PASS/FAIL line per check.

Usage (from the repo root, with the image built):
    uv run --project tools/browser --frozen --no-sync python tools/browser/docker/probes/spike.py

Starts throwaway containers from signal-browser:latest, runs the checks
for the docker backend (refdocs/research/docker-browser.md) plus the relay and
exposure checks, and removes every container it started. Never touches the
desktop browser or its profile.
"""

import asyncio
import ipaddress
import subprocess
import time

import check_edge_safety as edge_safety
import check_guest as guest
import check_playwright as pw_checks
import check_relay as relay
import docker_job
from playwright.async_api import async_playwright
from results import Result, guarded, print_report

from browser_tool.redaction import register_sensitive_engine

RESOLVER_RULES = "MAP example.net ~NOTFOUND"
CLOSE_EVENT_TIMEOUT_S = 15.0
GONE_TIMEOUT_S = 15.0


def check_host_addresses() -> Result:
    """14: the getaddrinfo list covers every non-loopback address Get-NetIPAddress shows."""
    listed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "(Get-NetIPAddress -AddressFamily IPv4).IPAddress",
        ],
        capture_output=True,
        text=True,
        check=True,
        creationflags=docker_job.NO_WINDOW,
    ).stdout.split()
    ours = docker_job.host_ipv4s()
    missing = sorted(set(listed) - set(ours) - {"127.0.0.1"})
    fixed = [ipaddress.ip_network(cidr) for cidr in docker_job.BLOCKED_GUEST_CIDRS]
    uncovered = [ip for ip in missing if not any(ipaddress.ip_address(ip) in net for net in fixed)]
    detail = f"getaddrinfo {ours}; missing {missing}, of which outside the fixed ranges {uncovered}"
    return Result("14 getaddrinfo vs Get-NetIPAddress", not uncovered, detail)


async def browser_checks(job: docker_job.Job, processes: list[dict[str, str]]) -> list[Result]:
    """Everything that drives Edge over connect_over_cdp, ending with the close hook (8)."""
    async with async_playwright() as playwright:
        await pw_checks.register_early_engine(playwright)
        browser = await playwright.chromium.connect_over_cdp(job.endpoint, headers=job.auth_headers)
        # After connecting, so the engine reaches the default context (check 2).
        await register_sensitive_engine(playwright)
        context = browser.contexts[0]
        results = [pw_checks.check_about_blank(browser)]
        page = context.pages[0]
        await edge_safety.harden(browser, context)
        checks = {
            "policy path": edge_safety.check_policies(page),
            "10 edge://sandbox": edge_safety.check_sandbox_page(page),
            "1 routing": pw_checks.check_routing(context),
            "2 selector engine": pw_checks.check_selector_engine(page),
            "3 aria refs": pw_checks.check_aria_refs(page),
            "4 handles and frames": pw_checks.check_handles_and_frames(page),
            "5 masked screenshot": pw_checks.check_masked_screenshot(page),
            "6 frame and popup events": pw_checks.check_frame_and_popup_events(context, page),
            "service worker blocker": edge_safety.check_service_worker_blocked(page),
            "11 firewall from Edge": edge_safety.check_edge_firewall(
                context, docker_job.host_ipv4s()
            ),
            "resolver rules": edge_safety.check_resolver_rules(context),
            # Last before the logs: it removes the policy file from this container.
            "7 downloads": edge_safety.check_downloads(browser, job, page),
        }
        # Coroutines are awaited one at a time, in this order, on the same tab.
        for name, coroutine in checks.items():
            results.append(await guarded(name, coroutine))
        # The logs go with the container, so read them before the close hook removes it.
        results += [relay.check_relay_log(job), guest.check_edge_stderr(job)]
        results.append(await guarded("8 close hook", check_close_hook(job, context, processes)))
    return results


async def check_close_hook(job: docker_job.Job, context, processes: list[dict[str, str]]) -> Result:
    """8: kill Edge (a crash); context 'close' fires and the hook's docker rm -f leaves nothing."""
    closed = asyncio.Event()
    removals = []

    def on_close(_context) -> None:
        # The real handler is synchronous too, so it only starts the removal.
        removals.append(docker_job.remove_job_async(job.name))
        closed.set()

    context.on("close", on_close)
    edge = next(p for p in processes if p["Name"] == "msedge" and "--type=" not in p["cmd"])
    docker_job.docker("exec", "-u", "edge", job.name, "kill", "-9", edge["pid"])
    try:
        await asyncio.wait_for(closed.wait(), CLOSE_EVENT_TIMEOUT_S)
    except TimeoutError:
        return Result("8 close event + docker rm -f", False, "no close event after Edge was killed")
    started = time.monotonic()
    while docker_job.is_running(job.name) and time.monotonic() - started < GONE_TIMEOUT_S:
        await asyncio.sleep(0.5)
    gone = not docker_job.is_running(job.name)
    return Result(
        "8 close event + docker rm -f",
        gone,
        f"close fired, hook ran {len(removals)}x, container gone {gone}",
    )


def main_job_checks() -> list[Result]:
    """Start the main container and run the relay, guest and browser checks on it."""
    job = docker_job.start_job("main", resolver_rules=RESOLVER_RULES)
    try:
        ready_s = docker_job.wait_ready(job)
        results = [Result("authenticated readiness poll", True, f"200 after {ready_s:.1f} s")]
        results += [
            relay.check_rejections(job),
            relay.check_token_accepted(job),
            relay.check_exposure(job),
        ]
        host_ips = docker_job.host_ipv4s()
        results += [
            guest.check_firewall(job, host_ips),
            guest.check_rules(job),
            guest.check_ipv6(job),
        ]
        process_result, processes = guest.check_processes(job)
        results += [
            process_result,
            guest.check_dumpable(job, processes),
            guest.check_listeners(job),
        ]
        return [*results, *asyncio.run(browser_checks(job, processes))]
    finally:
        docker_job.docker("rm", "-f", job.name, check=False)


def main() -> None:
    """Run every check and print the report."""
    public_ips = [ip for ip in docker_job.host_ipv4s() if ipaddress.ip_address(ip).is_global]
    print(f"host IPv4 {docker_job.host_ipv4s()}, public {public_ips}")
    results = [
        check_host_addresses(),
        relay.check_bare_connect_without_listener(),
        guest.check_bad_block_lists(),
    ]
    results += main_job_checks()
    results.append(relay.check_idle_exit_after_kill())
    print_report(results)


if __name__ == "__main__":
    main()
