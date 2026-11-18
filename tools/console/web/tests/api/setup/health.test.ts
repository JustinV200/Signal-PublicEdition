// Health rows from both sources keep their fix and command: the console's own
// checks (GET /api/health's `{rows}`) and the tools' (`setup status --json`).
// A null fix or command reads as "", a row without an id is dropped, and an
// unknown level never reads as a quiet ok.
import { describe, expect, it } from "vitest";
import { parseHealth } from "../../../src/api";
// On purpose beside the setup parser's tests: one table covers both parsers' rows.
import { parseConsoleHealth } from "../../../src/api/parse";

const FIX = "Add the console's hooks with setup, then restart Claude Code.";
const COMMAND = String.raw`.\setup.cmd console`;

describe("health rows", () => {
  it.each([
    [
      "console",
      (rows: unknown[]) => parseConsoleHealth({ rows }),
      {
        id: "turn-hook",
        name: "Turn hook",
        level: "fail",
        state: "missing",
        words: "Not registered.",
      },
      { level: "fail", state: "missing" },
      { level: "attention" },
    ],
    [
      "tools",
      parseHealth,
      { id: "mail", name: "Gmail", state: "down", words: "No Gmail account is signed in." },
      { state: "down" },
      { state: "not_set_up" },
    ],
  ])("%s rows keep fix and command", (_source, parse, row, kept, oddDefault) => {
    const parsed = parse([
      { ...row, fix: FIX, command: COMMAND },
      { ...row, id: "plain", fix: null, command: null },
      { ...row, id: "odd", level: "weird", state: "weird" },
      { name: "no id" },
    ]);
    expect(parsed.map((item) => item.id)).toEqual([row.id, "plain", "odd"]);
    expect(parsed[0]).toMatchObject({ ...kept, words: row.words, fix: FIX, command: COMMAND });
    expect(parsed[1]).toMatchObject({ fix: "", command: "" });
    expect(parsed[2]).toMatchObject(oddDefault);
  });
});
