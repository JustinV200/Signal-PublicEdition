"""Page-level checks of the night sky's effect pool (static/night/effects/) and moon
(static/night/moon.js) in headless Edge.

Checks that the picker is a pure function of the date (same seed, same effects; 3 or 4
of them; never two of one family; every effect in the pool comes up over a year), that
the moon's phase is computed from the date (a known full moon and a known new moon),
and that a frame with every effect on, the moon, a meteor and the brightest star never
passes the per-channel cap or the light budget. Skipped where headless Edge can't run.
"""

import pytest

CAP_RGB = (107, 77, 64)  # 42%, 30% and 25% of a channel: paint.js's CHANNEL_PEAK
# Mean linear luminance of a frame as a share of full white. Measured: a real night is
# 0.08% to 0.30% (the brightest has a wide band and the fog effect), every effect at
# once on a real sky 0.14% to 0.27%, and this test's frame (every effect, the band
# through the pivot, a full moon and a meteor) 0.31%. The bound leaves it some room.
LIGHT_BUDGET_PCT = 0.45
FULL_MOON_SEED = 20240125  # full at 17:54 UTC
NEW_MOON_SEED = 20240111  # new at 11:57 UTC
PHASE_TOLERANCE = 1 / 29.53  # a day, in phase

HARNESS = """<!doctype html>
<html><body><script type="module">
import { buildSky } from "/static/night/night.js";
import { drawFrame } from "/static/night/draw.js";
import { EFFECTS, buildEffects, pickEffects } from "/static/night/effects/index.js";
import { buildMoon, moonPhase } from "/static/night/moon.js";
const names = (seed) => pickEffects(seed, EFFECTS).map((e) => e.name).join();
const seeds = Array.from({ length: 365 }, (_, i) => 20260101 + i);
const picks = seeds.map((seed) => pickEffects(seed, EFFECTS));
// Every effect built, the band through the pivot and the brightest warm-white hero
// star on it, the moon and a meteor mid-flight, at moments when the hour marker, the
// heartbeat and the schedules can be at their peak; the brightest channel of any
// pixel and the mean linear luminance over the frame.
const canvas = document.createElement("canvas");
canvas.width = 1920; canvas.height = 1080;
const context = canvas.getContext("2d", { willReadFrequently: true });
const sky = buildSky(20261019);
sky.stars.push({ r: 0, cos: 1, sin: 0, brightness: 1, radius: 3.4, colour: 0, hero: true,
  twinkle: null });
sky.band.offset = 0;
const effects = buildEffects(20261019, sky, EFFECTS);
const meteor = { x: 0.5, y: 0.4, dx: Math.SQRT1_2, dy: Math.SQRT1_2, length: 0.28,
  start: 0, duration: 2 };
const linear = Array.from({ length: 256 }, (_, v) => {
  const c = v / 255;
  return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
});
const max = [0, 0, 0];
let worstMean = 0;
for (const t of [36045, 36061, 39630, 43290]) {
  drawFrame(context, sky, { t, rotation: 0.3, meteor: { ...meteor, start: t - 1 },
    width: 1920, height: 1080, zoom: 0.99, bandGain: 1,
    nebulaTints: { rgbs: sky.nebulae.map(() => [1, 0.2, 0.35]), amount: 0.5 },
    moon: buildMoon(FULL_SEED), effects });
  const data = context.getImageData(0, 0, 1920, 1080).data;
  let luminance = 0;
  for (let i = 0; i < data.length; i += 4) {
    for (let c = 0; c < 3; c++) max[c] = Math.max(max[c], data[i + c]);
    luminance += 0.2126 * linear[data[i]] + 0.7152 * linear[data[i + 1]]
      + 0.0722 * linear[data[i + 2]];
  }
  worstMean = Math.max(worstMean, (100 * luminance) / (data.length / 4));
}
const result = {
  sameSeed: names(20261019) === names(20261019),
  counts: [...new Set(picks.map((p) => p.length))].sort(),
  familiesDistinct: picks.every((p) => new Set(p.map((e) => e.family)).size === p.length),
  distinctNights: new Set(picks.map((p) => p.map((e) => e.name).join())).size,
  everyEffectPicked: EFFECTS.every((e) => picks.some((p) => p.includes(e))),
  uniqueNames: new Set(EFFECTS.map((e) => e.name)).size === EFFECTS.length,
  fullPhase: moonPhase(FULL_SEED), newLit: buildMoon(NEW_SEED).lit,
  max, worstMean,
};
fetch("/result", { method: "POST", headers: { "content-type": "application/json" },
  body: JSON.stringify(result) });
</script></body></html>""".replace("FULL_SEED", str(FULL_MOON_SEED)).replace(
    "NEW_SEED", str(NEW_MOON_SEED)
)


@pytest.mark.asyncio
async def test_effects_are_picked_from_the_date_and_stay_under_the_cap(run_harness) -> None:
    result = await run_harness(HARNESS)
    assert result["sameSeed"] is True
    assert result["counts"] == [3, 4]
    assert result["familiesDistinct"] is True
    assert result["distinctNights"] > 300
    assert result["everyEffectPicked"] is True
    assert result["uniqueNames"] is True
    assert abs(result["fullPhase"] - 0.5) < PHASE_TOLERANCE
    assert result["newLit"] < 0.02  # a new moon shows nothing
    # The warm-white hero star's red is exactly the cap; nothing under it adds to it.
    assert result["max"][0] == CAP_RGB[0]
    assert result["max"][1] <= CAP_RGB[1] and result["max"][2] <= CAP_RGB[2]
    assert result["worstMean"] < LIGHT_BUDGET_PCT
