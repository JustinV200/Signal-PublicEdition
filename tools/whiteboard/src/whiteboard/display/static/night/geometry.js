// Placing the night sky on the canvas (night.js): sky units to pixels for the current
// turn, which stars stay in view through it, and paths across the frame, for draw.js
// and every effect in effects/. The sky is measured in sky units (1 = the canvas height)
// from its pivot, and turns by `frame.rotation`; the Milky Way band has its own frame,
// turned a further `band.normalAngle` (see sky.js).

import { between } from "./random.js";

export const REFERENCE_HEIGHT_PX = 1080; // radii and line widths are given for 1080p
const CULL_MARGIN_PX = 16; // things this far outside the canvas are still drawn (halos show)
// The frame's shape when the sky is built, before any canvas exists: the projector's
// 16:9. shortcut: a board fit much taller than that puts the "safe" circle's sides off
// the board; take the fit's aspect from the page if that ever happens.
const BUILD_ASPECT = 16 / 9;
const SAFE_MARGIN = 0.03; // sky units kept clear of the edge, for halos and the 1% zoom

/**
 * The frame with its placement filled in: `scale` (pixels per sky unit, after `zoom`),
 * the pivot in pixels, the turn's cos and sin, and `px` (pixels per 1080p pixel).
 */
export function placeFrame(sky, frame) {
  return {
    ...frame,
    scale: frame.height * (frame.zoom ?? 1),
    pivotX: sky.pivot.x * frame.width,
    pivotY: sky.pivot.y * frame.height,
    cosR: Math.cos(frame.rotation),
    sinR: Math.sin(frame.rotation),
    px: frame.height / REFERENCE_HEIGHT_PX,
  };
}

/**
 * A point given in sky units from the pivot (before the turn), in canvas pixels: {x, y}.
 */
export function skyToCanvas(skyX, skyY, frame) {
  return {
    x: frame.pivotX + (skyX * frame.cosR - skyY * frame.sinR) * frame.scale,
    y: frame.pivotY + (skyY * frame.cosR + skyX * frame.sinR) * frame.scale,
  };
}

/**
 * A star's place for this turn, in canvas pixels: {x, y}.
 */
export function placeStar(star, frame) {
  return skyToCanvas(star.r * star.cos, star.r * star.sin, frame);
}

/**
 * A star's position in sky units from the pivot, before the turn: {x, y}.
 */
export function starSkyPoint(star) {
  return { x: star.r * star.cos, y: star.r * star.sin };
}

/**
 * The radius about the pivot, in sky units, inside which a point stays on a 16:9 frame
 * however far the sky turns: the pivot's distance to the nearest edge, less a margin.
 * Between 0.07 and 0.47 for the pivots sky.js makes.
 */
export function safeRadius(sky) {
  const { x, y } = sky.pivot;
  const toSide = Math.min(x, 1 - x) * BUILD_ASPECT;
  return Math.max(0, Math.min(toSide, y, 1 - y) - SAFE_MARGIN);
}

/**
 * The sky's stars within `radius` sky units of the pivot (see safeRadius).
 */
export function starsWithin(sky, radius) {
  return sky.stars.filter((star) => star.r <= radius);
}

/**
 * A seeded path across the frame for something that crosses it: {leftToRight, fromY,
 * toY, margin}. `heights` is the range it enters and leaves at, as fractions of the
 * height; `margin` is how far outside the frame it starts and ends, as a fraction of
 * the width; `level` keeps it at one height.
 */
export function crossing(next, { heights, margin, level = false }) {
  const leftToRight = next() < 0.5;
  const fromY = between(next, ...heights);
  return { leftToRight, fromY, toY: level ? fromY : between(next, ...heights), margin };
}

/**
 * Where a crossing is at `progress` in [0, 1]: {x, y} in pixels and {dx, dy}, the unit
 * direction of travel.
 */
export function crossingPoint(path, progress, frame) {
  const span = 1 + 2 * path.margin;
  const across = -path.margin + span * progress;
  const runX = (path.leftToRight ? 1 : -1) * span * frame.width;
  const runY = (path.toY - path.fromY) * frame.height;
  const length = Math.hypot(runX, runY);
  return {
    x: (path.leftToRight ? across : 1 - across) * frame.width,
    y: (path.fromY + (path.toY - path.fromY) * progress) * frame.height,
    dx: runX / length,
    dy: runY / length,
  };
}

/**
 * Whether a canvas point is on the canvas or within the cull margin of it.
 */
export function isInView(x, y, frame) {
  return x >= -CULL_MARGIN_PX && x <= frame.width + CULL_MARGIN_PX
    && y >= -CULL_MARGIN_PX && y <= frame.height + CULL_MARGIN_PX;
}

/**
 * Move the context into the band's frame (save it first): x runs across the band along
 * its normal and y along it, both in pixels (sky units times `frame.scale`).
 */
export function enterBandFrame(context, sky, frame) {
  context.translate(frame.pivotX, frame.pivotY);
  context.rotate(frame.rotation + sky.band.normalAngle);
}
