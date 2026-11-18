// The counts the tab row and the browser window's title share: Chat's
// `2 new`, Tasks' `1 needs you`, and the title that joins them,
// `(2 new, 1 needs you) Signal console`. Pure, so the words stay one wording.

/** The page's name: the window title when nothing is new. */
export const APP_NAME = "Signal console";

/** `2 new` (Chat rows not seen yet); null at 0. */
export function newWords(count: number): string | null {
  return count > 0 ? `${count} new` : null;
}

/** `1 needs you` (tasks waiting on the owner); null at 0. */
export function needsYouWords(count: number): string | null {
  return count > 0 ? `${count} needs you` : null;
}

/**
 * The window title: `(2 new, 1 needs you) Signal console`, a part dropped at 0
 * (`(1 needs you) Signal console`), and `Signal console` alone when both are 0.
 */
export function windowTitle(chatNew: number, needsYou: number): string {
  const parts = [newWords(chatNew), needsYouWords(needsYou)].filter((part) => part !== null);
  return parts.length > 0 ? `(${parts.join(", ")}) ${APP_NAME}` : APP_NAME;
}
