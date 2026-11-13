// Grows a textarea with its content from 1 to `maxRows` rows, then scrolls.
import { useLayoutEffect } from "react";
import type { RefObject } from "react";

/** Re-measures `ref` whenever `value` changes. */
export function useAutoGrow(
  ref: RefObject<HTMLTextAreaElement | null>,
  value: string,
  maxRows: number,
): void {
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const rowHeight = parseFloat(getComputedStyle(el).lineHeight);
    const maxHeight = rowHeight * maxRows;
    // Collapse first so scrollHeight reports the content height, not the old box.
    el.style.height = "auto";
    const needed = el.scrollHeight;
    el.style.height = `${Math.min(needed, maxHeight)}px`;
    el.style.overflowY = needed > maxHeight ? "auto" : "hidden";
  }, [ref, value, maxRows]);
}
