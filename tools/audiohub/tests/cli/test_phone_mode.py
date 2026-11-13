"""Tests for audiohub.cli.phone_mode: the phone's audio settings."""

import pytest

from audiohub.cli.phone_mode import phone_audio_settings
from audiohub.config import AudioSettings, PhoneSettings, Settings


def test_phone_mode_moves_the_reply_point_by_its_extra_lag():
    # Regression: phone mode lengthened the echo tail but left the reply point
    # where the glasses' is, so the end of Claude's echo was taken for a reply.
    glasses = AudioSettings(echo_tail_s=2.0, reply_after_s=1.3)
    phone = phone_audio_settings(Settings(audio=glasses, phone=PhoneSettings(echo_tail_s=2.5)))
    assert (phone.echo_tail_s, phone.reply_after_s) == pytest.approx((2.5, 1.8))
