// The wizard's one running state: only the clicked button reads Working…,
// every other is off with the reason, and a busy answer (409) is no failure,
// so it is never offered to Claude.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { Button } from "../../../src/ui";
import { ANOTHER_RUNNING, buttonLook } from "../../../src/views/setup";
import { claim, OutputLog, release } from "../../../src/views/setup/run";
import type { SetupRun } from "../../../src/views/setup/run";

// Two runners' buttons, as useSetupRun keys them (`<runner id>:<button>`).
const A = "runner-a:run";
const B = "runner-b:yes";

/** Each button's markup while `active` holds the running state. */
const rendered = (active: string | null) =>
  [A, B].map((key) =>
    renderToStaticMarkup(
      <Button onClick={() => {}} {...buttonLook(active, key)}>
        Go
      </Button>,
    ),
  );

/** Which of A and B read Working… while `active` holds it. */
const working = (active: string | null) =>
  rendered(active).map((html) => html.includes("Working…"));

describe("one running state", () => {
  it("lets one runner hold it, and shows Working… on its button only", () => {
    let active = claim(null, A); // A's click
    expect(active).toBe(A);
    expect(working(active)).toEqual([true, false]);
    expect(rendered(active)[1]).toContain(`title="${ANOTHER_RUNNING}"`);

    active = claim(active, B); // B can't take it while A runs
    expect(active).toBe(A);
    active = release(active, B); // nor free it
    expect(active).toBe(A);
    expect(working(active)).toEqual([true, false]);

    active = release(active, A); // A's run ends: free, and every button is on
    expect(active).toBeNull();
    expect(working(active)).toEqual([false, false]);
    expect(rendered(active).some((html) => html.includes("disabled"))).toBe(false);
  });

  it("words a busy answer without a failure or a hand-off", () => {
    const busy: SetupRun = {
      lines: [],
      exit: null,
      running: false,
      error: "another setup step is still running; wait for it to finish",
      busy: true,
      run: async () => null,
      button: () => ({ pending: false }),
    };
    // A hand-off would need the store, so rendering without one also proves there is none.
    const html = renderToStaticMarkup(<OutputLog run={busy} what="Gmail: Install" />);
    expect(html).toContain("! busy: another setup step is still running");
    expect(html).not.toContain("Claude");
  });
});
