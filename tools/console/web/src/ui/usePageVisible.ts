// Whether the document is visible, for animations that should stop while
// the tab is in the background.
import { useEffect, useState } from "react";

function isVisible(): boolean {
  return document.visibilityState !== "hidden";
}

/** True while the page is visible; updates on `visibilitychange`. */
export function usePageVisible(): boolean {
  const [visible, setVisible] = useState(isVisible);
  useEffect(() => {
    const onChange = () => setVisible(isVisible());
    document.addEventListener("visibilitychange", onChange);
    return () => document.removeEventListener("visibilitychange", onChange);
  }, []);
  return visible;
}
