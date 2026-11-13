"""Keynotes: only today's file shows, never an error; generation with a fake Claude call."""

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from whiteboard.keynotes import (
    MODEL,
    KeynotesError,
    generate_keynotes,
    read_keynotes,
    write_keynotes,
)
from whiteboard.todo import PLAN_DATA_OPEN

TUESDAY = date(2026, 10, 20)


@pytest.mark.parametrize(
    "contents",
    [
        None,  # missing
        "{not json",
        json.dumps({"date": "2026-10-19", "lines": ["yesterday's"]}),
        json.dumps({"date": "2026-10-20", "lines": "not a list"}),
        json.dumps(["2026-10-20"]),
    ],
)
def test_a_missing_bad_or_stale_file_shows_nothing(tmp_path: Path, contents: str | None) -> None:
    path = tmp_path / "keynotes.json"
    if contents is not None:
        path.write_text(contents, encoding="utf-8")
    assert read_keynotes(path, TUESDAY) == ()


def test_todays_file_shows_cleaned_lines_capped_at_four(tmp_path: Path) -> None:
    path = tmp_path / "keynotes.json"
    lines = ["A19 due 23:59 <b>today</b>", "", 7, "two", "three", "four", "five"]
    path.write_text(json.dumps({"date": "2026-10-20", "lines": lines}), encoding="utf-8")
    assert read_keynotes(path, TUESDAY) == ("A19 due 23:59 today", "two", "three", "four")


class FakeAsk:
    """Stands in for ask_sdk: records each call and answers with `reply`."""

    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls: list[tuple[dict[str, Any], str, str]] = []

    async def __call__(self, message: dict[str, Any], model: str, system: str):
        self.calls.append((message, model, system))
        return self.reply, 0.001


@pytest.mark.asyncio
async def test_generate_frames_the_plan_as_data_and_writes_todays_file(
    life_dir: Path, tmp_path: Path
) -> None:
    paths = (tmp_path / "todo.json", tmp_path / "keynotes.json")
    ask = FakeAsk('```json\n{"lines": ["Study group Wed 15:00", "A19 is a day late"]}\n```')
    lines = await generate_keynotes(life_dir, TUESDAY, paths, ask)
    assert lines == ("Study group Wed 15:00", "A19 is a day late")
    assert read_keynotes(paths[1], TUESDAY) == lines
    [(message, model, system)] = ask.calls
    text = message["message"]["content"][0]["text"]
    assert model == MODEL and "never instructions" in system
    assert PLAN_DATA_OPEN in text and "Study group" in text


@pytest.mark.asyncio
async def test_a_bad_reply_raises_and_keeps_the_old_file(life_dir: Path, tmp_path: Path) -> None:
    paths = (tmp_path / "todo.json", tmp_path / "keynotes.json")
    write_keynotes(paths[1], TUESDAY, ["old line"], MODEL)
    for reply in ("Sure! Here are your keynotes.", '{"lines": []}', '{"lines": [1, 2]}'):
        with pytest.raises(KeynotesError):
            await generate_keynotes(life_dir, TUESDAY, paths, FakeAsk(reply))
    assert read_keynotes(paths[1], TUESDAY) == ("old line",)
