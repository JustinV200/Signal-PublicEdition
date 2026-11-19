// The radar's input: a blip is a mark, its words and where it sits. The scope
// builds them from the store (blips.ts, taskBlips.ts); the radar only draws.
import type { View } from "../../../state";
import type { MarkShape } from "../../../ui";

/** The ui marks the scope uses. */
export type BlipShape = Extract<
  MarkShape,
  "disc" | "ring" | "half" | "square" | "diamond" | "triangle"
>;

export interface Blip {
  id: string;
  shape: BlipShape;
  /** The words beside the mark; cut with an ellipsis to stay inside the rim. */
  label: string;
  /** Kept whole when the label is cut: a task's ` 60%`. */
  tail?: string;
  /** Degrees clockwise from the top. */
  bearingDeg: number;
  /** 0 at the centre, 1 on the outer ring. */
  range: number;
  /** Something is in flight: the mark pulses, `slow` while only agents run (static under reduced motion). */
  pulse?: "normal" | "slow";
  /** The view a click opens (the readout row for the same thing opens it by keyboard). */
  view: View;
  /** Waits on the owner: a triangle with a bold label (the needs-you count). */
  isUrgent?: boolean;
  /**
   * A label that always shows whole in its first spot, never cut short of a
   * neighbour or hidden (Claude's, the needs-you count's). Whoever builds the
   * blip keeps that spot clear of every other mark and of the fixed words.
   */
  isLabelPinned?: boolean;
}
