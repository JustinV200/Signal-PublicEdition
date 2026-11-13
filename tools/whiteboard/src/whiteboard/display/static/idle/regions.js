// The idle view's data regions (today's tasks, keynotes or else priorities, agent tasks,
// upcoming dates, the news footer with its ticker), each built from its slice of the daemon's payload
// (whiteboard/daemon/idle/controller.py). Overflow and empty states follow design.md
// section 5: past a region's slots its last row is "+N more"; with nothing to show it
// says so, and it keeps its place so the layout never shifts.

import { DUE_COLORS, LAYOUT, SLOTS, STATUS } from "./layout.js";
import { bold, chipColumn, div, empty, fitRows, fitting, labelRow, more, region, span } from "./parts.js";
import { clearTicker, tickerElement } from "./ticker.js";

// `animated` holds the ids of tasks that just turned done: they get the TODO view's
// cross-out animation once. `overdue` counts every open overdue item, shown or not.
export function todayRegion(tasks, animated, overdue) {
  const el = region("today", LAYOUT.today);
  const dueToday = tasks.filter((t) => t.when === "today" && !t.done).length;
  el.append(labelRow("Today", tasks.length ? `· ${overdue} overdue · ${dueToday} today` : ""));
  if (!tasks.length) {
    el.append(empty("Nothing due today"));
    return el;
  }
  const { shown, hidden } = fitRows(tasks, SLOTS.today);
  el.append(...shown.map((task) => taskRow(task, animated.has(task.id))));
  if (hidden) el.append(more(hidden));
  return el;
}

function taskRow(task, isAnimated) {
  const row = div("task-row");
  row.style.setProperty("--tag-color", task.chip?.color ?? "#ffffff");
  row.style.setProperty("--due-color", DUE_COLORS[task.when] ?? DUE_COLORS.later);
  row.classList.toggle("done", Boolean(task.done));
  row.classList.toggle("just-done", isAnimated);
  row.append(chipColumn(task.chip), fitting("text", task.text), span("due", task.due));
  return row;
}

// Today's keynotes (AI-written each morning), in the priorities' place; one plain line
// each, behind the same left rule as the priorities.
export function keynotesRegion(lines) {
  const el = region("notes", LAYOUT.notes);
  el.append(labelRow("Keynotes", "· today"));
  const rows = div("note-rows");
  for (const line of lines.slice(0, SLOTS.keynotes)) rows.append(span("keynote-row cut", line));
  el.append(rows);
  return el;
}

export function notesRegion(notes) {
  const el = region("notes", LAYOUT.notes);
  el.append(labelRow("Priorities", ""));
  if (!notes.length) {
    el.append(empty("No priorities this week"));
    return el;
  }
  const rows = div("note-rows");
  for (const note of notes.slice(0, SLOTS.notes)) {
    const row = div("note-row");
    row.style.setProperty("--tag-color", note.chip?.color ?? "#ffffff");
    row.append(chipColumn(note.chip), fitting("text", note.text));
    rows.append(row);
  }
  el.append(rows);
  return el;
}

export function agentsRegion(agents) {
  const el = region("agents", LAYOUT.agents);
  const counts = agents ? `· ${agents.active.length} active · ${agents.queued} queued · ${agents.done} done` : "";
  el.append(labelRow("Agents", counts));
  if (!agents || !agents.active.length) {
    el.append(empty("No agent tasks"));
    return el;
  }
  const { lines, hidden } = agentLines(agents.active, SLOTS.agents);
  el.append(...lines);
  if (hidden) el.append(more(hidden));
  return el;
}

// One line per task, plus a "YOU:" line under the first task that needs the owner. Past
// `slots` lines the last slot is "+N more", N counting tasks whose row isn't shown.
function agentLines(active, slots) {
  const lines = [];
  let youShown = false;
  for (const task of active) {
    lines.push({ el: agentRow(task), task });
    if (task.you && task.status === "needs_you" && !youShown) {
      lines.push({ el: youLine(task.you), task: null });
      youShown = true;
    }
  }
  if (lines.length <= slots) return { lines: lines.map((l) => l.el), hidden: 0 };
  const kept = lines.slice(0, slots - 1);
  const shownTasks = kept.filter((l) => l.task).length;
  return { lines: kept.map((l) => l.el), hidden: active.length - shownTasks };
}

function agentRow(task) {
  const status = STATUS[task.status] ?? STATUS.building;
  const row = div("agent-row");
  row.style.setProperty("--status-color", status.color);
  const statusChip = span("status-chip cut");
  statusChip.append(bold(String(status.number)), document.createTextNode(status.word));
  const bar = span("bar");
  const fill = document.createElement("i");
  fill.style.width = `${Math.max(0, Math.min(100, task.pct))}%`;
  bar.append(fill);
  row.append(statusChip, span("name cut", task.name), span("pct", `${task.pct}%`), bar);
  return row;
}

function youLine(text) {
  const line = div("you-line cut");
  line.append(bold("YOU:"), document.createTextNode(text));
  return line;
}

export function upcomingRegion(events) {
  const el = region("upcoming", LAYOUT.upcoming);
  el.append(labelRow("Upcoming", ""));
  if (!events.length) {
    el.append(empty("No dates this week"));
    return el;
  }
  const { shown, hidden } = fitRows(events, SLOTS.upcoming);
  el.append(...shown.map((event, index) => eventRow(event, index === 0)));
  if (hidden) el.append(more(hidden));
  return el;
}

// Day, chip, title. The first row carries the console's "next" glyph.
function eventRow(event, isNext) {
  const row = div("event-row");
  row.style.setProperty("--tag-color", event.chip?.color ?? "#ffffff");
  const day = span(event.today ? "day today cut" : "day cut", event.day);
  const title = span("title cut");
  if (isNext) title.append(span("next", "▸"));
  title.append(document.createTextNode(event.text));
  row.append(day, chipColumn(event.chip), title);
  return row;
}

// NEWS, the scrolling headlines (ticker.js), then the source name; only the middle moves.
export function newsFooter(news) {
  const el = region("news", LAYOUT.news);
  el.append(span("hud", "News"));
  if (!news) {
    clearTicker();
    el.append(span("headline meta", "No headline"));
    return el;
  }
  el.append(tickerElement(news), span("meta", news.source));
  return el;
}
