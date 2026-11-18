// The console's claim step, live: whether a Claude Code session is linked to
// this console right now and, until one is, the sentence to paste into Claude
// Code with Copy (the claim sentence and CopyButton Chat uses). It ticks
// itself: when a session links, the claim step is marked done once (`setup
// mark console claim done` only records progress). Shown in the claim step's
// row on the Task console's page and on Permissions, which connects Claude Code.
// The tick waits while another setup step runs (the wizard's running state),
// so it never meets a busy answer mid-install.
import { useEffect, useRef } from "react";
import { CLAIM_SENTENCE, claudeLink, PASTE_INTO_CLAUDE_NOTE, useStore } from "../../../state";
import type { ClaudeLink } from "../../../state";
import { CopyButton, Mark } from "../../../ui";
import type { MarkShape } from "../../../ui";
import { useRunningState, useSetupRun } from "../run";
import styles from "../setup.module.css";
import { CONSOLE_ID } from "../wizardScreens";
import { claimFailure } from "./claimFailure";

/** The console's claim step in the setup registry. */
export const CLAIM_STEP_ID = "claim";

// Each link state's ui `Mark` shape and words.
const LINK_LOOKS: Record<ClaudeLink, { mark: MarkShape; words: string }> = {
  linked: { mark: "check", words: "Linked: Claude Code is connected to this console." },
  none: { mark: "ring", words: "Not linked yet." },
  closed: { mark: "ring", words: "The linked Claude Code session closed. Link the new one." },
};

interface ClaimLinkProps {
  /** The claim step is already done (nothing to mark). */
  isClaimDone: boolean;
  /** Re-read the tools after the step was marked. */
  onMarked: () => void;
}

/** The link state in words, the sentence and Copy, and the self-tick. */
export function ClaimLink({ isClaimDone, onMarked }: ClaimLinkProps) {
  const { state } = useStore();
  const runner = useSetupRun();
  const { run } = runner;
  const { active } = useRunningState();
  // Marked at most once per mount, so a refused mark (say a 409 while a step runs) never loops.
  const triedRef = useRef(false);
  const link = state.server ? claudeLink(state.server.orchestrator) : null;

  useEffect(() => {
    if (link !== "linked" || isClaimDone || triedRef.current || active) return;
    triedRef.current = true;
    void run({ command: "mark", tool: CONSOLE_ID, step: CLAIM_STEP_ID, status: "done" }).then(
      onMarked,
    );
  }, [link, isClaimDone, active, run, onMarked]);

  const failure = claimFailure(runner);
  return (
    <div className={styles.form}>
      <p className={styles.stepTitle} role="status">
        {link ? (
          <>
            <Mark shape={LINK_LOOKS[link].mark} /> {LINK_LOOKS[link].words}
          </>
        ) : (
          "… checking the link"
        )}
      </p>
      {link !== "linked" && (
        <>
          <p>
            Paste this into Claude Code: <code>{CLAIM_SENTENCE}</code>
          </p>
          <CopyButton text={CLAIM_SENTENCE} copiedNote={PASTE_INTO_CLAUDE_NOTE} />
        </>
      )}
      {failure && (
        // A busy answer (another command ran) is no failure: `!`, not a cross.
        <p className={failure.isNotice ? styles.note : styles.problem}>
          {failure.isNotice ? "!" : <Mark shape="cross" />} Couldn't record the link:{" "}
          {failure.words}
        </p>
      )}
    </div>
  );
}
