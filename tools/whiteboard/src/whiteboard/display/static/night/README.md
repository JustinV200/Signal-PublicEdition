# night

The night view's renderer: a dim, seeded night sky the projector shows while sleep mode runs (`tools/sleepmode`). This folder is the renderer, behind `night.js`; "How it's wired in" below says where the routes, the view and the page wiring live.

## API (`night.js`, ES module)

```js
import { startNight, buildSky, buildScene, renderFrame } from "/static/night/night.js";

const night = startNight(container, { seed: 20261019 });
night.stop();   // removes the canvas and every listener; safe to call twice
```

- `container`: a positioned block element (`position: relative` or `absolute`). The canvas fills it.
- `seed` (integer): the night, `YYYYMMDD` of the evening it began (nights run noon to noon). `TypeError` otherwise.
- Starting again in a container that already shows a sky stops the old one first.
- `buildSky(seed)` is the pure sky (pivot, band, nebulae, stars); `buildScene(seed)` adds the moon, the night's effects and the meteor schedule; `renderFrame(context, scene, t, width, height)` draws it at sky time `t`. For tests and previews.

## Deterministic, offline

Everything the sky shows is a pure function of the seed and the clock: the star field, the colours, the effects picked and their timing, the meteors and the moon's phase all come from the seeded mulberry32 generator (`random.js`) or from arithmetic on the date. Nothing uses `Math.random()`, nothing fetches, and no model is called. The same date always gives the same night, and a reload mid-night shows the same moment. The one thing taken from the machine is its time zone: the moon's phase is taken at the night's local midnight, and the night window (22:00 to 08:00) that the moon's drift and the zoom follow is in local time, through `Date`, so daylight saving is handled. The colours are decorative only; nothing carries meaning.

## What varies per seed

- The pivot the sky turns around, and the star field's density (1600 to 3200 stars over the sky disk, a 16:9 frame sees about a sixth) and arrangement, with most stars faint and a handful bright.
- Each star's colour: warm white, amber, orange, blue-white or cyan (`STAR_COLOURS`, weighted warm; blue-white and cyan are accents). 2.5% are hero stars, bright with a soft halo eight times their size.
- A Milky Way band: its angle, how far it runs from the pivot, its spread, its glow, its two hues (a core and an edge hue from crimson, magenta, amber, gold, violet and teal, weighted warm), 2 to 4 soft nebulae along it, each with a dense core in a second hue, and 250 to 700 extra fainter stars scattered along it.
- Which stars twinkle (14% of them, periods of 3 to 8 s, dipping to 40%), and each nebula's slow breath (25 to 45 s, fading by a quarter and back).
- A meteor schedule: one every 60 to 180 s, each 1.4 to 2.4 s long, always falling, warm white, at most 85% of the cap.
- 3 or 4 effects from the pool in `effects/` (its README lists them), never two of one family.

The moon shows every night (`moon.js`): its real phase for the date, from the mean synodic month (reference new moon 2000-01-06 18:14 UTC, 29.530588853 days; within about a day of the true phase), as a 15 px crescent or disc, lit on the right while waxing, that drifts across the top of the board between 22:00 and 08:00 with a soft halo breathing over 45 s. A new moon (under 2% lit, about a day each side) shows nothing, which is the real phase.

Motion is tied to the clock, not to page load: the sky turns once a day about its pivot, and every schedule is laid out from 17:00 UTC (midday here). Nothing is kept between starts.

## Brightness cap

