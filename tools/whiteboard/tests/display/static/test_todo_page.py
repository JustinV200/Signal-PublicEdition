"""Page-level check of the TODO view's JS (static/todo.js) in headless Edge.

A tiny harness page imports todo.js, renders a payload, then a second one, and POSTs
what it sees to /result (conftest.run_harness). Checks that plan text is shown as text
(never parsed as HTML), keynote lines included, and that only a row the page had shown
open gets the cross-out animation. Skipped where headless Edge can't run.
"""

import pytest

HARNESS = """<!doctype html>
<html><body><div id="todo"></div>
<script type="module">
import { renderTodo } from "/static/todo.js";
const box = { x: 0, y: 0, w: 400, h: 30 };
const metrics = { font_px: 20, tag_font_px: 12, due_font_px: 15, check_w: 22, tag_w: 90 };
const row = (id, text, done) => ({ id, text, done, tag: "chem-120", due_label: "23:59",
  color: "#76ff03", hint: false, overdue: false, text_x: 120, text_w: 200, ...box });
const view = (rows) => ({ title: "TODO", date_label: "Monday 19 October", updated_label: "",
  note: "", header: box, body: box, metrics, headings: [], rows, more: null });
renderTodo(view([row("a", "A19", false), row("b", "<img src=x onerror=alert(1)>", false)]), ["a"]);
const firstAnimated = document.querySelectorAll(".just-done").length;
const keynotes = { label: "Keynotes", lines: ["A19 due tonight", "<img src=x onerror=alert(1)>"],
  font_px: 22, ...box };
renderTodo({ ...view([row("a", "A19", true), row("b", "<img src=x onerror=alert(1)>", false),
  row("c", "New, already done", true)]), keynotes }, ["a", "c"]);
const classes = (id) => [...document.querySelectorAll(".todo-row")]
  .find((el) => el.querySelector(".todo-label").textContent === id)?.className;
const result = {
  firstAnimated,
  a: classes("A19"),
  c: classes("New, already done"),
  imgs: document.querySelectorAll("#todo img").length,
  bText: [...document.querySelectorAll(".todo-label")].map((el) => el.textContent)[1],
  keynotes: [...document.querySelectorAll(".todo-keynote")].map((el) => el.textContent),
};
fetch("/result", { method: "POST", headers: { "content-type": "application/json" },
  body: JSON.stringify(result) });
</script></body></html>"""


@pytest.mark.asyncio
async def test_todo_page_shows_text_safely_and_animates_only_rows_it_saw_open(
    run_harness,
) -> None:
    result = await run_harness(HARNESS)
    assert result["firstAnimated"] == 0
    assert result["a"].split() == ["todo-row", "done", "just-done"]
    assert result["c"].split() == ["todo-row", "done"]
    assert result["imgs"] == 0 and result["bText"] == "<img src=x onerror=alert(1)>"
    # Keynotes (model output) go in as text too.
    assert result["keynotes"] == ["A19 due tonight", "<img src=x onerror=alert(1)>"]
