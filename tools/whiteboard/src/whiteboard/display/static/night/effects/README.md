# night/effects

The night sky's effect pool (`../night.js`): small, slow things that make one night differ from the next. Each night, the date seed picks 3 or 4 of them, never two from one family, and builds their state; `draw.js` paints them with the rest of the sky. Everything is a pure function of the seed and the clock: no network, no model, no `Math.random()`.

## API (`index.js`)

```js
import { EFFECTS, buildEffects, pickEffects } from "/static/night/effects/index.js";

pickEffects(seed, EFFECTS);          // the night's 3 or 4 effects, one per family
buildEffects(seed, sky);             // [{effect, state}] for those picks
buildEffects(seed, sky, EFFECTS);    // every effect built, for the cap test
```

`picker.js` holds `pickEffects`: a seeded shuffle of the registry, walked until 3 or 4 are taken, skipping any whose family is taken already. Over a year every effect comes up many times.

## The effect contract

One module per effect, default-exporting:

```js
export default {
  name: "fireflies",         // unique; what the picker and tests report
  family: "fireflies",       // a night never gets two of one family
  layer: "front",            // "behind" draws before the stars; default "front"
  build(next, sky) {},       // seeded state from `next()` (random.js) and the pure sky
  adjust(state, frame) {},   // optional: returns frame overrides (zoom, bandGain, nebulaTints, rotation)
  draw(context, state, frame) {},  // optional: paints, inside its own save/restore
};
```

`frame` is the placed frame from `geometry.js` (`t` in sky seconds, `rotation`, `width`, `height`, `scale`, the pivot, `px` for 1080p sizes). Effects paint only through `paint.js`, so the per-channel cap holds whatever they draw, and every change in brightness is a ramp from `timing.js` (`envelope`, `swell`) of at least 2.5 s: nothing flashes or jumps. Schedules of occasional events (`eventAt`) draw each event's details from `eventRandom(seed, index)`, so a reload mid-event shows the same event. Things that turn with the sky are placed or anchored inside `safeRadius(sky)` (`geometry.js`), the circle about the pivot that stays on the board however far the sky turns, so an effect is never off the board for the night; things that cross the board use `crossing` and `crossingPoint`.

## The pool

| Folder | Effect (family) | What it does |
|---|---|---|
| `stars/` | constellations (constellations) | faint warm lines joining nearby bright stars, one figure at a time, fading in and out every 4 to 6 min |
| | planets (planets) | 1 or 2 steady amber and warm-white points that never twinkle |
| | twinkle-groups (twinkle) | 3 clusters of neighbours that pulse together |
| | heartbeat-star (heartbeat) | a hero's halo swells over 2.5 s and fades over 4 s, once a minute |
| | hour-marker (hour-marker) | a steady gold star low on the board whose halo swells on the hour |
| `motion/` | rotation (rotation) | the sky turns once every 6 h instead of once a day |
| | star-trails (rotation) | a short fading arc behind each hero along the turn |
| | zoom-out (zoom) | the sky shrinks 1% about its pivot over the night |
| `glow/` | band-breath (milkyway) | the Milky Way's glow swells and fades by a third over 10 min |
| | hue-crossfade (nebula-hue) | each cloud drifts to a second hue (never its own) and back over about 5 min |
| | aurora (aurora) | a ribbon of swaying crimson, magenta and violet strokes along one edge |
| | galaxies (galaxies) | 2 or 3 small tilted smudges that resolve and fade over 20 min |
| `bodies/` | satellite (satellite) | a point crosses in 90 s every 7 to 10 min, with a gentle glint half way |
| | comet (comet) | a gold head with a long soft tail crosses over 90 s every 17 to 23 min |
| `weather/` | cloud (weather) | a thin cloud with a warm rim drifts across over 3 min, dimming the stars under it |
| | fog (weather) | a warm-grey haze along the bottom that slowly rises and settles |
| | snow (snow) | 100 to 140 soft flakes in three size tiers (bigger is nearer and faster), 2.5 to 4 px at 1080p, crossing the board in 20 to 60 s |
| `motes/` | fireflies (fireflies) | 6 to 10 amber points low on the board, each glowing up over 2.5 s and fading over 3 s on its own rhythm |
| | dust-motes (motes) | small specks in a cloud's core hue drifting in front of it |

The moon isn't in the pool: it shows every night (`../moon.js`).

## Depends on

`../random.js`, `../paint.js`, `../timing.js`, `../geometry.js` and `../sky.js` (its colour tables). Nothing outside `night/`.
