// The idle view's top-left band: a scope-style dial, the HH:MM clock and the date, all
// from the PC's own clock. They change once a minute, on the minute (a timer set to the
// next boundary each time, so it never drifts), and never show seconds: the daemon
// counts each minute boundary as a page change for the camera (display/server/board/
// minute.py), so the flip never looks like someone drawing.

import { DIAL, LAYOUT } from "./layout.js";
import { placed, region, span, svgElement } from "./parts.js";

// Fixed English names, so the page never depends on the browser's locale.
const WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
  "September", "October", "November", "December"];
const MS_PER_MINUTE = 60_000;

// The elements the minute tick updates (the last ones built), and the pending timer.
let parts = null;
let timer = null;

// Build the dial, the clock and the date block (with the usage line under the date) for
// `now`, and keep them so the minute tick can update them in place.
export function clockElements(now, usage) {
  const dial = dialElement();
  const clock = region("clock", LAYOUT.clock);
  const weekday = span("hud");
  const day = span("date-day cut");
  const date = region("date-block", LAYOUT.date);
  date.append(weekday, day);
  if (usage) date.append(span("meta cut", usageText(usage)));
  parts = { dial, clock, weekday, day };
  showTime(now);
  return [dial.svg, clock, date];
}

// Start the minute tick (once); each tick redraws the time on the kept elements.
export function startClock() {
  if (timer !== null) return;
  const schedule = () => {
    const now = new Date();
    const wait = MS_PER_MINUTE - (now.getSeconds() * 1000 + now.getMilliseconds());
    timer = setTimeout(() => {
      showTime(new Date());
      schedule();
    }, wait);
  };
  schedule();
}

function showTime(now) {
  if (!parts) return;
  const hours = now.getHours();
  const minutes = now.getMinutes();
  parts.clock.textContent = `${pad(hours)}:${pad(minutes)}`;
  parts.weekday.textContent = WEEKDAYS[now.getDay()];
  parts.day.textContent = `${now.getDate()} ${MONTHS[now.getMonth()]}`;
  rotate(parts.dial.hour, ((hours % 12) + minutes / 60) * 30);
  rotate(parts.dial.minute, minutes * 6);
}

// "Claude 5h 42% · wk 18% · 5 agents"; "--" for a window that's unknown.
function usageText(usage) {
  const pct = (value) => (value === null || value === undefined ? "--" : `${value}%`);
  const agents = `${usage.agents} agent${usage.agents === 1 ? "" : "s"}`;
  return `Claude 5h ${pct(usage.five_hour)} · wk ${pct(usage.week)} · ${agents}`;
}

// Ring, inner range ring, 12 ticks, hour and minute hands, centre pin. No seconds hand.
function dialElement() {
  const svg = svgElement("svg", { viewBox: "0 0 96 96", class: "dial" });
  const { c, r } = DIAL;
  svg.append(svgElement("circle", { cx: c, cy: c, r, class: "ring" }));
  svg.append(svgElement("circle", { cx: c, cy: c, r: DIAL.range, class: "range" }));
  const ticks = svgElement("g", { class: "ticks" });
  for (let i = 0; i < 12; i++) {
    const length = i % 3 === 0 ? DIAL.quarterTick : DIAL.tick;
    ticks.append(svgElement("line", { x1: c, y1: c - r, x2: c, y2: c - r + length, transform: `rotate(${i * 30} ${c} ${c})` }));
  }
  const hour = svgElement("line", { x1: c, y1: c, x2: c, y2: c - DIAL.hour, class: "hand-hour" });
  const minute = svgElement("line", { x1: c, y1: c, x2: c, y2: c - DIAL.minute, class: "hand-minute" });
  svg.append(ticks, hour, minute, svgElement("circle", { cx: c, cy: c, r: 2.5, class: "pin" }));
  placed(svg, LAYOUT.dial);
  return { svg, hour, minute };
}

function rotate(hand, angle) {
  hand.setAttribute("transform", `rotate(${angle} ${DIAL.c} ${DIAL.c})`);
}

function pad(value) {
  return String(value).padStart(2, "0");
}