Every light is a colour whose channels are at most `CHANNEL_PEAK` (`paint.js`): red 42%, green 30%, blue 25% (107, 77 and 64 of 255), drawn with normal blending, so no pixel ever passes those whatever overlaps. Blue, the channel that suppresses melatonin, keeps the old flat 25% cap; green barely moves; red has headroom because it hardly affects sleep and is what reads as colour against the projector's blue-grey black level. The sky spends that headroom on small, saturated, warm things (nebula cores, hero halos, the band's narrow core, the effects) rather than on lifting everything: at the projector's Brightness 30 anything under about 24/255 sits in its black level and never shows, so the faintest star is now about 27/255 red instead of 8. Measured on 1920x1080 frames of four nights: 3% to 28% of the pixels at or above 24/255 (the old sky: 0.1% to 3.5%), a mean luminance of 0.08% to 0.30% of white (the old sky: 0.03% to 0.21%; the brightest night is one with a wide band and the fog effect, which adds about 0.05% on its own), and melanopic light between 0.8 and 1.6 times the old sky's, lower on the brighter nights, which are where the old sky spent its blue. That is about as much light as the projector's own black level. Black is no light on the projector; the vibrancy comes from hue and contrast, not from light.

The page test (`tests/display/static/test_night_effects.py`) draws a frame with every effect on and checks those per-channel maxima and a light budget on the mean.

## Cost

One canvas, redrawn at most 20 times a second from `requestAnimationFrame`; the loop is cancelled while `document.hidden`. A frame at 1920x1080 takes about 10.5 ms on a real night, and 16 ms with every effect in the pool on at once, with a software canvas (all stars are placed with four multiplies each and only those in view are drawn). The backing store follows `devicePixelRatio` (capped at 2), so the projector's 1280x720 CSS pixels at 150% draw at 1920x1080. Size changes come through a `ResizeObserver`. Under `prefers-reduced-motion: reduce` the sky is drawn once and only redrawn on resize: no twinkle, no meteors, no turning, no effects moving.

## How it's wired in

The contract is in `tools/sleepmode/README.md` ("The whiteboard contract"); the whiteboard README's "The night view" covers what it does to the board.

- **Routes:** `POST /api/night/show {seed?}` and `POST /api/night/hide` in `display/server/api_routes.py`, behind the daemon's token guard like every `/api/*` route.
- **The view:** the scene's `view` becomes `"night"`, and `Scene.night` keeps `{seed, previous_view}` (`display/scene`: `show_night`, `hide_night`), saved in `scene.json`.
- **Pausing:** `BoardController` refuses flashes and highlights while it shows, and its `page_changed_s()` is `math.inf`, which pauses the change watcher (and so the board agent and the cross-out check) and the drift monitor.
- **The page:** `board.html` has a `#night` layer in `#stage`, sized like the other views (`stage.js`), so the sky is warped onto the board quad and clipped to it like the items, with the wall left black. `board.css` hides every other layer under `body[data-view="night"]`. `board.js` calls `startNight(layer, night)` only when a scene message brings a new `seed` (each call rebuilds the sky), and `stop()` once the view is anything else, since `visibility: hidden` alone would keep the loop running. A daemon restart, or `show` twice in one night, starts the same sky at the same point of its turn.

## Files

- `night.js`: the entry point: the API, the scene, the canvas, the frame loop, sky time.
- `sky.js`: `buildSky(seed)`, the pure star field, band and nebulae; the colour tables.
- `moon.js`: the moon's phase for the date and its drawing.
- `meteors.js`: the seeded meteor schedule.
- `draw.js`: one frame (band, nebulae, effects, stars and halos, moon, meteor).
- `paint.js`: the per-channel cap and the soft shapes everything paints with.
- `timing.js`: sky time, slow waves, fade envelopes, event schedules and the night's progress.
- `geometry.js`: sky units to pixels for the current turn, the radius that stays on the board all night, and paths across the frame.
- `random.js`: mulberry32 and its helpers.
- `effects/`: the effect pool, its registry and picker (see its README).

Tested by `tests/display/static/test_night_page.py` (the API, the seed and the cap) and `test_night_effects.py` (the picker, the moon's phase, the cap and light budget with every effect on), and the page wiring by `test_board_page.py` (headless Edge, through the `run_harness` fixture in that folder's `conftest.py`).
