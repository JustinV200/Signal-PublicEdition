// The setup CLI's indented JSON, found among a step's other output lines.
import { describe, expect, it } from "vitest";
import { firstJson, jsonDocs } from "../../../src/api";

describe("jsonDocs", () => {
  it("skips program output and reads each indented document", () => {
    const lines = [
      "$ uv sync --project tools/brief",
      "Resolved 12 packages",
      "[]",
      "{",
      '  "tool": "brief",',
      '  "messages": ["{not json"]',
      "}",
    ];
    expect(jsonDocs(lines)).toEqual([[], { tool: "brief", messages: ["{not json"] }]);
  });

  it("throws with the last line when there is no JSON", () => {
    expect(() => firstJson(["setup: error: unknown tool 'x'"])).toThrow("unknown tool");
  });
});
