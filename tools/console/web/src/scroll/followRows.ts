// The follow decision for newly appended rows, kept apart from the hook so it
// reads on its own. It only reads the scroller; the caller acts on the result.
import { contentEnd } from "./measure";

// When a new row is taller than the view, where the old content ended lands
// this far below the top: it covers the view's bottom padding and the working
// row that sat under the log, so the new row's first line shows, under a
// sliver of the last.
const NEW_ROW_LEAD_PX = 64;

/** What to do with rows that just landed. */
export type FollowAction =
  | { kind: "count" } // reader is scrolled up: count them on the pill
  | { kind: "top"; scrollTop: number } // too tall: show from the top, count them
  | { kind: "end" }; // follow to the end

/** What `followRows` needs to know besides the scroller. */
export interface FollowInput {
  /** Whether the reader was at the end before the rows landed. */
  atBottom: boolean;
  /** Live append to a non-empty log (never a first fill). */
  isTopFirst: boolean;
  /** Where the content ended after the last follow or scroll. */
  endBefore: number;
}

/** Decides how to treat new rows, given the scroller as it is after they rendered. */
export function followRows(el: HTMLElement, input: FollowInput): FollowAction {
  if (!input.atBottom) return { kind: "count" };
  // The reader was at the end, so the new rows start where the old content
  // ended (or the view did, if that is earlier: the safer guess).
  const newStart = Math.min(el.scrollTop + el.clientHeight, input.endBefore);
  const isTall = contentEnd(el) - newStart > el.clientHeight - NEW_ROW_LEAD_PX;
  if (input.isTopFirst && isTall) return { kind: "top", scrollTop: newStart - NEW_ROW_LEAD_PX };
  return { kind: "end" };
}
