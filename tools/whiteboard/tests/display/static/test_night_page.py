"""Page-level check of the night view's JS (static/night/night.js) in headless Edge.

Checks that the sky is a pure function of the seed (one seed, one layout; the next
night differs), that a started sky is one
canvas that stop() removes, and that a drawn frame (band, nebulae, halo, moon and
meteor included, with the brightest possible star on top of them) never passes the
per-channel brightness cap. The effects and the moon's phase are covered by
test_night_effects.py. Skipped where headless Edge can't run.
"""

import pytest

CAP_RGB = (107, 77, 64)  # 42%, 30% and 25% of a channel: paint.js's CHANNEL_PEAK

HARNESS = """<!doctype html>
<html><body><div id="night" style="position:relative;width:320px;height:180px"></div>
<script type="module">
import { buildSky, startNight } from "/static/night/night.js";
import { drawFrame } from "/static/night/draw.js";
import { buildMoon } from "/static/night/moon.js";
const layout = (seed) =>
  JSON.stringify(buildSky(seed).stars.slice(0, 40).map((s) => [s.r, s.cos, s.sin]));
const box = document.getElementById("night");
const lit = startNight(box, { seed: 20261019 });
const litChildren = box.childElementCount;
const litTag = box.firstElementChild?.tagName;
lit.stop();
lit.stop();
// Full-HD, as shown: small radii lose peak to anti-aliasing. One offscreen frame
// with a meteor mid-flight, the moon, and a full-brightness warm-white hero star (with
// its halo) put at the pivot, where the band glow is drawn too; the brightest value of
// each channel over every pixel.
const canvas = document.createElement("canvas");
canvas.width = 1920; canvas.height = 1080;
const context = canvas.getContext("2d", { willReadFrequently: true });
const meteor = { x: 0.5, y: 0.4, dx: Math.SQRT1_2, dy: Math.SQRT1_2, length: 0.28,
  start: 0, duration: 2 };
const sky = buildSky(20261019);
sky.stars.push({ r: 0, cos: 1, sin: 0, brightness: 1, radius: 3.4, colour: 0, hero: true,
  twinkle: null });
sky.band.offset = 0;
drawFrame(context, sky, { t: 1, rotation: 0, meteor, width: 1920, height: 1080,
  moon: buildMoon(20261019) });
const data = context.getImageData(0, 0, 1920, 1080).data;
const max = [0, 0, 0];
for (let i = 0; i < data.length; i += 4) {
  for (let c = 0; c < 3; c++) max[c] = Math.max(max[c], data[i + c]);
}
let badSeed = "none";
try { startNight(box, { seed: "x" }); } catch (error) { badSeed = error.name; }
const result = {
  sameSeed: layout(20261019) === layout(20261019),
  nextNight: layout(20261019) === layout(20261020),
  litChildren, litTag, afterStop: box.childElementCount,
  max, badSeed,
};
fetch("/result", { method: "POST", headers: { "content-type": "application/json" },
  body: JSON.stringify(result) });
</script></body></html>"""


@pytest.mark.asyncio
async def test_night_page_is_seeded_capped_and_stops_clean(run_harness) -> None:
    result = await run_harness(HARNESS)
    assert result["sameSeed"] is True
    assert result["nextNight"] is False
    assert result["litChildren"] == 1 and result["litTag"] == "CANVAS"
    assert result["afterStop"] == 0
    assert result["badSeed"] == "TypeError"
    # The warm-white hero star's red is exactly the cap; nothing under it adds to it.
    assert result["max"][0] == CAP_RGB[0]
    assert result["max"][1] <= CAP_RGB[1] and result["max"][2] <= CAP_RGB[2]
