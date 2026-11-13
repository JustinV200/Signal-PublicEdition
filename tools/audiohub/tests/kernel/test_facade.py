"""Tests for the Kernel facade: batching, hold/re-check, fallback and thread-safe submit."""

import asyncio
import threading

import pytest

from audiohub.kernel import Decision, Dispatcher, Kernel, create_message

pytestmark = pytest.mark.asyncio


@pytest.fixture
def kernel(kernel_settings, fake_backend) -> Kernel:
    return Kernel(kernel_settings, Dispatcher(kernel_settings, backend=fake_backend))


class HoldOnceDispatcher:
    """Holds everything on its first decision, then delivers (the Sonnet one never holds)."""

    def __init__(self) -> None:
        self.calls = 0

    async def decide(self, pending, recent_delivered) -> list[Decision]:
        self.calls += 1
        action = "hold" if self.calls == 1 else "deliver"
        return [Decision(m.id, action, None, "test") for m in pending]


@pytest.fixture
def holding_kernel(kernel_settings) -> Kernel:
    return Kernel(kernel_settings, HoldOnceDispatcher())


async def test_batch_follows_decisions_and_uses_condensed_text(
    kernel, fake_backend, make_message, entry
) -> None:
    long_log = " ".join(f"line {i} ok" for i in range(40))
    for message in (make_message("m1", text=long_log), make_message("m2"), make_message("m3")):
        kernel.submit(message)
    fake_backend.respond(
        entry("m2", "deliver"),
        entry("m1", "deliver", "Deploy done."),
        entry("m3", "drop", reason="dup of m2"),
    )
    batch = await kernel.next_batch()
    assert [(m.id, text) for m, text in batch] == [("m1", "Deploy done."), ("m2", "hello there")]
    assert kernel.pending_count == 0


async def test_delivered_messages_feed_the_next_request_history(
    kernel, fake_backend, make_message
) -> None:
    kernel.submit(make_message("m1"))
    await kernel.next_batch()
    kernel.submit(make_message("m2"))
    await kernel.next_batch()
    history = fake_backend.last_request()["recently_delivered"]
    assert [h["id"] for h in history] == ["m1"]


async def test_held_message_is_rechecked_and_delivered_later(holding_kernel, make_message) -> None:
    kernel = holding_kernel
    kernel.submit(make_message("m1"))
    assert await kernel.next_batch() == []
    assert kernel.pending_count == 1
    # Nothing new arrives, but hold_recheck_s (0.05 s) wakes the waiter.
    assert await kernel.wait_for_work(timeout_s=2.0) is True
    batch = await kernel.next_batch()
    assert [m.id for m, _ in batch] == ["m1"]


async def test_wait_for_work_wakes_on_submit(kernel, make_message) -> None:
    waiter = asyncio.create_task(kernel.wait_for_work(timeout_s=2.0))
    await asyncio.sleep(0.01)
    kernel.submit(make_message("m1"))
    assert await waiter is True


async def test_fallback_still_delivers_everything(kernel, fake_backend, make_message) -> None:
    fake_backend.delay_s = 5.0
    kernel.submit(make_message("m1", "low"))
    kernel.submit(make_message("m2", "urgent"))
    batch = await kernel.next_batch()
    assert [m.id for m, _ in batch] == ["m2", "m1"]


async def test_submit_from_many_threads_loses_nothing(kernel) -> None:
    threads_count, per_thread = 8, 25

    def produce(worker: int) -> None:
        for n in range(per_thread):
            kernel.submit(create_message(f"worker-{worker}", f"note {n}"))

    await kernel.wait_for_work(timeout_s=0)  # binds the kernel to this loop
    workers = [threading.Thread(target=produce, args=(w,)) for w in range(threads_count)]
    for worker in workers:
        worker.start()
    assert await kernel.wait_for_work(timeout_s=2.0) is True
    await asyncio.to_thread(lambda: [w.join() for w in workers])
    batch = await kernel.next_batch()
    ids = [m.id for m, _ in batch]
    assert len(ids) == len(set(ids)) == threads_count * per_thread


async def test_submit_before_loop_is_bound_is_picked_up(kernel, make_message) -> None:
    kernel.submit(make_message("m1"))
    assert await kernel.wait_for_work(timeout_s=0.5) is True


async def test_start_survives_a_dispatcher_that_cannot_connect(
    kernel_settings, fake_backend, caplog
) -> None:
    class BrokenDispatcher(Dispatcher):
        async def start(self) -> None:
            raise ConnectionError("no auth")

    kernel = Kernel(kernel_settings, BrokenDispatcher(kernel_settings, backend=fake_backend))
    await kernel.start()
    assert "failed to start" in caplog.text


async def test_drain_pending_returns_held_and_unprocessed_messages(
    holding_kernel, make_message
) -> None:
    kernel = holding_kernel
    kernel.submit(make_message("m1"))
    await kernel.next_batch()
    kernel.submit(make_message("m2"))
    assert [m.id for m in kernel.drain_pending()] == ["m1", "m2"]
    assert kernel.pending_count == 0


async def test_close_warns_about_undelivered_messages(kernel, make_message, caplog) -> None:
    kernel.submit(make_message("m1"))
    kernel.submit(make_message("m2"))
    await kernel.close()
    assert "2 undelivered message(s): m1, m2" in caplog.text


async def test_fast_pathed_reply_enters_history_for_later_decisions(
    kernel, fake_backend, make_message
) -> None:
    kernel.submit(make_message("m1", "high", "It is 3 pm.", is_direct_reply=True))
    assert [(m.id, text) for m, text in await kernel.next_batch()] == [("m1", "It is 3 pm.")]
    assert fake_backend.prompts == []
    kernel.submit(make_message("m2"))
    kernel.submit(make_message("m3"))
    await kernel.next_batch()
    assert [h["id"] for h in fake_backend.last_request()["recently_delivered"]] == ["m1"]


async def test_requeued_message_is_pending_again_and_not_a_repeat(
    kernel, fake_backend, make_message
) -> None:
    # Regression: a notification cut off by "stop" was marked delivered and lost.
    kernel.submit(make_message("m1", text="Build finished."))
    [(cut, _)] = await kernel.next_batch()
    kernel.submit(make_message("m2", text="Deploy started."))
    kernel.requeue([cut])
    batch = await kernel.next_batch()
    assert [m.id for m, _ in batch] == ["m1", "m2"]
    assert fake_backend.last_request()["recently_delivered"] == []
