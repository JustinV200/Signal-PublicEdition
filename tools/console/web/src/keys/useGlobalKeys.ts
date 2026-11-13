// Window-level keys: Ctrl+K (command mode), Ctrl+1 to 9 (views), Esc (close
// help or the input mode, else back to the scope), PageUp/PageDown/Ctrl+End from
// the input (scroll the view), and any printable key with nothing focused (go
// to the input).
import { useEffect } from "react";
import type { Dispatch, RefObject } from "react";
import { focusInput, INPUT_ID } from "../input";
import { HOME_VIEW, VIEWS } from "../state";
import type { InputMode, StoreAction, View } from "../state";

// Ctrl+1 is the first view in tab order, Ctrl+9 the last.
const VIEW_BY_DIGIT: Record<string, View> = Object.fromEntries(
  VIEWS.map((view, index) => [String(index + 1), view]),
);
// PageUp/PageDown move by most of a screen, like a terminal pager.
const PAGE_FRACTION = 0.9;

interface GlobalKeyOptions {
  dispatch: Dispatch<StoreAction>;
  mode: InputMode;
  helpOpen: boolean;
  scrollRef: RefObject<HTMLElement | null>;
}

function isPrintable(event: KeyboardEvent): boolean {
  return event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey;
}

function isNothingFocused(): boolean {
  const active = document.activeElement;
  return !active || active === document.body;
}

/** Scrolls the view for pager keys sent from the input. Returns true when handled. */
function scrollView(event: KeyboardEvent, scroller: HTMLElement | null): boolean {
  if (!scroller || (event.target as HTMLElement | null)?.id !== INPUT_ID) return false;
  if (event.key === "PageDown") scroller.scrollBy({ top: scroller.clientHeight * PAGE_FRACTION });
  else if (event.key === "PageUp")
    scroller.scrollBy({ top: -scroller.clientHeight * PAGE_FRACTION });
  else if (event.key === "End" && event.ctrlKey) scroller.scrollTop = scroller.scrollHeight;
  else return false;
  return true;
}

/** Installs the global key handler for the shell. */
export function useGlobalKeys({ dispatch, mode, helpOpen, scrollRef }: GlobalKeyOptions): void {
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.ctrlKey && event.key.toLowerCase() === "k") {
        dispatch({ type: "inputMode", mode: { kind: "command" } });
      } else if (event.ctrlKey && VIEW_BY_DIGIT[event.key]) {
        dispatch({ type: "view", view: VIEW_BY_DIGIT[event.key] });
        focusInput();
      } else if (event.key === "Escape") {
        if (helpOpen) dispatch({ type: "help", open: false });
        else if (mode.kind !== "text") dispatch({ type: "inputMode", mode: { kind: "text" } });
        else dispatch({ type: "view", view: HOME_VIEW });
        focusInput();
      } else if (scrollView(event, scrollRef.current)) {
        // handled
      } else if (isPrintable(event) && isNothingFocused()) {
        // Focus now; the browser delivers this same keystroke to the textarea.
        focusInput();
        return;
      } else {
        return;
      }
      event.preventDefault();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [dispatch, mode.kind, helpOpen, scrollRef]);
}
