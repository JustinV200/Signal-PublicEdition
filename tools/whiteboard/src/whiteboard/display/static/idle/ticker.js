// The NEWS footer's ticker: the daemon's headlines scroll right to left like a TV news
// crawl, in a window between the fixed NEWS label and source name (regions.js). It's a
// conveyor: headlines are appended at the right as the track runs out and dropped at
// the left once they've scrolled off, so the loop is seamless and nothing ever jumps.
// New headlines from the daemon wait for the loop seam (the next time the list starts
// over) before they join. One window lives for the page's life, so a re-render (each
// push replaces the board) moves it rather than restarting it. The daemon's camera
// watcher leaves this band out of its motion check (display/server/board/idle_ticker.py).
// Each headline goes in with textContent.

import { div, span } from "./parts.js";

const SEPARATOR = "•";
// Headline kept queued past the window's right edge, so a new one never pops in.
const LOOKAHEAD_PX = 200;
// A frame gap longer than this (a hidden tab, a blank flash) moves the track no further.
const MAX_FRAME_S = 0.1;
// How often a sleeping ticker (hidden, or still) checks whether to run again.
const WAKE_CHECK_MS = 1000;

const windowEl = div("ticker");
const trackEl = div("ticker-track");
windowEl.append(trackEl);
const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");

let headlines = [];
let pending = null;
let nextIndex = 0;
let offsetPx = 0;
// Width of each headline element on the track, in order, and their sum.
let widths = [];
let trackWidth = 0;
let pxPerS = 0;
let lastFrameMs = null;
// The pending animation frame and wake-up check, or null.
let frameId = null;
let wakeId = null;

// The ticker window for `news` ({headlines, px_s}). The same headlines keep running;
// different ones wait for the seam, unless the track is empty or can't move.
export function tickerElement(news) {
  pxPerS = reducedMotion.matches ? 0 : news.px_s;
  const isSame = JSON.stringify(news.headlines) === JSON.stringify(pending ?? headlines);
  if (!isSame) {
    if (!widths.length || pxPerS === 0) restart(news.headlines);
    else pending = news.headlines;
  }
  wake();
  return windowEl;
}

// Empty the track, for when there are no headlines to show.
export function clearTicker() {
  restart([]);
}

// Empty the track and start `list` from its first headline at the window's left edge.
function restart(list) {
  headlines = list;
  pending = null;
  nextIndex = 0;
  offsetPx = 0;
  widths = [];
  trackWidth = 0;
  trackEl.replaceChildren();
  trackEl.style.transform = "translateX(0px)";
}

// The headline after the last one appended; at the seam a waiting list takes over.
function nextHeadline() {
  if (nextIndex >= headlines.length) {
    nextIndex = 0;
    if (pending) [headlines, pending] = [pending, null];
  }
  return headlines[nextIndex++];
}

// Append headlines until the track reaches LOOKAHEAD_PX past the window's right edge.
function fill() {
  if (!windowEl.clientWidth) return; // not laid out yet; try again next frame
  const needPx = windowEl.clientWidth + LOOKAHEAD_PX;
  while (headlines.length && offsetPx + trackWidth < needPx) {
    const item = span("ticker-item", nextHeadline());
    item.append(span("ticker-sep", SEPARATOR));
    trackEl.append(item);
    // The used width, fractional and in design px whatever the board's scale or warp
    // (flex items; offsetWidth would round and accumulate a jump at each drop).
    const width = parseFloat(getComputedStyle(item).width);
    if (!(width > 0)) {
      // Not laid out (NaN): take it back off so the track and `widths` stay in step.
      item.remove();
      return;
    }
    widths.push(width);
    trackWidth += width;
  }
}

// Drop headlines that have scrolled fully past the left edge, keeping the rest in place.
function dropPassed() {
  while (widths.length && offsetPx + widths[0] <= 0) {
    const width = widths.shift();
    trackEl.firstElementChild.remove();
    offsetPx += width;
    trackWidth -= width;
  }
}

// Whether the window is on the board and visible (not another view, the night sky or a
// blank flash).
function isShown() {
  return windowEl.isConnected && windowEl.checkVisibility({ visibilityProperty: true });
}

// One animation frame: move, drop, fill. Keeps asking for frames only while it's shown
// and moving; otherwise it sleeps (see sleep) so a hidden or still ticker costs nothing.
function frame(nowMs) {
  frameId = null;
  if (!isShown()) {
    sleep();
    return;
  }
  const stepS = lastFrameMs === null ? 0 : Math.min((nowMs - lastFrameMs) / 1000, MAX_FRAME_S);
  lastFrameMs = nowMs;
  offsetPx -= pxPerS * stepS;
  dropPassed();
  fill();
  trackEl.style.transform = `translateX(${offsetPx}px)`;
  if (pxPerS > 0) frameId = requestAnimationFrame(frame);
  else sleep();
}

// Stop the frame loop and look again in WAKE_CHECK_MS: going back to the idle view may
// only flip body[data-view], with no re-render to wake it. The next frame starts its
// step from zero, so the track never leaps on resuming.
function sleep() {
  lastFrameMs = null;
  if (wakeId === null) wakeId = setTimeout(wake, WAKE_CHECK_MS);
}

// Ask for a frame unless one is already coming. Called early (new data), it cancels the
// pending check, so re-renders while asleep never pile up timers.
function wake() {
  clearTimeout(wakeId);
  wakeId = null;
  if (frameId === null) frameId = requestAnimationFrame(frame);
}

wake();
