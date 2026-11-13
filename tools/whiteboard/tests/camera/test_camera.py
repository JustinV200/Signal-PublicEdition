"""Tests for Camera's grab thread with a fake capture device: read_fresh returns only a
frame produced after the call, and close() wakes a waiting read_fresh."""

import threading
import time

import numpy as np
import pytest

from whiteboard.camera import Camera, CameraError
from whiteboard.camera import camera as camera_module
from whiteboard.camera.device import OpenedCapture
from whiteboard.config import CameraSettings

FRAME_INTERVAL_S = 0.005
STALL_READ_S = 0.05


class FakeCapture:
    """A cv2.VideoCapture stand-in: numbered frames every few ms, until stalled."""

    def __init__(self) -> None:
        self.frame_number = 0
        self.is_stalled = False

    def read(self) -> tuple[bool, np.ndarray | None]:
        if self.is_stalled:
            time.sleep(STALL_READ_S)
            return False, None
        time.sleep(FRAME_INTERVAL_S)
        self.frame_number += 1
        return True, np.full((2, 2), self.frame_number, np.int64)

    def release(self) -> None:
        pass


@pytest.fixture
def fake_capture(monkeypatch: pytest.MonkeyPatch) -> FakeCapture:
    capture = FakeCapture()
    opened = OpenedCapture(capture, "fake", 2, 2, 200.0)  # type: ignore[arg-type]
    monkeypatch.setattr(camera_module, "open_capture", lambda *args: opened)
    return capture


def wait_for_first_frame(camera: Camera) -> np.ndarray:
    deadline = time.monotonic() + 2
    while (frame := camera.latest()) is None:
        assert time.monotonic() < deadline, "no frame from the fake capture"
        time.sleep(FRAME_INTERVAL_S)
    return frame


def test_read_fresh_returns_a_frame_from_after_the_call(fake_capture: FakeCapture) -> None:
    with Camera(CameraSettings()) as camera:
        wait_for_first_frame(camera)
        newest_before_call = camera.latest()
        assert newest_before_call is not None

        fresh = camera.read_fresh()

        assert fresh[0, 0] >= newest_before_call[0, 0] + camera_module.FRESH_FRAME_GAP


def test_close_wakes_a_waiting_read_fresh(fake_capture: FakeCapture) -> None:
    camera = Camera(CameraSettings())
    camera.open()
    wait_for_first_frame(camera)
    fake_capture.is_stalled = True
    errors: list[Exception] = []

    def wait_for_fresh_frame() -> None:
        try:
            camera.read_fresh(timeout_s=10)
        except CameraError as error:
            errors.append(error)

    waiter = threading.Thread(target=wait_for_fresh_frame)
    waiter.start()
    time.sleep(0.1)
    camera.close()
    waiter.join(timeout=2)

    assert not waiter.is_alive()
    assert len(errors) == 1 and "closed" in str(errors[0])
