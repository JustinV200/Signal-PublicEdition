// What Chat shows while no Claude session is linked: the cause in one line,
// then the sentence to paste into Claude Code, with Copy. It leads an empty
// Chat and follows the last message otherwise, so a session that closed
// mid-conversation is as easy to replace as the first one.
import { CLAIM_SENTENCE, PASTE_INTO_CLAUDE_NOTE } from "../../state";
import type { ClaudeLink } from "../../state";
import { CopyButton } from "../../ui";
import styles from "./chat.module.css";

export type UnlinkedState = Exclude<ClaudeLink, "linked">;

const CAUSES: Record<UnlinkedState, string> = {
  none: "No Claude session yet.",
  closed: "Claude session closed.",
};

/** The cause (worded and bold; the warning colour only repeats it), the sentence and Copy. */
export function ClaimHelp({ link }: { link: UnlinkedState }) {
  return (
    <div className={styles.claim}>
      <div className={styles.claimCause}>{CAUSES[link]}</div>
      <div>
        Paste this into Claude Code to link it: <code>{CLAIM_SENTENCE}</code>
      </div>
      <CopyButton text={CLAIM_SENTENCE} copiedNote={PASTE_INTO_CLAUDE_NOTE} />
    </div>
  );
}
