"""Tests for audiohub.audio.framing: re-cutting blocks into fixed-size frames."""

import numpy as np
import pytest

from audiohub.audio.framing import FrameChunker


def test_frames_have_exact_size_and_keep_sample_order():
    chunker = FrameChunker(4)
    frames = chunker.push(np.arange(6)) + chunker.push(np.arange(6, 10))
    assert [frame.tolist() for frame in frames] == [[0, 1, 2, 3], [4, 5, 6, 7]]
    assert all(frame.dtype == np.float32 for frame in frames)


def test_short_block_yields_nothing_until_a_frame_is_complete():
    chunker = FrameChunker(512)
    assert chunker.push(np.zeros(511)) == []
    assert len(chunker.push(np.zeros(1))) == 1


def test_clear_drops_the_partial_frame():
    chunker = FrameChunker(4)
    chunker.push(np.ones(3))
    chunker.clear()
    assert chunker.push(np.zeros(4))[0].tolist() == [0, 0, 0, 0]


def test_non_positive_frame_size_raises():
    with pytest.raises(ValueError, match="positive"):
        FrameChunker(0)
