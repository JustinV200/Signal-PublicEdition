"""Page-level check of the board page's night view wiring (board.html, board.css,
board.js) in headless Edge, with a stand-in for the daemon's /ws.

The harness loads the real board.html body and board.css, then sends scene messages
the way the daemon does: the night view starts one sky inside the fitted stage (so it
sits on the board, not the wall), keeps it while only the remembered view changes,
stops it (canvas gone, the items visible again) when the view goes back to the items,
and starts it again on the next night. Under it, not even an item
whose SVG says visibility="visible" (which paints through a hidden parent) or carries
a <style> (SVG or markdown) shows, nor under the TODO or idle view (where the board
agent's "thinking" box still shows) or in blank mode, and
mermaid's scratch element never paints. The sky itself is tested in
test_night_page.py. Skipped where headless Edge can't run.
"""

import pytest

HARNESS = """<!doctype html>
<html><head><link rel="stylesheet" href="/static/board.css">
<script src="/static/vendor/dompurify/purify.min.js"></script>
<script src="/static/vendor/marked/marked.umd.js"></script></head><body>
<script>
  // board.js connects to the daemon's /ws on import; this stands in for it.
  window.WebSocket = class { constructor() { window.fakeSocket = this; } };
</script>
<script type="module">
if (document.readyState !== "complete") await new Promise((done) => addEventListener("load", done));
const html = await (await fetch("/static/board.html")).text();
document.body.replaceChildren(...new DOMParser().parseFromString(html, "text/html").body.children);
await import("/static/board.js");
const stage = { width: 320, height: 180, matrix3d: null, quad: null,
  projector: { width: 320, height: 180 } };
const style = { color: "#ffffff", stroke_width: 2, font_size: 0, rough: false, opacity: 1 };
// Two ways out of a hidden layer: a visibility="visible" attribute, and a <style> (as in
// a scene saved before the daemon stripped it), which renderSvg must drop.
const unhide = "#screen,#stage,#items,#todo{visibility:visible!important;opacity:1!important}";
const leak = { id: "s1", kind: "svg", x: 0, y: 0, w: 100, h: 100, style, created_by: "t",
  created_at: "", content: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
    + `<style>${unhide}</style>`
    + '<rect id="leak" visibility="visible" width="10" height="10" fill="#fff"/></svg>' };
// A markdown item's <style> would unhide the layers just the same (renderMarkdown drops
// it). Text first: a <style> leading the fragment is hoisted out by the parser anyway.
const mdLeak = { ...leak, id: "m1", kind: "markdown", content: `x<style>${unhide}</style>` };
const send = (view, night) => window.fakeSocket.onmessage({ data: JSON.stringify(
  { type: "scene", items: [leak, mdLeak], board_quad: null, view, night, stage }) });
// Whether an element paints: visible itself, and no ancestor at opacity 0.
const paints = (element) => {
  for (let node = element; node; node = node.parentElement) {
    if (getComputedStyle(node).opacity === "0") return false;
  }
  return getComputedStyle(element).visibility === "visible";
};
const nightEl = document.getElementById("night");
// The ids of the stage's layers, other than the sky, that paint: under the night view
// none may (items, TODO and idle views, highlights, whatever is added later).
const lit = () => [...document.getElementById("stage").children]
  .filter((layer) => layer !== nightEl && paints(layer)).map((layer) => layer.id);
const seen = () => ({ canvases: nightEl.querySelectorAll("canvas").length,
  sky: getComputedStyle(nightEl).visibility, lit: lit(),
  item: paints(document.getElementById("leak")) });
send("night", { seed: 20261019, previous_view: "items" });
// Items render in a microtask (renderers.js); later scenes reuse the same element.
await new Promise((done) => setTimeout(done, 0));
const shown = seen();
const first = nightEl.querySelector("canvas");
send("night", { seed: 20261019, previous_view: "todo" });
const kept = nightEl.querySelector("canvas") === first;
send("items", null);
const after = seen();
// The TODO view hides the items the same way.
send("todo", null);
const todoItem = paints(document.getElementById("leak"));
// The idle view hides them too, but not the board agent's "thinking" box.
const thinking = { ...leak, id: "loading", kind: "loading", content: "" };
window.fakeSocket.onmessage({ data: JSON.stringify({ type: "scene",
  items: [leak, mdLeak, thinking], board_quad: null, view: "idle", night: null, stage }) });
await new Promise((done) => setTimeout(done, 0));
const idleItem = paints(document.getElementById("leak"));
const idleThinking = paints(document.querySelector(".item-loading"));
send("night", { seed: 20261020, previous_view: "items" });
const again = seen();
// A clean capture's blank page hides the same item on the items view.
send("items", null);
window.fakeSocket.onmessage({ data: JSON.stringify({ type: "mode", mode: "blank", markers: [] }) });
const blankItem = paints(document.getElementById("leak"));
// Mermaid's scratch element sits on <body>, outside every hidden layer.
const scratch = document.body.appendChild(document.createElement("div"));
scratch.id = "dmermaid-x";
const result = { shown, kept, after, again, todoItem, idleItem, idleThinking, blankItem,
  scratch: getComputedStyle(scratch).opacity,
  // The sky lives in the fitted stage, sized like the other layers, so it's warped onto
  // the board quad and clipped to it.
  fitted: nightEl.parentElement.id, size: [nightEl.clientWidth, nightEl.clientHeight] };
fetch("/result", { method: "POST", headers: { "content-type": "application/json" },
  body: JSON.stringify(result) });
</script></body></html>"""


@pytest.mark.asyncio
async def test_board_page_starts_the_night_sky_and_stops_it_on_leaving(run_harness) -> None:
    result = await run_harness(HARNESS)
    assert result["shown"] == {"canvases": 1, "sky": "visible", "lit": [], "item": False}
    assert result["kept"] is True
    assert result["after"] == {
        "canvases": 0,
        "sky": "hidden",
        "lit": ["items", "highlights"],
        "item": True,
    }
    assert result["again"] == {"canvases": 1, "sky": "visible", "lit": [], "item": False}
    assert (result["todoItem"], result["blankItem"], result["idleItem"]) == (False, False, False)
    assert result["idleThinking"] is True
    assert result["scratch"] == "0"
    assert (result["fitted"], result["size"]) == ("stage", [320, 180])
