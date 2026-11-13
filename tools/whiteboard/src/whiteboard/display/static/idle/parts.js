// The small pieces every idle region is built from: label rows, chips, "+N more" and
// empty lines, placement and DOM helpers. Every string goes in with textContent: plan
// text, task names, calendar titles and the headline are never parsed as HTML.

const SVG_NS = "http://www.w3.org/2000/svg";
// Where a too-long row is cut before its ellipsis: the first ":", ";" or " (" that leaves
// at least MIN_HEAD_CHARS (8). The floor guards against cuts like "A24 Graphs:", so
// "A24 Graphs: Traversal Part 1" keeps its ellipsis instead of shrinking to "A24 Graphs".
// It's lower than the daemon's short_title floor (20): titles arrive already shortened,
// so this only trims what still overflows the row's width.
const CUT_MARKS = [":", ";", " ("];
const MIN_HEAD_CHARS = 8;

// A region's first row: label, counts, then a thin rule to the region's edge.
export function labelRow(title, counts) {
  const row = div("label-row");
  row.append(span("hud", title));
  if (counts) row.append(span("meta cut", counts));
  row.append(div("rule-fill"));
  return row;
}

// The first `slots` items, or `slots - 1` and how many are hidden.
export function fitRows(items, slots) {
  if (items.length <= slots) return { shown: items, hidden: 0 };
  return { shown: items.slice(0, slots - 1), hidden: items.length - (slots - 1) };
}

// A course chip ({label, color} from the daemon, or null) in its fixed-width column,
// so the text after it lines up across rows.
export function chipColumn(chip) {
  const col = div("chip-col");
  if (chip) col.append(span("chip", chip.label));
  return col;
}

export function more(count) {
  return span("more", `+${count} more`);
}

export function empty(text) {
  return span("empty", text);
}

// A text cell that, when it overflows its row, is cut at its first CUT_MARKS (then the
// CSS ellipsis takes over); fitTexts does the cutting once the board is laid out.
export function fitting(cls, text) {
  return span(`${cls} cut fit`, text);
}

// Cut every overflowing `.fit` cell under `root` (see fitting). Needs layout, so the
// board must be in the document; a hidden (visibility) layer still lays out.
export function fitTexts(root) {
  for (const el of root.querySelectorAll(".fit")) {
    if (el.scrollWidth <= el.clientWidth) continue;
    const text = el.textContent;
    const cuts = CUT_MARKS.map((mark) => text.indexOf(mark, MIN_HEAD_CHARS)).filter((index) => index > 0);
    if (cuts.length) el.textContent = text.slice(0, Math.min(...cuts));
  }
}

export function rule(box, cls) {
  return placed(div(cls), box);
}

export function region(cls, box) {
  return placed(div(`region ${cls}`), box);
}

// Absolutely position `el` at a LAYOUT box, in design pixels.
export function placed(el, { x, y, w, h }) {
  Object.assign(el.style, { position: "absolute", left: `${x}px`, top: `${y}px`, width: `${w}px`, height: `${h}px` });
  return el;
}

export function svgElement(name, attributes) {
  const el = document.createElementNS(SVG_NS, name);
  for (const [key, value] of Object.entries(attributes)) el.setAttribute(key, value);
  return el;
}

export function div(cls) {
  const el = document.createElement("div");
  el.className = cls;
  return el;
}

export function span(cls, text) {
  const el = document.createElement("span");
  el.className = cls;
  if (text !== undefined) el.textContent = text;
  return el;
}

export function bold(text) {
  const el = document.createElement("b");
  el.textContent = text;
  return el;
}
