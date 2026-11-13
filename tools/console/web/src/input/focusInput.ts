// Focus the message input from anywhere (after an action, confirm or view
// switch). A fixed id keeps this a one-liner instead of threading a ref.

export const INPUT_ID = "console-input";

/** Moves keyboard focus to the input textarea if it is on screen. */
export function focusInput(): void {
  document.getElementById(INPUT_ID)?.focus();
}
