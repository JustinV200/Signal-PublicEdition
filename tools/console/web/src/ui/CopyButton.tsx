// The console's one copy-to-clipboard control: a Button, a note beside it,
// and a fallback. A click writes the text with the async Clipboard API. That
// is not verified in the Edge app window on http://127.0.0.1, and it can be
// missing or refused, so a failed write shows the text in a read-only box,
// focused and selected, for Ctrl+C by hand.
import { useEffect, useRef, useState } from "react";
import { Button } from "./Button";
import styles from "./copy.module.css";

export interface CopyButtonProps {
  /** Exactly what lands on the clipboard. */
  text: string;
  /** The button's label; `Copy` unless set. */
  label?: string;
  /** Beside the button before any click, e.g. why this is copied rather than sent. */
  note?: string;
  /** Beside the button after a good copy; `Copied.` unless set. */
  copiedNote?: string;
}

type Outcome = "idle" | "copied" | "failed";

const FAILED_NOTE = "Couldn't copy here. The text is selected below: press Ctrl+C.";
const MAX_FALLBACK_ROWS = 6;

/** Copies `text` on click and says how it went; on failure, selects it in a box instead. */
export function CopyButton({
  text,
  label = "Copy",
  note,
  copiedNote = "Copied.",
}: CopyButtonProps) {
  const [outcome, setOutcome] = useState<Outcome>("idle");
  const fallbackRef = useRef<HTMLTextAreaElement>(null);

  // Select the fallback's text as soon as it shows, so Ctrl+C is all that's left.
  useEffect(() => {
    if (outcome !== "failed") return;
    fallbackRef.current?.focus();
    fallbackRef.current?.select();
  }, [outcome]);

  const fail = (error: unknown) => {
    // Handled by the fallback box; the reason only matters to someone debugging.
    console.warn("clipboard write failed", error);
    setOutcome("failed");
  };
  const copy = () => {
    // `navigator.clipboard` is undefined outside a secure context, so the call itself can throw.
    try {
      navigator.clipboard.writeText(text).then(() => setOutcome("copied"), fail);
    } catch (error) {
      fail(error);
    }
  };

  const words = { idle: note, copied: copiedNote, failed: FAILED_NOTE }[outcome];
  return (
    <span className={styles.copy}>
      <span className={styles.row}>
        <Button onClick={copy}>{label}</Button>
        <span role="status" className={styles.note}>
          {words}
        </span>
      </span>
      {outcome === "failed" && (
        <textarea
          ref={fallbackRef}
          className={styles.fallback}
          readOnly
          value={text}
          rows={Math.min(MAX_FALLBACK_ROWS, text.split("\n").length)}
          aria-label="text to copy"
        />
      )}
    </span>
  );
}
