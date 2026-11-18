// Keeps `useFollow`'s bottom state current from scroll and visibility events.
import { useEffect } from "react";
import type { MutableRefObject, RefObject } from "react";
import { isPageVisible } from "../ui";
import { contentEnd, isAtBottom } from "./measure";

/** What the watcher shares with `useFollow`. */
export interface BottomWatchState {
  atBottom: MutableRefObject<boolean>;
  endBefore: MutableRefObject<number>;
  onAtBottomRef: MutableRefObject<(() => void) | undefined>;
  clearNew: () => void;
}

/**
 * Tracks whether the reader is at the end, clearing the new count when they are.
 *
 * @param scrollRef The scrolling element.
 * @param s The refs and callbacks shared with `useFollow` (see `BottomWatchState`).
 */
export function useBottomWatch(scrollRef: RefObject<HTMLElement | null>, s: BottomWatchState) {
  const { atBottom, endBefore, onAtBottomRef, clearNew } = s;
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const onScroll = () => {
      // A scroll also follows content that moved above (scroll anchoring), so
      // re-read the end. Row height changes without a scroll leave it slightly
      // stale; the error falls on the safe side (the follow takes the earlier of
      // this and the view's bottom).
      endBefore.current = contentEnd(el);
      atBottom.current = isAtBottom(el);
      if (!atBottom.current) return;
      clearNew();
      if (isPageVisible()) onAtBottomRef.current?.();
    };
    // Rows that landed while hidden are seen once the page shows at the end.
    const onVisibilityChange = () => {
      if (!isPageVisible() || !isAtBottom(el)) return;
      atBottom.current = true;
      clearNew();
      onAtBottomRef.current?.();
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => {
      el.removeEventListener("scroll", onScroll);
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, [scrollRef, atBottom, endBefore, onAtBottomRef, clearNew]);
}
