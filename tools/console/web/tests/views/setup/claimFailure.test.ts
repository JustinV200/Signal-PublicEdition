// ClaimLink's failure line shows one mark: `!` for a busy answer or exit 3, a cross otherwise.
import { describe, expect, it } from "vitest";
import { claimFailure } from "../../../src/views/setup/steps/claimFailure";

describe("claim failure", () => {
  it.each([
    {
      what: "busy",
      run: { error: "! busy: a step runs", busy: true, exit: null },
      notice: true,
      words: "busy: a step runs",
    },
    {
      what: "exit 3",
      run: { error: null, busy: false, exit: 3 },
      notice: true,
      words: "needs you",
    },
    {
      what: "other failure",
      run: { error: null, busy: false, exit: 1 },
      notice: false,
      words: "failed",
    },
  ])("$what", ({ run, notice, words }) => {
    const got = claimFailure(run);
    expect(got?.isNotice).toBe(notice);
    expect(got?.words.startsWith("!")).toBe(false);
    expect(got?.words).toContain(words);
  });
});
