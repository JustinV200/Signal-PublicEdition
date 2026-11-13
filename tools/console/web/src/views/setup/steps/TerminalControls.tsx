// A step that needs the owner's own terminal (a password, Windows Hello, a
// typed client ID): the wizard never takes those. "Open a terminal" starts a
// PowerShell window on `setup.ps1 <tool>`; once it's done there, "Mark done"
// records it.
import { useState } from "react";
import { openSetupTerminal, UnauthorizedError } from "../../../api";
import { useStore } from "../../../state";
import { Button } from "../../../ui";
import styles from "../setup.module.css";

interface TerminalControlsProps {
  toolId: string;
  onMarkDone: () => void;
  busy: boolean;
}

/** Open a terminal, the command to type instead, and Mark done. */
export function TerminalControls({ toolId, onMarkDone, busy }: TerminalControlsProps) {
  const { dispatch } = useStore();
  const [note, setNote] = useState<string | null>(null);
  const open = async () => {
    try {
      await openSetupTerminal(toolId);
      setNote("Opened. Follow it there, then come back and mark the step done.");
    } catch (failure) {
      if (failure instanceof UnauthorizedError) dispatch({ type: "auth", auth: "out" });
      setNote(failure instanceof Error ? failure.message : String(failure));
    }
  };
  return (
    <div className={styles.form}>
      <p className={styles.note}>
        This step asks for something secret, so it runs in your own terminal:{" "}
        <code>.\setup.ps1 {toolId}</code>
      </p>
      <div className={styles.controls}>
        <Button primary onClick={() => void open()}>
          Open a terminal
        </Button>
        <Button onClick={onMarkDone} pending={busy}>
          Done there: mark done
        </Button>
      </div>
      {note && (
        <p className={styles.note} role="status">
          {note}
        </p>
      )}
    </div>
  );
}
