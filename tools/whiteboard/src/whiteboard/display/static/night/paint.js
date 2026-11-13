// Light for the night sky (night.js): the per-channel brightness cap and the helpers that
// keep every light under it. draw.js and every effect in effects/ paint through these,
// so the cap holds whatever is drawn.

// The brightest each channel may be, in [0, 1]: red 42%, green 30%, blue 25%. Blue is the
// channel that suppresses melatonin, so it keeps the old flat 25% cap; green, the main
// contributor to brightness, barely moves; red gets headroom because it hardly affects
// sleep and is what reads as colour against the projector's blue-grey black level.
// Every light is a colour at or under this cap drawn with normal (source-over) blending,
// which never pushes a channel past its cap, whatever overlaps.
export const CHANNEL_PEAK = [0.42, 0.3, 0.25];

// A soft radial falloff, [position, weight]: full at the centre, nothing at the edge.
export const SOFT_STOPS = [[0, 1], [0.35, 0.4], [1, 0]];

/**
 * A CSS colour for `rgb` (per channel in [0, 1]) at the brightness cap, with `alpha`.
 */
export function lightCss(rgb, alpha) {
  const [red, green, blue] = rgb.map((channel, i) => Math.round(channel * CHANNEL_PEAK[i] * 255));
  return `rgba(${red}, ${green}, ${blue}, ${alpha})`;
}

/**
 * Fill a disk at the origin fading from `alpha` at its centre to nothing at `radius`, in
 * `rgb` at the cap. Scale the context first for an oval.
 */
export function fillSoftDisk(context, radius, rgb, alpha) {
  const gradient = context.createRadialGradient(0, 0, 0, 0, 0, radius);
  for (const [position, weight] of SOFT_STOPS) {
    gradient.addColorStop(position, lightCss(rgb, weight * alpha));
  }
  context.globalAlpha = 1;
  context.fillStyle = gradient;
  context.fillRect(-radius, -radius, 2 * radius, 2 * radius);
}

/**
 * A soft disk (fillSoftDisk) centred on (x, y): a halo around a star or a point.
 */
export function fillHalo(context, x, y, radius, rgb, alpha) {
  context.save();
  context.translate(x, y);
  fillSoftDisk(context, radius, rgb, alpha);
  context.restore();
}

/**
 * Fill a disk of `radius` at (x, y) in `rgb` at the cap with `alpha`: a star or a point.
 */
export function fillDot(context, x, y, radius, rgb, alpha) {
  context.globalAlpha = alpha;
  context.fillStyle = lightCss(rgb, 1);
  context.beginPath();
  context.arc(x, y, radius, 0, 2 * Math.PI);
  context.fill();
  context.globalAlpha = 1;
}

/**
 * `a` blended towards `b` (both per channel in [0, 1]) by `amount` in [0, 1].
 */
export function mixRgb(a, b, amount) {
  return a.map((channel, i) => channel + (b[i] - channel) * amount);
}
