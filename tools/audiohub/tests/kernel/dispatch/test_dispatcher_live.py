"""Live smoke test: a realistic batch through the real Sonnet dispatcher.

Skipped unless AUDIOHUB_LIVE_TESTS=1 (it needs a Claude login and costs a
little). Run with -s to see the decisions and latency:
    AUDIOHUB_LIVE_TESTS=1 uv run pytest tests/kernel/dispatch/test_dispatcher_live.py -s
"""

import json
import os
import time

import pytest

from audiohub.config import KernelSettings
from audiohub.kernel import DeliveredRecord, Dispatcher, create_message

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(os.environ.get("AUDIOHUB_LIVE_TESTS") != "1", reason="live Sonnet test"),
]

DEPLOY_LOG = (
    "deploy-agent run 4182 for signal-web, target production, region us-east-1. "
    "10:01:58 preflight: disk 61 percent free on all hosts, config diff shows 2 changed "
    "keys, feature flag new-onboarding enabled for 10 percent of users. "
    "10:02:11 fetching artifact signal-web-2.3.7.tar.gz from the release bucket, 48.2 MB. "
    "10:02:14 checksum sha256 9f2c41ab77e0 verified. "
    "10:02:15 draining instance web-1, 37 open connections, waiting up to 30 seconds. "
    "10:02:41 web-1 drained, stopping service, unpacking release, running migrations 0042 "
    "and 0043, both applied in 1.8 seconds. 10:02:49 starting service on web-1, health "
    "check GET /healthz returned 200 after 3 attempts. 10:02:55 draining instance web-2, "
    "29 open connections. 10:03:20 web-2 drained, stopping service, unpacking release, "
    "migrations already applied, skipping. 10:03:27 starting service on web-2, health "
    "check returned 200 after 2 attempts. 10:03:31 draining instance web-3, 41 open "
    "connections. 10:03:58 web-3 drained, stopping service, unpacking release. 10:04:05 "
    "starting service on web-3, health check returned 503 twice, then 200 on attempt 4. "
    "10:04:19 warning: web-3 p95 latency 840 ms during warm-up, settled to 120 ms. "
    "10:04:30 updating load balancer target group, 3 of 3 targets healthy. 10:04:33 "
    "purging CDN cache for /static, 1,204 objects invalidated. 10:04:40 deploy complete, "
    "version 2.3.7 live, total time 2 minutes 29 seconds, 0 errors, 1 warning."
)


def smoke_batch() -> list:
    """The brief's batch: a direct reply, a result and its duplicate, a log dump, a question."""
    return [
        create_message("build-agent", "Tests passed: 214 of 214 in 38 seconds.", "normal"),
        create_message("deploy-agent", DEPLOY_LOG, "low"),
        create_message("build-agent", "Tests passed: 214 of 214 in 38 seconds.", "normal"),
        create_message(
            "claude",
            "Your next meeting is at 3 pm with Sam, about the Signal launch plan.",
            "high",
        ),
        create_message(
            "claude",
            "I'd like to run git push origin main to publish the release. Should I go ahead?",
            "urgent",
        ),
    ]


async def decide_and_show(dispatcher, pending, history, label) -> list:
    """Run one live decision, print its latency and decisions, and check nothing was lost."""
    started = time.perf_counter()
    decisions = await dispatcher.decide(pending, history, "idle")
    print(f"\n{label}: decision took {time.perf_counter() - started:.2f}s")
    by_id = {m.id: m for m in pending}
    for decision in decisions:
        row = {"source": by_id[decision.message_id].source, **decision.__dict__}
        print(json.dumps(row, ensure_ascii=False))
    assert {d.message_id for d in decisions} == set(by_id)
    assert not any(d.reason.startswith("fallback") for d in decisions), "Sonnet was not used"
    return decisions


async def test_realistic_batch_against_sonnet() -> None:
    """Round 1: the brief's batch while idle. Round 2: what was held, after the user answered."""
    dispatcher = Dispatcher(KernelSettings())
    started = time.perf_counter()
    await dispatcher.start()
    print(f"\nconnect + warm-up {time.perf_counter() - started:.2f}s")
    print("deploy log words:", len(DEPLOY_LOG.split()))
    batch = smoke_batch()
    try:
        first = await decide_and_show(dispatcher, batch, [], "round 1")
        by_id = {m.id: m for m in batch}
        history = [
            DeliveredRecord(by_id[d.message_id], d.text or by_id[d.message_id].text)
            for d in first
            if d.action == "deliver"
        ]
        held = [by_id[d.message_id] for d in first if d.action == "hold"]
        if held:
            await decide_and_show(dispatcher, held, history, "round 2")
    finally:
        await dispatcher.close()
