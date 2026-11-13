// Id-keyed list helpers for the reducer. The server replays recent events on
// every (re)connect with stable ids, so inserts dedupe by id (first one wins)
// and keep time order.
import { toMs } from "../time";
import type { TimeLike } from "../time";

interface Stamped {
  id: string;
  at: TimeLike;
}

/**
 * Appends `item` to `list` unless an entry with the same id exists (a replay:
 * the first one is kept), then returns a new list sorted by `at` (stable, so
 * equal times keep arrival order).
 */
export function upsertSorted<T extends Stamped>(list: readonly T[], item: T): T[] {
  const next = list.some((entry) => entry.id === item.id) ? [...list] : [...list, item];
  return next.sort((a, b) => toMs(a.at) - toMs(b.at));
}

/** Returns `list` with the entry matching `id` replaced by `update(entry)`, or unchanged. */
export function updateById<T extends { id: string }>(
  list: readonly T[],
  id: string,
  update: (entry: T) => T,
): T[] {
  const index = list.findIndex((entry) => entry.id === id);
  return index === -1 ? [...list] : list.with(index, update(list[index]));
}
