// The idle view's weather block: a line-drawn glyph, the temperature, then a words
// column (condition, high and low, rain chance, and the place, or "as of" when the
// reading is an older cached one). Glyphs are thin outlines in a 48-unit box, built
// with createElementNS (no markup strings); the condition word always shows beside
// them, since the owner is colourblind, so a glyph is only a second cue.

import { LAYOUT } from "./layout.js";
import { div, region, span, svgElement } from "./parts.js";

const GLYPH_STROKE = 2.2;
const SUN = "#ffea00";
const LINE = "#ffffff";
const RAIN = "#00e5ff";
const MIST = "#cfd8dc";
// One cloud outline, filled black so a sun or moon behind it is hidden where they overlap
// (black is no light on the board).
const CLOUD_PATH = "M14 36H34A8 8 0 0 0 34 20A11 11 0 1 0 13.5 23.5A6.5 6.5 0 0 0 14 36Z";
const MOON_PATH = "M30 9.2A16 16 0 1 0 30 38.8A16 16 0 0 1 30 9.2Z";

// Glyph, temperature, words. Stale weather adds "as of" and dims; none says so.
export function weatherElement(weather) {
  const el = region("weather", LAYOUT.weather);
  const glyph = div("glyph");
  const words = div("words");
  if (!weather) {
    glyph.append(GLYPHS.unknown());
    words.classList.add("wide");
    words.append(span("condition meta", "Weather unavailable"));
    el.append(glyph, words);
    return el;
  }
  glyph.append(GLYPHS[weatherGlyph(weather.code, weather.is_day)]());
  words.append(span("condition cut", weather.word),
    span("range-line cut", `H ${weather.hi}° L ${weather.lo}°`),
    span("range-line cut", `Rain ${weather.rain}%`));
  if (weather.as_of) {
    words.append(span("meta cut", `as of ${weather.as_of}`));
    el.classList.add("stale");
  } else if (weather.place) {
    words.append(span("meta cut", weather.place));
  }
  el.append(glyph, span("temp", `${weather.temp}°`), words);
  return el;
}

// WMO weather_code (Open-Meteo) -> glyph name. Day and night only differ for clear and
// partly cloudy. Anything unlisted is "cloud", never a blank.
export function weatherGlyph(code, isDay) {
  if (code === null || code === undefined) return "unknown";
  if (code === 0) return isDay ? "sun" : "moon";
  if (code === 1 || code === 2) return isDay ? "partly-day" : "partly-night";
  if (code === 45 || code === 48) return "fog";
  if ((code >= 51 && code <= 67) || (code >= 80 && code <= 82)) return "rain";
  if ((code >= 71 && code <= 77) || code === 85 || code === 86) return "snow";
  if (code >= 95 && code <= 99) return "storm";
  return "cloud";
}

const GLYPHS = {
  sun: () => glyph(sun(24, 24, 9, 8, 0)),
  moon: () => glyph(moon(1, 0, 0)),
  "partly-day": () => glyph(sun(18, 17, 6.5, 5, 180), cloudAt(6, 4)),
  "partly-night": () => glyph(moon(0.55, 6, 2), cloudAt(6, 4)),
  cloud: () => glyph(cloudAt(0, 0)),
  rain: () => glyph(cloudAt(0, -6),
    group({ stroke: RAIN }, [line(17, 34, 14, 41), line(24, 34, 21, 41), line(31, 34, 28, 41)])),
  snow: () => glyph(cloudAt(0, -6),
    group({ stroke: LINE }, [...flake(17, 38), ...flake(25, 38), ...flake(33, 38)])),
  storm: () => glyph(cloudAt(0, -8),
    svgElement("polyline", { stroke: SUN, points: "25,30 20,39 26,39 22,46" })),
  fog: () => glyph(cloudAt(0, -6), group({ stroke: MIST }, [line(13, 36, 35, 36), line(17, 41, 31, 41)])),
  // The console's "disabled" look: dashed. Shown with "Weather unavailable".
  unknown: () => glyph(svgElement("circle", { cx: 24, cy: 24, r: 14, stroke: MIST, "stroke-dasharray": "4 4" })),
};

function glyph(...children) {
  return group({ "stroke-width": GLYPH_STROKE, "stroke-linecap": "round", "stroke-linejoin": "round" },
    children, svgElement("svg", { viewBox: "0 0 48 48", fill: "none" }));
}

function group(attributes, children, parent = svgElement("g", {})) {
  for (const [key, value] of Object.entries(attributes)) parent.setAttribute(key, value);
  parent.append(...children);
  return parent;
}

function line(x1, y1, x2, y2) {
  return svgElement("line", { x1, y1, x2, y2 });
}

// `count` short rays around (cx, cy) from radius r1 to r2, starting at `fromDeg`.
function rays(cx, cy, r1, r2, count, fromDeg = 0, stepDeg = 45) {
  const lines = [];
  for (let i = 0; i < count; i++) {
    const a = ((fromDeg + i * stepDeg) * Math.PI) / 180;
    lines.push(line((cx + r1 * Math.cos(a)).toFixed(1), (cy + r1 * Math.sin(a)).toFixed(1),
      (cx + r2 * Math.cos(a)).toFixed(1), (cy + r2 * Math.sin(a)).toFixed(1)));
  }
  return lines;
}

function sun(cx, cy, r, rayCount, fromDeg) {
  return group({ stroke: SUN }, [svgElement("circle", { cx, cy, r }), ...rays(cx, cy, r + 4, r + 9, rayCount, fromDeg)]);
}

function moon(scale, dx, dy) {
  return group({ stroke: LINE, transform: `translate(${dx} ${dy}) scale(${scale})` },
    [svgElement("path", { d: MOON_PATH })]);
}

// A six-armed snowflake at (cx, cy).
function flake(cx, cy) {
  return rays(cx, cy, 0, 3.5, 6, 0, 60);
}

function cloudAt(dx, dy) {
  return group({ transform: `translate(${dx} ${dy})` },
    [svgElement("path", { fill: "#000", stroke: LINE, d: CLOUD_PATH })]);
}
