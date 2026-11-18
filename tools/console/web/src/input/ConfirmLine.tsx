// Confirm mode: the question in place of the textarea, in 600, with Yes and No
// buttons. It takes focus on mount so a screen reader reads the question; the
// y / n keys and Esc are handled globally (keys/useGlobalKeys), so they work
// wherever focus is.
import { useEffect, useRef } from "react";
import { Button } from "../ui";
import styles from "./input.module.css";

interface ConfirmLineProps {
  prompt: string;
  onYes: () => void;
  onNo: () => void;
}

/** The question line with its Yes / No buttons. */
export function ConfirmLine({ prompt, onYes, onNo }: ConfirmLineProps) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => ref.current?.focus(), []);

  return (
    <div ref={ref} tabIndex={-1} role="alertdialog" aria-label={prompt} className={styles.confirm}>
      <span className={styles.question}>{prompt}</span>
      <span className={styles.answers}>
        <Button hint="y" onClick={onYes}>
          Yes
        </Button>
        <Button hint="n" onClick={onNo}>
          No
        </Button>
      </span>
    </div>
  );
}
