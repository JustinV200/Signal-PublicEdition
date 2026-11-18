// `setup plan`'s answer for the Permissions page, split where
// wiring.summary_lines puts its one blank line: the plain consent lines first,
// the exact entries after. A failed plan is an error, never consent.

/** The parsed plan: consent lines and exact entries, or the failure's words. */
export interface ConsentPlan {
  /** One line per tool, "Gmail: Claude can …", then the closing line. */
  plain: string[];
  /** The exact entries, as printed. */
  exact: string;
  /** The output of a plan that exited non-zero; null when it worked. */
  error: string | null;
}

/**
 * Splits `setup plan`'s lines at the first blank one.
 *
 * @param lines The command's output lines.
 * @param exit Its exit code: anything but 0 makes the whole output the error.
 */
export function splitPlan(lines: string[], exit: number): ConsentPlan {
  if (exit !== 0) {
    return { plain: [], exact: "", error: lines.join("\n").trim() || `exit ${exit}` };
  }
  const gap = lines.indexOf("");
  // No gap (an older CLI): every line is shown, none folded away.
  if (gap < 0) return { plain: lines, exact: "", error: null };
  const exact = lines
    .slice(gap + 1)
    .join("\n")
    .trimEnd();
  return { plain: lines.slice(0, gap), exact, error: null };
}
