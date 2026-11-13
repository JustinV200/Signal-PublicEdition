"""Tests for audiohub.stt.frames: frame constants and the frame shape check."""

import numpy as np
import pytest

from audiohub.stt.frames import FRAME_SAMPLES, validate_frame


def test_float32_frame_is_returned_without_copy() -> None:
    frame = np.zeros(FRAME_SAMPLES, dtype=np.float32)
    assert validate_frame(frame) is frame


def test_other_dtypes_are_converted_to_float32() -> None:
    result = validate_frame(np.zeros(FRAME_SAMPLES, dtype=np.float64))
    assert result.dtype == np.float32


@pytest.mark.parametrize("shape", [(480,), (2, FRAME_SAMPLES)])
def test_wrong_shapes_raise(shape: tuple) -> None:
    with pytest.raises(ValueError, match="512 samples"):
        validate_frame(np.zeros(shape, dtype=np.float32))
