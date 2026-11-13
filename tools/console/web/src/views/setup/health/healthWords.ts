// How a tool's health (`setup status --json`) reads: a mark and a label for
// each state, so the state never rides on colour alone (the owner is
// colourblind), and the button that fixes it.
import type { HealthState, ToolHealth } from "../../../api";

export interface HealthLook {
  /** A shape that differs per state: filled, crossed, hollow. */
  mark: string;
  label: string;
}

const LOOKS: Record<HealthState, HealthLook> = {
  active: { mark: "●", label: "Active" },
  down: { mark: "✗", label: "Down" },
  not_set_up: { mark: "○", label: "Not set up" },
};

/** The mark and label for a state. */
export function healthLook(state: HealthState): HealthLook {
  return LOOKS[state];
}

/** The row's button: Fix when it's down, Re-run setup when active, else Set up (or Continue). */
export function healthAction(row: ToolHealth): string {
  if (row.state === "down") return "Fix";
  if (row.state === "active") return "Re-run setup";
  return row.setupStatus === "started" || row.setupStatus === "failed"
    ? "Continue setup"
    : "Set up";
}

/** `3 active · 1 down · 9 not set up` for a header. */
export function healthCounts(rows: readonly ToolHealth[]): string {
  const count = (state: HealthState) => rows.filter((row) => row.state === state).length;
  return `${count("active")} active · ${count("down")} down · ${count("not_set_up")} not set up`;
}
