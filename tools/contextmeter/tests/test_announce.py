"""Tests for when the hook speaks and what it says."""

from contextmeter.announce import decide


def test_speaks_once_per_band_and_firmly_at_threshold():
    said = []
    last = 0
    for pct in [10, 39.9, 41, 45, 52, 58, 74, 76, 79, 81, 30, 42]:
        last, note = decide(pct, 75, last)
        said.append((pct, note))
    spoken = [pct for pct, note in said if note]
    # 30 after 81 is a compaction: it resets, so 42 speaks again.
    assert spoken == [41, 52, 74, 76, 81, 42]
    assert "(handoff at 75%)" in dict(said)[74]
    assert "hand off now, per AGENTS.md section 4" in dict(said)[76]
