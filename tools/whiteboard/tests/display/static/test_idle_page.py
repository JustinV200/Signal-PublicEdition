"""Page-level check of the idle view's JS (static/idle/) in headless Edge.

A harness page renders a payload, then a second one, and POSTs what it sees to /result
(conftest.run_harness). Checks that outside text (plan lines, the headline) is shown as
text and never parsed as HTML, that overflowing rows become "+N more", that a too-long
row is cut at its first ":" or " (", that the clock shows HH:MM, that only a task the
page had shown open gets the cross-out animation, that empty states read as such, that keynotes take
the priorities' place, and
that the news ticker scrolls left at 26 px, carries on through a re-render without a
jump, takes new headlines only at its loop seam, and sleeps while hidden.
Skipped where headless Edge can't run.
"""

import re

import pytest

HARNESS = """<!doctype html>
<html><head><link rel="stylesheet" href="/static/board.css">
<link rel="stylesheet" href="/static/idle/idle.css">
<link rel="stylesheet" href="/static/idle/top.css">
<link rel="stylesheet" href="/static/idle/ticker.css"></head>
<body data-view="idle"><div id="idle" style="position:absolute;width:1112px;height:720px"></div>
<script type="module">
import { renderIdle, fitIdle } from "/static/idle/idle.js";
const chip = { label: "CHEM 120", color: "#76ff03" };
const task = (id, text, done) => ({ id, chip, text, due: "today", when: "today", done });
const evil = "<img src=x onerror=alert(1)>";
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const track = () => document.querySelector(".ticker-track");
const offset = () => new DOMMatrix(getComputedStyle(track()).transform).m41;
const items = () => [...track().children].map((el) => el.firstChild.textContent);
const data = (doneA, headlines) => ({
  usage: { five_hour: 42, week: null, agents: 3 },
  weather: { code: 2, is_day: true, temp: 61, hi: 64, lo: 48, rain: 10, word: "Partly cloudy",
    place: "Springfield, IL", as_of: null },
  tasks: [task("a", "A19", doneA), task("b", evil, false),
    task("c", "Project notebook: EDA, one-hot, splits, decision tree, ROC, hit rate", false),
    ...[1, 2, 3, 4].map((n) => task(`x${n}`, `Extra ${n}`, false))],
  notes: [], agents: null, upcoming: [], overdue: 3,
  // The second render has keynotes: they take the priorities' place.
  keynotes: doneA ? ["A19 due 23:59 tonight", evil] : [],
  news: { headlines, source: "AllSides", px_s: 200 },
});
fitIdle({ width: 1112, height: 720 });
const old = [evil, "Second story", "Third story"];
renderIdle(data(false, old));
await sleep(600);
renderIdle(data(true, old));
const ticker = { first: offset(), firstItems: items() };
const rows = [...document.querySelectorAll(".task-row")];
const result = {
  imgs: document.querySelectorAll("#idle img").length,
  taskText: rows[1].querySelector(".text").textContent,
  cutText: rows[2].querySelector(".text").textContent,
  ticker,
  separator: document.querySelector(".ticker-sep").textContent,
  tickerFont: getComputedStyle(document.querySelector(".ticker-item")).fontSize,
  source: document.querySelector(".news .meta").textContent,
  more: document.querySelector(".today .more")?.textContent,
  rowCount: rows.length,
  animated: rows.filter((row) => row.classList.contains("just-done")).length,
  clock: document.querySelector(".clock").textContent,
  usage: document.querySelector(".date-block .meta").textContent,
  empties: [...document.querySelectorAll(".empty")].map((el) => el.textContent),
  keynotes: [...document.querySelectorAll(".keynote-row")].map((el) => el.textContent),
  todayCounts: document.querySelector(".today .meta").textContent,
};
// Then the ticker: it keeps moving, and new headlines wait for the loop seam.
await sleep(600);
ticker.moved = offset();
renderIdle(data(true, ["Fresh A", "Fresh B"]));
ticker.atSwap = offset();
ticker.itemsAtSwap = items();
await sleep(2500);
ticker.later = items();
// Hidden under another view, re-renders (each push) mustn't pile up wake-up timers:
// the ticker asks for about one frame a second, not one per re-render per second.
document.body.dataset.view = "todo";
await sleep(100);
for (let n = 0; n < 6; n++) renderIdle(data(true, ["Fresh A", "Fresh B"]));
await sleep(100);
let frames = 0;
const realFrame = window.requestAnimationFrame;
window.requestAnimationFrame = (callback) => { frames++; return realFrame(callback); };
await sleep(2100);
ticker.hiddenFrames = frames;
fetch("/result", { method: "POST", headers: { "content-type": "application/json" },
  body: JSON.stringify(result) });
</script></body></html>"""


@pytest.mark.asyncio
async def test_idle_page_shows_outside_text_safely_fits_rows_and_scrolls_news(run_harness) -> None:
    result = await run_harness(HARNESS)
    evil = "<img src=x onerror=alert(1)>"
    assert result["imgs"] == 0
    assert result["taskText"] == evil
    assert result["cutText"] == "Project notebook"
    assert (result["rowCount"], result["more"]) == (5, "+2 more")
    assert result["animated"] == 1
    assert re.fullmatch(r"\d\d:\d\d", result["clock"])
    assert result["usage"] == "Claude 5h 42% · wk -- · 3 agents"
    assert result["empties"] == ["No agent tasks", "No dates this week"]
    assert result["keynotes"] == ["A19 due 23:59 tonight", evil]
    # The overdue count comes from the daemon (rows past the idle cap still count).
    assert result["todayCounts"] == "· 3 overdue · 6 today"

    # The ticker: headlines as text, 26 px, the source fixed beside it.
    ticker = result["ticker"]
    assert ticker["firstItems"][:3] == [evil, "Second story", "Third story"]
    assert (result["separator"], result["tickerFont"], result["source"]) == (
        "•",
        "26px",
        "AllSides",
    )
    # It scrolls left, and a re-render (each push replaces the board) doesn't restart it.
    assert ticker["moved"] < ticker["first"] < 0
    # New headlines don't jump in: nothing on the track changes at the push ...
    assert ticker["atSwap"] == ticker["moved"]
    assert set(ticker["itemsAtSwap"]) <= {evil, "Second story", "Third story"}
    # ... they join at the loop seam, from their top, right after the old list's last.
    later = ticker["later"]
    seam = next(i for i, text in enumerate(later) if text.startswith("Fresh"))
    assert later[seam] == "Fresh A" and all(text.startswith("Fresh") for text in later[seam:])
    assert seam == 0 or later[seam - 1] == "Third story"
    # Hidden: about one frame a second over 2.1 s, however many re-renders came first.
    assert ticker["hiddenFrames"] <= 3
