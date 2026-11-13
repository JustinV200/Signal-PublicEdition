// The idle view (the board's default when nothing is drawn): draws the daemon's idle
// payload (whiteboard/daemon/idle/controller.py) into #idle. The board is built at the
// design size (layout.js, 1112x720) and scaled to the stage. Every string goes in with
// textContent. A region whose data changed fades its rows in once; a task that turned
// done since the last render gets the TODO view's cross-out animation. The clock ticks
// here, on the minute (clock.js), and the news footer's headlines scroll (ticker.js).

import { clockElements, startClock } from "./clock.js";
import { DESIGN, LAYOUT } from "./layout.js";
import { div, fitTexts, rule } from "./parts.js";
import { agentsRegion, keynotesRegion, newsFooter, notesRegion, todayRegion, upcomingRegion } from "./regions.js";
import { weatherElement } from "./weather.js";

const idleEl = document.getElementById("idle");
const boardEl = div("idle-board");
idleEl?.append(boardEl);
// Each region's data at the last render, to fade only the ones that changed.
let lastSlices = null;
// Ids of the tasks the last render showed not done.
let openIds = new Set();

// Draw the view from the payload; null (before the daemon's first push) draws nothing.
export function renderIdle(data) {
  if (!data) {
    boardEl.replaceChildren();
    return;
  }
  const animated = new Set(data.tasks.filter((task) => task.done && openIds.has(task.id)).map((task) => task.id));
  const regions = {
    weather: weatherElement(data.weather),
    tasks: todayRegion(data.tasks, animated, data.overdue ?? 0),
    // On days with keynotes they take the priorities' place.
    notes: data.keynotes?.length ? keynotesRegion(data.keynotes) : notesRegion(data.notes),
    agents: agentsRegion(data.agents),
    upcoming: upcomingRegion(data.upcoming),
    news: newsFooter(data.news),
  };
  const sliceOf = { notes: [data.notes, data.keynotes], tasks: [data.tasks, data.overdue] };
  const slices = Object.fromEntries(
    Object.keys(regions).map((key) => [key, JSON.stringify(sliceOf[key] ?? data[key])]),
  );
  for (const [key, el] of Object.entries(regions)) {
    // The news ticker takes new headlines at its loop seam instead (ticker.js).
    if (key !== "news" && lastSlices && lastSlices[key] !== slices[key]) el.classList.add("fresh");
  }
  boardEl.replaceChildren(
    ...cornerTicks(),
    ...clockElements(new Date(), data.usage),
    regions.weather,
    rule(LAYOUT.topRule, "rule-cyan"),
    regions.tasks,
    regions.notes,
    rule(LAYOUT.divider, "rule-faint"),
    regions.agents,
    regions.upcoming,
    rule(LAYOUT.footRule, "rule-faint"),
    regions.news,
  );
  fitTexts(boardEl);
  lastSlices = slices;
  openIds = new Set(data.tasks.filter((task) => !task.done).map((task) => task.id));
  startClock();
}

// Scale the design-size board to fit the stage ({width, height}), centred.
export function fitIdle(stage) {
  const scale = Math.min(stage.width / DESIGN.width, stage.height / DESIGN.height);
  const left = (stage.width - DESIGN.width * scale) / 2;
  const top = (stage.height - DESIGN.height * scale) / 2;
  boardEl.style.transform = `translate(${left}px, ${top}px) scale(${scale})`;
}

// An L at each corner of the ticks rectangle, in the margin ring: a missing tick shows
// the fit is clipped or has drifted.
function cornerTicks() {
  const { x, y, w, h } = LAYOUT.ticks;
  const size = 18;
  const tick = (cls, left, top) => {
    const el = div(`tick ${cls}`);
    Object.assign(el.style, { left: `${left}px`, top: `${top}px` });
    return el;
  };
  return [tick("tl", x, y), tick("tr", x + w - size, y), tick("bl", x, y + h - size), tick("br", x + w - size, y + h - size)];
}
