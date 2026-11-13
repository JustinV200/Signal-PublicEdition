// The TODO view: draws the daemon's todo payload (whiteboard/todo/view/payload.py) into #todo.
// The daemon has already laid everything out in board pixels, so this only builds boxes.
// Plan text comes from the owner's files: it goes in with textContent only, never as HTML.
// A row that turns done gets an animated cross-out line, then dims (todo.css). Today's
// keynotes, if any, sit in their own block under the header. Only rows
// this page itself showed open before are animated, so a fresh page load never animates.

import { place } from "./dom.js";

const todoEl = document.getElementById("todo");
// Ids of the rows the last render showed not done.
let openIds = new Set();

// Draw the view. `todo` may be null (no sync yet); `newlyDone` lists ids to animate.
export function renderTodo(todo, newlyDone) {
  if (!todo) {
    todoEl.replaceChildren();
    openIds = new Set();
    return;
  }
  const animated = new Set(newlyDone.filter((id) => openIds.has(id)));
  const nodes = [
    header(todo),
    ...todo.headings.map(heading),
    ...todo.rows.map((row) => rowElement(row, todo.metrics, animated.has(row.id))),
  ];
  if (todo.keynotes) nodes.push(keynotes(todo.keynotes));
  if (todo.more) nodes.push(more(todo.more));
  if (todo.note) nodes.push(note(todo));
  todoEl.style.fontSize = `${todo.metrics.font_px}px`;
  todoEl.replaceChildren(...nodes);
  openIds = new Set(todo.rows.filter((row) => !row.done).map((row) => row.id));
}

function header(todo) {
  const box = positioned("todo-header", todo.header);
  box.append(
    span("todo-title", todo.title),
    span("todo-date", todo.date_label),
    span("todo-updated", todo.updated_label),
  );
  return box;
}

function heading(item) {
  const box = positioned("todo-heading", item);
  box.style.color = item.color;
  box.append(span("todo-heading-label", item.label));
  return box;
}

function rowElement(row, metrics, isAnimated) {
  const box = positioned("todo-row", row);
  box.style.setProperty("--tag-color", row.color);
  box.classList.toggle("done", row.done);
  box.classList.toggle("just-done", isAnimated);
  box.classList.toggle("overdue", row.overdue);
  const check = div("todo-check");
  check.style.width = `${metrics.check_w}px`;
  const tag = div("todo-tag");
  Object.assign(tag.style, { left: `${metrics.check_w}px`, width: `${metrics.tag_w}px`,
    fontSize: `${metrics.tag_font_px}px` });
  if (row.tag) tag.append(span("todo-tag-chip", row.tag));
  const text = div("todo-text");
  Object.assign(text.style, { left: `${row.text_x}px`, width: `${row.text_w}px` });
  text.append(span("todo-label", row.text));
  const due = div(row.hint ? "todo-due todo-hint" : "todo-due");
  due.style.fontSize = `${metrics.due_font_px}px`;
  due.append(span("todo-due-label", row.hint ? "done?" : row.due_label));
  box.append(check, tag, text, due);
  return box;
}

// Today's keynotes under the header: a small heading, then one line each (cut, never wrapped).
function keynotes(item) {
  const box = positioned("todo-keynotes", item);
  box.style.fontSize = `${item.font_px}px`;
  box.append(span("todo-keynotes-label", item.label), ...item.lines.map((line) => span("todo-keynote", line)));
  return box;
}

function more(item) {
  const box = positioned("todo-more", item);
  box.append(span("todo-more-label", item.label));
  return box;
}

function note(todo) {
  const box = positioned("todo-note", todo.body);
  box.append(span("todo-note-label", todo.note));
  return box;
}

function positioned(className, { x, y, w, h }) {
  const box = div(className);
  place(box, x, y, w, h);
  return box;
}

function div(className) {
  const element = document.createElement("div");
  element.className = className;
  return element;
}

function span(className, text) {
  const element = document.createElement("span");
  element.className = className;
  element.textContent = text;
  return element;
}
