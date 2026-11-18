// The away state in words: System's YOU says it in full, and the title row
// shows a short form only when the owner isn't Here (nothing while Here or
// unreadable), its end split off so narrow widths can drop it.
import { expect, it } from "vitest";
import type { AwayInfo } from "../../src/api";
import { awayWords, titleAwayWords } from "../../src/status";

const ENDS_AT = "2026-11-19T17:00:00Z";
// The day and clock after it are local time, so only this start is checked.
const UNTIL = "Away until ";
const away = (state: AwayInfo["state"], endsAt: string | null = null): AwayInfo => ({
  state,
  endsAt,
  note: "",
});

// [the away block, YOU's words, the title row's word and whether it has an end (null: nothing)]
const CASES: [string, AwayInfo | null, string | null, [string, boolean] | null][] = [
  ["here", away("here"), "Here", null],
  ["away with an end", away("away", ENDS_AT), UNTIL, ["Away", true]],
  ["away with none", away("away"), "Away (ends by itself in 3 days)", ["Away", false]],
  ["asleep", away("asleep"), "Asleep (sleep mode)", ["Asleep", false]],
  ["unreadable", null, null, null],
];

it.each(CASES)("words the away state: %s", (_name, block, full, title) => {
  if (block && full === UNTIL) expect(awayWords(block).startsWith(UNTIL)).toBe(true);
  else if (block) expect(awayWords(block)).toBe(full);
  const short = titleAwayWords(block);
  expect(short && [short.word, short.until.startsWith(" until ")]).toEqual(title);
});

it("points the title row's tooltip at I'm back only while away", () => {
  expect(titleAwayWords(away("away"))?.tooltip).toContain("I'm back");
  expect(titleAwayWords(away("asleep"))?.tooltip).not.toContain("I'm back");
});
