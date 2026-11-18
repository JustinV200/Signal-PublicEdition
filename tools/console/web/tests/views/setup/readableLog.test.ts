// A setup log never shows the CLI's raw JSON, not even part-way through
// streaming or cut short: each document becomes the words it holds, and exit 3
// quotes the last document's first message.
import { describe, expect, it } from "vitest";
import { needsYouWords, readableLines } from "../../../src/views/setup/run";

/** `data` as the CLI prints it (json.dumps with indent=2), one line each. */
const printed = (data: unknown) => JSON.stringify(data, null, 2).split("\n");

describe("readable setup log", () => {
  it.each([
    {
      what: "apply: a program's lines, then its messages",
      lines: [
        "Resolved 12 packages",
        ...printed({
          tool: "mail",
          step: "email",
          status: "needs_input",
          messages: ["Answer the 'email' step first.\n(Details: x)"],
        }),
      ],
      shown: ["Resolved 12 packages", "Answer the 'email' step first.\n(Details: x)"],
      needsYou: "! needs you: Answer the 'email' step first.",
    },
    {
      what: "samples files: the report's lines, the count's JSON hidden",
      lines: [
        ...printed(["added a.txt", "skipped b.bin: no"]),
        ...printed({ samples: 3, target: "5-15" }),
      ],
      shown: ["added a.txt", "skipped b.bin: no"],
      needsYou: "! needs you: see the log below",
    },
    {
      what: "mark: placeholders left, worded",
      lines: printed({
        tool: "jobs",
        step: "config",
        status: "needs_input",
        placeholders_left: ["email", "name"],
      }),
      shown: ["Placeholders left: email, name"],
      needsYou: "! needs you: Placeholders left: email, name",
    },
    {
      what: "a line that only looks like JSON stays, and the real document after it is read",
      lines: ["[INFO] building", "done", ...printed({ messages: ["Built."] })],
      shown: ["[INFO] building", "done", "Built."],
      needsYou: "! needs you: Built.",
    },
    {
      what: "a document that never closes stays hidden (streaming, or cut short)",
      lines: ["Resolved 12 packages", "{", '  "ran": [],'],
      shown: ["Resolved 12 packages"],
      needsYou: "! needs you: see the log below",
    },
    {
      what: "nothing to show: needs you, pointing at nothing",
      lines: ["{", '  "ran": [],'],
      shown: [],
      needsYou: "! needs you",
    },
  ])("$what", ({ lines, shown, needsYou }) => {
    expect(readableLines(lines)).toEqual(shown);
    expect(needsYouWords(lines)).toBe(needsYou);
  });
});
