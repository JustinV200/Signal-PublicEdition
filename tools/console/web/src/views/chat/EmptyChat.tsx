// What the chat view shows before the first message: the shared empty state
// (`NO MESSAGES YET`), then, while no Claude session is linked, the claim help
// (the cause, the sentence to paste, Copy); otherwise which session is linked
// and how to send. Then where the rest is.
import { EmptyState } from "../../empty";
import type { ClaudeLink } from "../../state";
import { ClaimHelp } from "./ClaimHelp";

interface EmptyChatProps {
  /** Undefined before the first snapshot: nothing is said about Claude yet. */
  link: ClaudeLink | undefined;
  /** The claimed session's label; empty for an unlabelled one. */
  label: string;
}

/** The opening lines of an empty Chat. */
export function EmptyChat({ link, label }: EmptyChatProps) {
  return (
    <EmptyState label="No messages yet">
      {link && link !== "linked" && <ClaimHelp link={link} />}
      {link === "linked" && (
        <>
          {/* No quotes or brackets around an empty label. */}
          <div>{label ? `Linked to the Claude session "${label}".` : "Linked to Claude."}</div>
          <div>Type a message below and press Enter, or click Send. Claude answers here.</div>
        </>
      )}
      <div>
        Scope shows everything at a glance, Voice starts and stops Voice, Boards puts things on the
        projector, and Help lists the shortcuts.
      </div>
    </EmptyState>
  );
}
