// Auto-follow for a scrolling log: stay pinned to the bottom while the reader
// is there, otherwise count what arrived below the fold for the `↓ N new` pill.
// A row too tall to fit is shown from its top instead, with the pill.
import { useCallback, useLayoutEffect, useRef, useState } from "react";
import type { RefObject } from "react";
import { isPageVisible } from "../ui";
import { followRows } from "./followRows";
import { contentEnd } from "./measure";
import { useBottomWatch } from "./useBottomWatch";

const REDUCED_MOTION = "(prefers-reduced-motion: reduce)";

export interface Follow {
  /** Rows appended while the reader was scrolled up, or shown from their top. */
  newCount: number;
  /** Scrolls to the end (smooth, or instant under reduced motion) and clears `newCount`. */
  jumpToBottom: () => void;
}

/** What `useFollow` reads besides the scroller and the row count; all optional. */
export interface FollowOptions {
  /** Runs while the reader is at the end and the page is visible (Chat marks its rows seen). */
  onAtBottom?: () => void;
  /** Whether the newest row arrived after mount; false (the default) always follows to the end. */
  isLiveEnd?: boolean;
  /**
   * Changes when something after the rows comes or goes (Chat's working row):
   * the view re-pins to the end if the reader is there, and nothing is counted.
   */
  tailKey?: string | number | null;
}

/**
 * Follows `scrollRef` as `rowCount` grows. On mount it jumps to the bottom
 * instantly; appends are instant too, and only the pill click is smooth.
 * When `isLiveEnd` says the newest row arrived live (after mount) and the
 * rows appended at the end of a non-empty log are taller than the view, it
 * scrolls down only far enough to show their top and counts them on the pill,
 * so a long reply reads from its start. Replayed history, however many chunks
 * it comes in, and an empty log filling always go to the end. `onAtBottom`
 * runs on mount, after each followed append, on scrolling back down, and again
 * when the page becomes visible at the end.
 *
 * @param scrollRef The scrolling element.
 * @param rowCount How many rows the log holds (what the pill counts).
 * @param options See `FollowOptions`.
 */
export function useFollow(
  scrollRef: RefObject<HTMLElement | null>,
  rowCount: number,
  { onAtBottom, isLiveEnd = false, tailKey = null }: FollowOptions = {},
): Follow {
  const [newCount, setNewCount] = useState(0);
  const atBottom = useRef(true);
  const previousCount = useRef(0);
  // Where the content ended after the last follow (or scroll): new rows start there.
  const endBefore = useRef(0);
  // Kept in refs so a new callback each render doesn't re-attach the scroll
  // listener; synced before the follow effect below runs in the same commit.
  const onAtBottomRef = useRef(onAtBottom);
  const isLiveEndRef = useRef(isLiveEnd);
  useLayoutEffect(() => {
    onAtBottomRef.current = onAtBottom;
    isLiveEndRef.current = isLiveEnd;
  });

  const clearNew = useCallback(() => setNewCount(0), []);
  useBottomWatch(scrollRef, { atBottom, endBefore, onAtBottomRef, clearNew });

  useLayoutEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const added = rowCount - previousCount.current;
    // An empty log filling is always a first fill (mount, or the replay): it goes to the end.
    const isTopFirst = isLiveEndRef.current && previousCount.current > 0 && added > 0;
    previousCount.current = rowCount;
    const action = followRows(el, {
      atBottom: atBottom.current,
      isTopFirst,
      endBefore: endBefore.current,
    });
    if (action.kind === "count") {
      if (added > 0) setNewCount((count) => count + added);
    } else if (action.kind === "top") {
      el.scrollTop = action.scrollTop;
      atBottom.current = false;
      setNewCount((count) => count + added);
    } else {
      el.scrollTop = el.scrollHeight;
      if (isPageVisible()) onAtBottomRef.current?.();
    }
    endBefore.current = contentEnd(el);
    // tailKey re-runs this when the tail comes or goes with no row added, so the
    // end stays pinned past it (and is never counted on the pill).
  }, [rowCount, tailKey, scrollRef]);

  const jumpToBottom = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const behavior = window.matchMedia(REDUCED_MOTION).matches ? "instant" : "smooth";
    el.scrollTo({ top: el.scrollHeight, behavior });
    setNewCount(0);
  }, [scrollRef]);

  return { newCount, jumpToBottom };
}
