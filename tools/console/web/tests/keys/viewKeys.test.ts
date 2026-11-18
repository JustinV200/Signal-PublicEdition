// Ctrl+digit to view: the six tabs, the old Models and Tools keys kept as
// System aliases, Setup on Ctrl+9, and no view for other keys.
import { describe, expect, it } from "vitest";
import { viewForDigit } from "../../src/keys";

describe("viewForDigit", () => {
  it.each([
    ["1", "scope"],
    ["5", "tasks"],
    ["6", "system"],
    ["7", "system"],
    ["8", "system"],
    ["9", "setup"],
    ["0", undefined],
    ["toString", undefined],
  ])("Ctrl+%s opens %s", (key, view) => {
    expect(viewForDigit(key)).toBe(view);
  });
});
