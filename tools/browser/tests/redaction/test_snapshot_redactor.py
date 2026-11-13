"""The redaction pass, with a fake sensitivity check (no browser)."""

import pytest

from browser_tool.redaction import redact_snapshot

SNAPSHOT = """- generic [ref=e1]:
  - textbox "User" [ref=e2]: alice
  - textbox "Password" [ref=e3]: hunter2
  - textbox "Notes" [ref=e4]:
    - text: child text
  - button "Sign in" [ref=e5]
  - paragraph [ref=e6]: hunter2 is not checked here"""


def checker(sensitive: set[str]):
    async def is_sensitive(ref: str) -> bool:
        return ref in sensitive

    return is_sensitive


@pytest.mark.asyncio
async def test_only_sensitive_value_lines_are_rewritten():
    result = await redact_snapshot(SNAPSHOT, checker({"e3"}))
    assert '  - textbox "Password" [ref=e3]: "[redacted]"' in result.splitlines()
    assert "alice" in result
    assert result.count("hunter2") == 1  # the paragraph is checked but not sensitive


@pytest.mark.asyncio
async def test_children_of_a_sensitive_line_are_dropped():
    result = await redact_snapshot(SNAPSHOT, checker({"e4"}))
    assert "child text" not in result
    assert '- button "Sign in" [ref=e5]' in result


@pytest.mark.asyncio
async def test_fails_closed_on_check_errors_and_unparseable_lines():
    async def broken(ref: str) -> bool:
        raise RuntimeError("page went away")

    assert "alice" not in await redact_snapshot(SNAPSHOT, broken)
    assert "leaked" not in await redact_snapshot("- 'textbox [ref=e1]: leaked", checker(set()))


@pytest.mark.parametrize(
    ("snapshot", "checked"),
    [
        ('- link "Home" [ref=e1]:\n  - /url: /home', []),  # an href can't hold a field value
        ('- link "Home" [ref=e1]:\n  - /url: /home\n  - text: inner', ["e1"]),
        ('- link "Home" [ref=e1]:\n  - /url: /home\n  - \'broken', ["e1"]),  # unparsed: checked
    ],
)
@pytest.mark.asyncio
async def test_only_url_children_skip_the_live_check(snapshot, checked):
    seen = []

    async def recording(ref: str) -> bool:
        seen.append(ref)
        return False

    await redact_snapshot(snapshot, recording)
    assert seen == checked
