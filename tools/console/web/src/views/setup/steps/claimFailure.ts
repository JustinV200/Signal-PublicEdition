// What ClaimLink says when recording the link fails, with one mark only: a busy
// answer, or words that lead with `!` (exit 3's "! needs you"), are a notice
// (`!`, no cross); any other failure is a problem (cross). The `!` is stripped
// from the words so it only ever shows once, at the front.
import { exitLook } from "../run";

/** The slice of a setup runner this reads. */
interface ClaimRun {
  error: string | null;
  busy: boolean;
  exit: number | null;
}

/** The failure to show: its words (no leading "! ") and whether it is a notice. */
export function claimFailure(run: ClaimRun): { words: string; isNotice: boolean } | null {
  const look =
    run.error === null && run.exit !== null && run.exit !== 0 ? exitLook(run.exit) : null;
  const words = run.error ?? look?.words ?? null;
  if (!words) return null;
  return { words: words.replace(/^! /, ""), isNotice: run.busy || look?.mark === null };
}
