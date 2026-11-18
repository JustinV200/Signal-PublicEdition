// The radar's task blips: one per active task, spread evenly across the TASKS
// sector but off the band around 270° (the horizontal through Claude's mark
// and label, where a label pointing in would be cut short), at a range that is
// its progress (rim 0%, by the centre at 100%). A task that needs the owner is
// a triangle with an urgent (always-on, bold) label; the rest are half discs.
// The label is the name and percent, never the board's status number.
import type { TasksPayload } from "../../api";
import { percentRange, SECTORS } from "./radar";
import type { Blip } from "./radar";

// The left horizontal, and how far either side of it no task sits.
const HORIZON_DEG = 270;
const HORIZON_GAP_DEG = 30;

/**
 * Task `index` of `count`'s bearing: in the middle of an equal slice of the
 * sector less the gap, counter-clockwise from the top, so the most finished
 * (nearest the centre) sit above it, and none on the sector's edge.
 */
function taskBearing(index: number, count: number): number {
  const { fromDeg, toDeg } = SECTORS.tasks;
  const sliceDeg = (toDeg - fromDeg - 2 * HORIZON_GAP_DEG) / count;
  const fromTop = sliceDeg * (index + 0.5);
  const upperDeg = toDeg - HORIZON_DEG - HORIZON_GAP_DEG;
  // Past the upper part, jump the gap and carry on below the horizontal.
  return fromTop < upperDeg
    ? toDeg - fromTop
    : HORIZON_DEG - HORIZON_GAP_DEG - (fromTop - upperDeg);
}

/** A blip per active task, in the payload's order (most finished first); none before the first `tasks` event. */
export function taskBlips(tasks: TasksPayload | null): Blip[] {
  const active = tasks?.active ?? [];
  return active.map((task, index) => {
    const isUrgent = task.status === "needs_you";
    return {
      id: `task-${task.id}`,
      shape: isUrgent ? "triangle" : "half",
      label: task.name,
      tail: ` ${Math.round(task.pct)}%`,
      bearingDeg: taskBearing(index, active.length),
      range: percentRange(task.pct),
      view: "tasks",
      isUrgent,
      isLabelPinned: isUrgent,
    };
  });
}
