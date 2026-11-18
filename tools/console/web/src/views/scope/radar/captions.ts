// The radar's fixed words: each ring's age caption (`now / 1m / 5m`, centred
// on the ring just above the right half's horizontal, where the time-ranged
// sectors meet, leaving the free middle of the face to the labels),
// each sector's name in the corner beside it (outside the rim, so it never
// meets a blip), and the `NO SIGNAL 25s` banner near the top of the face.
import { CENTER, RADIUS, SIZE } from "./geometry";
import type { PlacedText } from "./labels";
import { RINGS, SECTORS } from "./scale";

const RING_CAPTION_LIFT = 4;
const CORNER_INSET = 6;
const CORNER_BASELINE = 16;
// The banner sits this far up the vertical, clear of Claude's centre label.
const SIGNAL_RANGE = 0.55;

/** `now`, `1m`, `5m`, each centred on its ring, just above the line out to 90°. */
export function ringCaptions(): PlacedText[] {
  return RINGS.map(({ fraction, caption }) => ({
    text: caption,
    x: CENTER + RADIUS * fraction,
    y: CENTER - RING_CAPTION_LIFT,
    anchor: "middle",
  }));
}

/** The sector names: VOICE top right, BOARD bottom right, TASKS top left. */
export function sectorNames(): PlacedText[] {
  const right = SIZE - CORNER_INSET;
  return [
    { text: SECTORS.voice.name, x: right, y: CORNER_BASELINE, anchor: "end" },
    { text: SECTORS.board.name, x: right, y: SIZE - CORNER_INSET, anchor: "end" },
    { text: SECTORS.tasks.name, x: CORNER_INSET, y: CORNER_BASELINE, anchor: "start" },
  ];
}

/** The stale-stream banner, centred above the middle of the face. */
export function signalCaption(words: string): PlacedText {
  return { text: words, x: CENTER, y: CENTER - RADIUS * SIGNAL_RANGE, anchor: "middle" };
}
