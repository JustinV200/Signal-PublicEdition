// Whether the document is visible: for animations that should stop while
// the tab is in the background, and for marking rows seen only when they
// can be (scroll's useFollow).
import { useEffect, useState } from "react";

/** True unless the page is hidden (minimised, or another browser tab). */
export function isPageVisible(): boolean {
  return document.visibilityState !== "hidden";
}

/** True while the page is visible; updates on `visibilitychange`. */
export function usePageVisible(): boolean {
  const [visible, setVisible] = useState(isPageVisible);
  useEffect(() => {
    const onChange = () => setVisible(isPageVisible());
    document.addEventListener("visibilitychange", onChange);
    return () => document.removeEventListener("visibilitychange", onChange);
  }, []);
  return visible;
}
