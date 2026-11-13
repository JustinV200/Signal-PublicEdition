// Auto-follow for a scrolling log: stay pinned to the bottom while the reader
// is there, otherwise count what arrived below the fold for the `↓ N new` pill.
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import type { RefObject } from "react";

// How close to the end still counts as "at the bottom" (sub-pixel scroll slop).
const BOTTOM_SLACK_PX = 8;

function isAtBottom(el: HTMLElement): boolean {
  return el.scrollHeight - el.scrollTop - el.clientHeight < BOTTOM_SLACK_PX;
}

export interface Follow {
  /** Rows appended while the reader was scrolled up. */
  newCount: number;
  /** Smooth-scrolls to the end and clears `newCount`. */
  jumpToBottom: () => void;
}

/**
 * Follows `scrollRef` as `itemCount` grows. On mount it jumps to the bottom
 * instantly; live appends are instant too, and only the pill click is smooth.
 */
export function useFollow(scrollRef: RefObject<HTMLElement | null>, itemCount: number): Follow {
  const [newCount, setNewCount] = useState(0);
  const atBottom = useRef(true);
  const previousCount = useRef(0);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const onScroll = () => {
      atBottom.current = isAtBottom(el);
      if (atBottom.current) setNewCount(0);
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, [scrollRef]);

  useLayoutEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const added = itemCount - previousCount.current;
    previousCount.current = itemCount;
    if (atBottom.current) el.scrollTop = el.scrollHeight;
    else if (added > 0) setNewCount((count) => count + added);
  }, [itemCount, scrollRef]);

  const jumpToBottom = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    setNewCount(0);
  }, [scrollRef]);

  return { newCount, jumpToBottom };
}
