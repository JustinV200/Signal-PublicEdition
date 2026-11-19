// The radar's task blips. A task that isn't waiting on the owner is a half
// disc at a range that is its progress (rim 0%, by the centre at 100%),
// labelled with its name and percent (never the board's status number), and
// they spread evenly across the TASKS sector but off the band around 270°
// (the horizontal through Claude's mark). The tasks that need the owner are
// not drawn one by one, since the readout beside the radar says what each
// needs: together they are one triangle on that horizontal, out by the rim,
// whose bold label says how many (`19 NEED YOU`). The band keeps every other
// task's mark off that line, so the count always shows whole.
import type { TasksPayload } from "../../api";
import { splitNeedsYou } from "./needsYou";
import { percentRange, SECTORS } from "./radar";
import type { Blip } from "./radar";

// The left horizontal, and how far either side of it no ordinary task sits.
const HORIZON_DEG = 270;
const HORIZON_GAP_DEG = 30;
// How far out on that horizontal the needs-you count sits: inside the rim and
// its tick, and far enough from the centre that its label, which runs in along
// the line, ends well short of the finished tasks around Claude's mark.
const NEEDS_YOU_RANGE = 0.9;

/**
 * Ordinary task `index` of `count`'s bearing: in the middle of an equal slice
 * of the sector less the gap, counter-clockwise from the top, so the most
 * finished (nearest the centre) sit above it, and none on the sector's edge.
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

// Every task waiting on the owner, as one triangle that says how many; its label is pinned to the line the gap keeps clear.
function needsYouBlip(waiting: number): Blip {
  return {
    id: "needs-you-count",
    shape: "triangle",
    label: waiting === 1 ? "1 NEEDS YOU" : `${waiting} NEED YOU`,
    bearingDeg: HORIZON_DEG,
    range: NEEDS_YOU_RANGE,
    view: "tasks",
    isUrgent: true,
    isLabelPinned: true,
  };
}

/**
 * The task blips: the needs-you count if any task waits on the owner, then a
 * blip per ordinary task in the payload's order (most finished first). Only
 * the ordinary tasks take slots in the bearing spread.
 * @param tasks the `tasks` payload, null before the first event (no blips)
 * @returns the blips; at most one of them urgent
 */
export function taskBlips(tasks: TasksPayload | null): Blip[] {
  // The readout's own split, so its rows always add up to this count.
  const { shown, folded } = splitNeedsYou(tasks);
  const waiting = shown.length + folded;
  const ordinary = tasks?.active.filter((task) => task.status !== "needs_you") ?? [];
  return [
    ...(waiting > 0 ? [needsYouBlip(waiting)] : []),
    ...ordinary.map((task, index): Blip => ({
      id: `task-${task.id}`,
      shape: "half",
      label: task.name,
      tail: ` ${Math.round(task.pct)}%`,
      bearingDeg: taskBearing(index, ordinary.length),
      range: percentRange(task.pct),
      view: "tasks",
    })),
  ];
}
