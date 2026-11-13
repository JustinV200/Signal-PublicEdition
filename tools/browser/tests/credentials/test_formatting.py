"""fill_login's model-facing text can't carry a value through the reason."""

from browser_tool.credentials import FillResult, format_fill_result


def test_fill_result_is_ok_or_a_reason_code():
    assert format_fill_result(FillResult(ok=True, reason="filled")) == "ok"
    result = format_fill_result(FillResult(ok=False, reason="origin_mismatch"))
    assert result == "failed: origin_mismatch"


def test_reason_that_is_not_a_code_cannot_carry_a_value():
    assert format_fill_result(FillResult(ok=False, reason="password is hunter2")) == "failed: error"
    assert format_fill_result(FillResult(ok=False, reason="Hunter2")) == "failed: error"
