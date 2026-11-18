// What a setup command's log shows instead of its raw output: the program
// lines as they are, and in place of each JSON document the words it holds
// (its `messages`, the `notes` of `setup wire`, the lines of a samples
// report). The rest of the JSON is data for the wizard, so it never shows.
// Exit 3 (needs you) is worded from the last document's first message.
import { outputParts } from "../../../api";
import type { OutputPart } from "../../../api";

/** Exit 3's result line on its own, when no log shows under it. */
export const NEEDS_YOU = "! needs you";
// Exit 3's result line when the output gives no message to quote but shows lines
// (the log sits under the result line).
const NEEDS_YOU_SEE_LOG = `${NEEDS_YOU}: see the log below`;

/** The strings in `value` when it is an array (others dropped), else none. */
function strings(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : [];
}

/**
 * The human lines one JSON document holds: an array's strings (`samples
 * files` reports `added x` / `skipped y: why`), or an object's `messages` and
 * `notes`; with no messages, `setup mark`'s `placeholders_left` is worded.
 */
function docLines(doc: unknown): string[] {
  if (Array.isArray(doc)) return strings(doc);
  if (typeof doc !== "object" || doc === null) return [];
  const fields = doc as Record<string, unknown>;
  const lines = [...strings(fields.messages), ...strings(fields.notes)];
  const left = strings(fields.placeholders_left);
  if (!("messages" in fields) && left.length) lines.push(`Placeholders left: ${left.join(", ")}`);
  return lines;
}

// How indent=2 JSON of a non-empty object or array begins: the bracket alone.
const DOC_STARTS = new Set(["{", "["]);

/**
 * Where a JSON document that has begun but not yet closed starts in `parts`
 * (its lines are still plain there), or `parts.length` when none is open.
 */
function openDocStart(parts: readonly OutputPart[]): number {
  for (let i = parts.length - 1; i >= 0; i--) {
    const part = parts[i];
    if (typeof part !== "string") break; // a whole document: nothing after it is open yet
    if (DOC_STARTS.has(part)) return i;
  }
  return parts.length;
}

/**
 * The log as it shows: plain lines, and each JSON document as its words.
 * A document that has begun but not closed stays hidden: while the command
 * runs it may be part-way through streaming, and once it has ended it is a
 * document cut short, still JSON (the raw lines go to Claude on a failure).
 */
export function readableLines(lines: readonly string[]): string[] {
  const parts = outputParts(lines);
  return parts
    .slice(0, openDocStart(parts))
    .flatMap((part) => (typeof part === "string" ? [part] : docLines(part.json)));
}

/**
 * Exit 3's result line: `! needs you: <first message>` of the last JSON
 * document; with none, it points at the log, or is bare when the log is empty.
 */
export function needsYouWords(lines: readonly string[]): string {
  const docs = outputParts(lines).filter((part) => typeof part !== "string");
  const last = docs.at(-1);
  // A message can span lines (a manual step's text, then its details): quote the first.
  const first = last ? docLines(last.json)[0]?.trim().split("\n")[0] : undefined;
  if (first) return `${NEEDS_YOU}: ${first}`;
  return readableLines(lines).length ? NEEDS_YOU_SEE_LOG : NEEDS_YOU;
}
