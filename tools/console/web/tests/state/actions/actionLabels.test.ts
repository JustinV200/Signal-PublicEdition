// A saved board's name is quoted exactly as the server's `_quoted` does
// (the same rows as tools/console/tests/actions/test_plans.py), so a row's
// label never changes when the server's echo lands: shown as typed, with
// quotes, newlines and hidden characters escaped.
import { describe, expect, it } from "vitest";
import { actionLabel } from "../../../src/state";

describe("actionLabel quoting", () => {
  it.each([
    ['lab "2"', 'Send to projector: "lab \\"2\\""'],
    ["café ☕", 'Send to projector: "café ☕"'],
    ["a\u202eb\u200bc\n", 'Send to projector: "a\\u202eb\\u200bc\\n"'],
    ["x\u{e0001}", 'Send to projector: "x\\udb40\\udc01"'],
    ["lab\u3164", 'Send to projector: "lab\\u3164"'],
    ["\ud800\x7f", 'Send to projector: "\\ud800\\u007f"'],
  ])("%j reads %s", (name, label) => {
    expect(actionLabel("board.load", { name })).toBe(label);
  });

  // Reads like the button clicked, and the same as the server's (test_plans.py).
  it("labels a live redraw like its button", () => {
    expect(actionLabel("board.update", { name: "grid" })).toBe('Show live version: "grid"');
  });
});
