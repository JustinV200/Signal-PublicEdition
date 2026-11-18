// Window-level keys: Ctrl+K (command mode), Ctrl+1 to 9 (views, see
// viewKeys.ts), Esc (close the palette or confirm, else help, else just focus
// the input; never a view change), y / n while the input line asks a question
// (wherever focus is), PageUp/PageDown/Ctrl+End from the input (scroll the
// view), and any printable key but Space from outside a text field (go to the
// input). The decisions themselves are in keyRoutes.ts.
import { useEffect, useRef } from "react";
import type { Dispatch, RefObject } from "react";
import { focusInput, INPUT_ID } from "../input";
import type { InputMode, StoreAction } from "../state";
import { escapeCloses, isPrintable, sendsToInput } from "./keyRoutes";
import { viewForDigit } from "./viewKeys";

// PageUp/PageDown move by most of a screen, like a terminal pager.
const PAGE_FRACTION = 0.9;
// The confirm line's answer keys: y is yes, n is no.
const ANSWER_BY_KEY: Record<string, boolean> = { y: true, n: false };

interface GlobalKeyOptions {
  dispatch: Dispatch<StoreAction>;
  mode: InputMode;
  helpOpen: boolean;
  scrollRef: RefObject<HTMLElement | null>;
  /** Answers the confirm line (the confirm gate's `answer`). */
  answerConfirm: (yes: boolean) => void;
}

/** The answer a key gives while the input line asks a question; undefined for any other key. */
function confirmAnswer(event: KeyboardEvent, mode: InputMode): boolean | undefined {
  // A held key repeats; only the first press answers, so a held y cannot run twice.
  if (mode.kind !== "confirm" || event.repeat || !isPrintable(event)) return undefined;
  return ANSWER_BY_KEY[event.key.toLowerCase()];
}

/** The focused element's input type, for keyRoutes; undefined when it isn't an input. */
function inputTypeOf(element: Element | null): string | undefined {
  return element instanceof HTMLInputElement ? element.type : undefined;
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
export function useGlobalKeys({
  dispatch,
  mode,
  helpOpen,
  scrollRef,
  answerConfirm,
}: GlobalKeyOptions): void {
  // The y or n that answered, while it is held: its repeats must not type into the input that returns.
  const answeredKey = useRef<string | null>(null);

  useEffect(() => {
    const closeOnEscape = () => {
      const target = escapeCloses(mode.kind, helpOpen);
      if (target === "mode") dispatch({ type: "inputMode", mode: { kind: "text" } });
      else if (target === "help") dispatch({ type: "help", open: false });
      focusInput();
    };

    const onKeyDown = (event: KeyboardEvent) => {
      const key = event.key.toLowerCase();
      if (event.repeat && key === answeredKey.current) {
        event.preventDefault();
        return;
      }
      if (!event.repeat) answeredKey.current = null;
      const active = document.activeElement;
      const answer = confirmAnswer(event, mode);
      const digitView = event.ctrlKey ? viewForDigit(event.key) : undefined;
      if (event.ctrlKey && key === "k") {
        dispatch({ type: "inputMode", mode: { kind: "command" } });
      } else if (digitView) {
        dispatch({ type: "view", view: digitView });
        focusInput();
      } else if (event.key === "Escape") {
        closeOnEscape();
      } else if (answer !== undefined) {
        answeredKey.current = key;
        answerConfirm(answer);
      } else if (scrollView(event, scrollRef.current)) {
        // handled
      } else if (sendsToInput(event, active?.tagName, inputTypeOf(active))) {
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
  }, [dispatch, mode, helpOpen, scrollRef, answerConfirm]);
}
