// Where each blip's label goes, and which labels a crowded face hides. Labels
// are horizontal, beside their mark, pointing towards the centre first (where
// the face is widest) and away from it when that side is blocked. Each is cut
// with an ellipsis (a task keeps its percent) to stop short of the rim and of
// anything already placed on its line. Blips come in priority order; a label
// that can't keep MIN_LABEL_CHARS of its words on either side hides (its mark
// stays, with the full words as a hover title). A pinned label (Claude's, the
// needs-you count's) is not fitted around the others: it always shows whole in
// its first spot, on a line the scope keeps clear for it, and the rest are laid
// out around it. Pure geometry; the text is monospace, so its width is its
// length times CHAR_WIDTH.
import { CENTER, polar, RADIUS } from "./geometry";
import type { Blip } from "./types";

export type Anchor = "start" | "middle" | "end";

/** A line of text on the radar: its words, baseline position and anchor. */
export interface PlacedText {
  text: string;
  x: number;
  y: number;
  anchor: Anchor;
}

export interface Box {
  x0: number;
  x1: number;
  y0: number;
  y1: number;
}

type Spot = Omit<PlacedText, "text">;

// One monospace character at the largest --font-small (14px at 4K; 13px elsewhere).
const CHAR_WIDTH = 8.4;
const ASCENT = 11;
const DESCENT = 4;
const LABEL_GAP = 11;
const LABEL_BASELINE = 4;
const CENTER_LABEL_DROP = 20;
// Clear space kept between a label and the rim or whatever it stops at.
const PADDING = 4;
const MARK_HALF = 6;
// Past this an unpinned label crowds the face; the hover title has the rest.
const MAX_LABEL_CHARS = 28;
// A label cut shorter than this says too little to be worth the space.
const MIN_LABEL_CHARS = 4;
const ELLIPSIS = "…";

/** The box a line of text covers. */
export function boxOf({ text, x, y, anchor }: PlacedText): Box {
  const width = text.length * CHAR_WIDTH;
  const x0 = anchor === "start" ? x : anchor === "end" ? x - width : x - width / 2;
  return { x0, x1: x0 + width, y0: y - ASCENT, y1: y + DESCENT };
}

const overlaps = (a: Box, b: Box) => a.x0 < b.x1 && b.x0 < a.x1 && a.y0 < b.y1 && b.y0 < a.y1;

// Room from the text's start to the rim, on the line at baseline `y`.
function roomInRim({ x, y, anchor }: Spot): number {
  const dy = Math.max(Math.abs(y - ASCENT - CENTER), Math.abs(y + DESCENT - CENTER));
  if (dy >= RADIUS - PADDING) return 0;
  const half = Math.sqrt(RADIUS ** 2 - dy ** 2) - PADDING;
  if (anchor === "middle") return 2 * half;
  return anchor === "end" ? x - (CENTER - half) : CENTER + half - x;
}

// Room from the text's start to the first box on its line, in its direction.
function roomBeforeTaken(spot: Spot, taken: readonly Box[]): number {
  let room = Infinity;
  for (const box of taken) {
    if (box.y1 <= spot.y - ASCENT || box.y0 >= spot.y + DESCENT) continue;
    const isAhead = spot.anchor === "start" ? box.x1 > spot.x : box.x0 < spot.x;
    if (!isAhead) continue;
    const gap = spot.anchor === "start" ? box.x0 - spot.x : spot.x - box.x1;
    room = Math.min(room, gap - PADDING);
  }
  return Math.max(0, room);
}

/** `label` + `tail` in at most `maxChars`, the label cut with an ellipsis; null when under `minKeep` of it would show. */
function fitText(blip: Blip, maxChars: number, minKeep: number): string | null {
  const tail = blip.tail ?? "";
  const whole = `${blip.label}${tail}`;
  if (whole.length <= maxChars) return whole;
  const keep = maxChars - tail.length - ELLIPSIS.length;
  return keep < minKeep ? null : `${blip.label.slice(0, keep).trimEnd()}${ELLIPSIS}${tail}`;
}

// The places a blip's label may go, best first.
function candidates(blip: Blip): Spot[] {
  const at = polar(blip.bearingDeg, blip.range);
  if (blip.range === 0) return [{ x: at.x, y: at.y + CENTER_LABEL_DROP, anchor: "middle" }];
  const y = at.y + LABEL_BASELINE;
  const inward: Anchor = at.x > CENTER ? "end" : "start";
  const place = (anchor: Anchor): Spot => ({
    x: anchor === "end" ? at.x - LABEL_GAP : at.x + LABEL_GAP,
    y,
    anchor,
  });
  return [place(inward), place(inward === "end" ? "start" : "end")];
}

function markBox(blip: Blip): Box {
  const at = polar(blip.bearingDeg, blip.range);
  return { x0: at.x - MARK_HALF, x1: at.x + MARK_HALF, y0: at.y - MARK_HALF, y1: at.y + MARK_HALF };
}

// The first place the label fits, cut short of the rim and of everything taken; null if none.
function firstClear(blip: Blip, taken: readonly Box[]): PlacedText | null {
  const minKeep = Math.min(MIN_LABEL_CHARS, blip.label.length);
  for (const spot of candidates(blip)) {
    const room = Math.min(roomInRim(spot), MAX_LABEL_CHARS * CHAR_WIDTH);
    // A centred label can't stop short on one side, so it only checks for overlaps.
    const clear = spot.anchor === "middle" ? room : Math.min(room, roomBeforeTaken(spot, taken));
    const text = fitText(blip, Math.floor(clear / CHAR_WIDTH), minKeep);
    if (text === null) continue;
    const placed = { ...spot, text };
    if (!taken.some((box) => overlaps(box, boxOf(placed)))) return placed;
  }
  return null;
}

// A pinned label's place, whatever else is on the face: its first spot, cut only to the rim (or just its tail).
function forced(blip: Blip): PlacedText {
  const [spot] = candidates(blip);
  const text =
    fitText(blip, Math.floor(roomInRim(spot) / CHAR_WIDTH), 1) ?? (blip.tail ?? "").trim();
  return { ...spot, text };
}

/**
 * The labels that show, by blip id, for `blips` in priority order; `fixed` are
 * boxes no label may cover (captions). A blip with no entry has its label hidden.
 */
export function layoutLabels(
  blips: readonly Blip[],
  fixed: readonly Box[],
): Map<string, PlacedText> {
  const taken: Box[] = [...fixed, ...blips.map(markBox)];
  const shown = new Map<string, PlacedText>();
  for (const blip of blips) {
    // A pinned label is never cut short of a neighbour or hidden; its builder keeps its line clear.
    const placed = blip.isLabelPinned ? forced(blip) : firstClear(blip, taken);
    if (!placed) continue;
    shown.set(blip.id, placed);
    taken.push(boxOf(placed));
  }
  return shown;
}
