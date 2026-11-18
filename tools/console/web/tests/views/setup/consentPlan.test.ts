// The Permissions page shows `setup plan`'s plain lines as consent and folds the
// exact entries after the blank line; a failed plan is an error, never consent.
import { describe, expect, it } from "vitest";
import { splitPlan } from "../../../src/views/setup/screens";

describe("consent plan", () => {
  it.each([
    {
      what: "plain lines, then the exact entries after the blank line",
      lines: [
        "Gmail: Claude can read mail.",
        "Everything else asks.",
        "",
        "Tools: mail",
        "  x",
        "",
      ],
      exit: 0,
      want: {
        plain: ["Gmail: Claude can read mail.", "Everything else asks."],
        exact: "Tools: mail\n  x",
        error: null,
      },
    },
    {
      what: "a failed plan is the error, with no consent lines",
      lines: ["Gmail: Claude can read mail.", "", "Traceback: boom"],
      exit: 1,
      want: {
        plain: [],
        exact: "",
        error: "Gmail: Claude can read mail.\n\nTraceback: boom",
      },
    },
  ])("$what", ({ lines, exit, want }) => {
    expect(splitPlan(lines, exit)).toEqual(want);
  });
});
