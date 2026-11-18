// Window-level key routing: a typed key reaches the input line from any
// focused control but a text field, and Esc closes the nearest open thing
// (palette or confirm, then help) without ever changing view.
import { describe, expect, it } from "vitest";
import { escapeCloses, sendsToInput } from "../../src/keys";

const PLAIN = { ctrlKey: false, metaKey: false, altKey: false };

describe("sendsToInput", () => {
  it.each([
    [{ key: "a" }, "BODY", undefined, true],
    [{ key: "a" }, "BUTTON", undefined, true],
    [{ key: "a" }, "INPUT", "checkbox", true],
    [{ key: "a" }, "INPUT", "text", false],
    [{ key: "a" }, "INPUT", undefined, false],
    [{ key: "a" }, "TEXTAREA", undefined, false],
    [{ key: "a" }, "SELECT", undefined, false],
    [{ key: " " }, "BUTTON", undefined, false],
    [{ key: "Enter" }, "BUTTON", undefined, false],
    [{ key: "a", ctrlKey: true }, "BODY", undefined, false],
  ])("%j with %s (%s) focused: %s", (key, tag, inputType, expected) => {
    expect(sendsToInput({ ...PLAIN, ...key }, tag, inputType)).toBe(expected);
  });
});

describe("escapeCloses", () => {
  it.each([
    ["command", true, "mode"],
    ["confirm", false, "mode"],
    ["text", true, "help"],
    ["text", false, "nothing"],
  ] as const)("in %s mode with help open %s: closes %s", (mode, helpOpen, target) => {
    expect(escapeCloses(mode, helpOpen)).toBe(target);
  });
});
