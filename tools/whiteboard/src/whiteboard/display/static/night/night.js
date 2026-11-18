// The night view's renderer: a dim, seeded night sky for the projector while sleep mode
// runs (tools/sleepmode asks for it with POST /api/night/show {seed}). It draws
// into one canvas inside a container at a capped frame rate and stops cleanly. What
// shows is a pure function of the seed and the clock, so one night always looks the
// same: no network, no model, no Math.random(). The sky is built in sky.js, the moon in
// moon.js, meteors in meteors.js, the night's effects in effects/, and frames in draw.js.
// See README.md for the API and how the page wires it in.

import { drawFrame } from "./draw.js";
import { buildEffects } from "./effects/index.js";
import { createMeteorSchedule } from "./meteors.js";
import { buildMoon } from "./moon.js";
import { buildSky } from "./sky.js";
import { skyTime } from "./timing.js";

export { buildSky };

const FRAME_INTERVAL_MS = 50; // 20 fps at most
const ROTATION_PERIOD_S = 86400; // one turn of the sky a day
const MAX_PIXEL_RATIO = 2;
const REDUCED_MOTION = matchMedia("(prefers-reduced-motion: reduce)");

// One sky per container, so starting again in the same place stops the old one first.
const running = new WeakMap();

/**
 * Show the night view in `container` (a positioned block element) and return a handle
 * {stop()}. `seed` is the night's integer (YYYYMMDD from sleepmode). stop() removes the
 * canvas and every listener and can be called more than once. Throws TypeError on a bad
 * container or seed.
 */
export function startNight(container, { seed } = {}) {
  if (!(container instanceof Element)) {
    throw new TypeError("the night view needs a container element");
  }
  const scene = buildScene(seed);
  running.get(container)?.stop();
  const handle = startSky(container, scene);
  running.set(container, handle);
  return handle;
}

/**
 * Everything one night shows, for a seed: {sky, moon, effects, meteors}, with `effects`
 * the night's picks as [{effect, state}]. Pure, so tests and previews can draw it.
 */
export function buildScene(seed) {
  const sky = buildSky(seed);
  return {
    sky,
    moon: buildMoon(seed),
    effects: buildEffects(seed, sky),
    meteors: createMeteorSchedule(seed),
  };
}

/**
 * Draw the scene as it looks at sky time `t` (seconds, see timing.js) onto a `width` x
 * `height` context: the effects first adjust the frame (zoom, band glow, nebula tints,
 * turn), then draw.js paints it. Under prefers-reduced-motion there is no meteor.
 */
export function renderFrame(context, scene, t, width, height) {
  const frame = {
    t,
    rotation: rotationAt(t),
    width,
    height,
    zoom: 1,
    bandGain: 1,
    nebulaTints: null,
    moon: scene.moon,
    effects: scene.effects,
    meteor: REDUCED_MOTION.matches ? null : scene.meteors.at(t),
  };
  for (const { effect, state } of scene.effects) {
    if (effect.adjust) Object.assign(frame, effect.adjust(state, frame));
  }
  drawFrame(context, scene.sky, frame);
}

function startSky(container, scene) {
  const canvas = addCanvas(container);
  const context = canvas.getContext("2d");
  const draw = () => renderFrame(context, scene, skyTime(), canvas.width, canvas.height);
  const loop = createLoop(draw);
  // Fires once on observe, which is the first draw; after that only on size changes.
  const observer = new ResizeObserver(() => {
    fitCanvas(canvas);
    draw();
  });
  const onVisibility = () => (document.hidden ? loop.pause() : loop.resume());
  observer.observe(canvas);
  document.addEventListener("visibilitychange", onVisibility);
  loop.resume();
  return {
    stop() {
      loop.pause();
      observer.disconnect();
      document.removeEventListener("visibilitychange", onVisibility);
      canvas.remove();
    },
  };
}

// A requestAnimationFrame loop that calls `draw` at most every FRAME_INTERVAL_MS, and
// not at all under prefers-reduced-motion: the sky is then drawn once, on size changes.
function createLoop(draw) {
  let rafId = 0;
  let lastDrawAt = 0;
  function frame(now) {
    rafId = requestAnimationFrame(frame);
    const elapsed = now - lastDrawAt;
    if (elapsed < FRAME_INTERVAL_MS) return;
    // Keep the remainder, so one late vsync doesn't push every later draw back.
    lastDrawAt = now - (elapsed % FRAME_INTERVAL_MS);
    draw();
  }
  return {
    resume() {
      if (!rafId && !REDUCED_MOTION.matches) rafId = requestAnimationFrame(frame);
    },
    pause() {
      cancelAnimationFrame(rafId);
      rafId = 0;
    },
  };
}

function addCanvas(container) {
  const canvas = document.createElement("canvas");
  canvas.className = "night-sky";
  Object.assign(canvas.style, {
    position: "absolute", left: "0", top: "0", width: "100%", height: "100%", display: "block",
  });
  container.append(canvas);
  return canvas;
}

// Match the backing store to the canvas's CSS size at the display's pixel ratio, so
// stars stay crisp on the projector (1280x720 CSS pixels at 150% is 1920x1080).
function fitCanvas(canvas) {
  const ratio = Math.min(devicePixelRatio || 1, MAX_PIXEL_RATIO);
  canvas.width = Math.max(1, Math.round(canvas.clientWidth * ratio));
  canvas.height = Math.max(1, Math.round(canvas.clientHeight * ratio));
}

function rotationAt(t) {
  return (2 * Math.PI * t) / ROTATION_PERIOD_S;
}
