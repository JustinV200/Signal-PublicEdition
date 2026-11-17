// The idle view's numbers (refdocs/research/idle-board/design.md sections 2 and 4): the
// grid in design pixels, rows per region, and the colour roles. The view is drawn at
// DESIGN size and scaled onto the board (idle.js fitIdle). Course chip names and colours
// come with the data from the daemon (whiteboard/idle/chips.py), so a new course needs
// no change here.

export const DESIGN = { width: 1112, height: 720 };

export const LAYOUT = {
  // The corner ticks sit in the margin ring, just outside the content (40 px margin).
  ticks: { x: 28, y: 34, w: 1056, h: 656 },
  dial: { x: 40, y: 54, w: 96, h: 96 },
  clock: { x: 148, y: 48, w: 240, h: 108 },
  date: { x: 390, y: 56, w: 326, h: 104 },
  weather: { x: 724, y: 54, w: 348, h: 104 },
  topRule: { x: 40, y: 168, w: 1032, h: 1.5 },
  today: { x: 40, y: 186, w: 560, h: 282 },
  notes: { x: 40, y: 484, w: 560, h: 140 },
  divider: { x: 620, y: 186, w: 1, h: 450 },
  // Capped at 4 lines (ending y 360) and UPCOMING starts at 444, around the projector's
  // glare spot (an ellipse at 815, 420); keep the gap even if the spot moves.
  agents: { x: 640, y: 186, w: 432, h: 176 },
  upcoming: { x: 640, y: 444, w: 432, h: 196 },
  footRule: { x: 40, y: 646, w: 1032, h: 1 },
  news: { x: 40, y: 652, w: 1032, h: 28 },
};

// Rows per region; past that, the last slot becomes "+N more".
export const SLOTS = { today: 6, notes: 3, keynotes: 4, agents: 4, upcoming: 5 };

// The task grid's numbers and colours (tasks_grid/items.py). The number and the word
// carry the meaning, so it also works for colourblind users; the colour is a second cue.
export const STATUS = {
  review: { number: 1, word: "review", color: "#00e5ff" },
  building: { number: 2, word: "building", color: "#ffea00" },
  needs_you: { number: 3, word: "YOU", color: "#ff99ff" },
  queued: { number: 4, word: "queued", color: "#ffffff" },
  done: { number: 5, word: "done", color: "#7cff00" },
};

// The due column's colour by "when"; the words (overdue, today, a time, a day) say it too.
export const DUE_COLORS = { overdue: "#ff5252", today: "#ffea00", later: "#cfd8dc" };

// The dial's geometry in its 96-unit box: ring, inner range ring, tick lengths, hands.
export const DIAL = { c: 48, r: 44, range: 28, tick: 5, quarterTick: 8, hour: 22, minute: 32 };
