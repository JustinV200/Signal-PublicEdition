// One row of the chat stream: gutter `HH:MM  role`, then the body. `you` is
// bold, `claude` renders markdown, `action` is muted plain text followed by
// where the button's run has got to (sending, working, done with what it did),
// `note` (a console notice) is bold with an amber label so it cannot be
// missed. A failed delivery adds a `failed: …` line with a Retry button.
import { Markdown } from "../../markdown";
import type { ActionProgress, LocalMessage, Origin } from "../../state";
import { formatClock } from "../../time";
import { Button } from "../../ui";
import styles from "./chat.module.css";

interface MessageRowProps {
  message: LocalMessage;
  /** True when the row appeared after the view mounted (animates in). */
  live: boolean;
  /** For action rows: how far the request has got. */
  progress?: ActionProgress;
  onRetry: (origin: Origin) => void;
}

const GUTTER_GAP = "  ";
const PROGRESS_WORDS: Record<ActionProgress, string> = {
  sending: "sending…",
  sent: "sent",
  working: "working…",
  done: "done",
  failed: "",
};

// A replayed failure has no local origin, but a chat message can still be resent as text.
function retryOrigin(message: LocalMessage): Origin | undefined {
  if (message.origin) return message.origin;
  return message.kind === "chat" ? { kind: "text", text: message.text } : undefined;
}

function Body({ message, progress }: { message: LocalMessage; progress?: ActionProgress }) {
  if (message.kind === "action")
    return (
      <div className={`${styles.plain} ${styles.muted}`}>
        {message.text}
        {progress && PROGRESS_WORDS[progress] && (
          <span className={styles.progress}>
            {" "}
            · {PROGRESS_WORDS[progress]}
            {progress === "done" && message.result && `: ${message.result}`}
          </span>
        )}
      </div>
    );
  if (message.kind === "note")
    return <div className={`${styles.plain} ${styles.noteBody}`}>{message.text}</div>;
  if (message.role === "claude") return <Markdown text={message.text} />;
  return <div className={styles.plain}>{message.text}</div>;
}

// Gutter label and its style per row kind; chat rows show the role.
function labelFor(message: LocalMessage): { text: string; className?: string } {
  if (message.kind === "action") return { text: "action" };
  if (message.kind === "note") return { text: "note", className: styles.note };
  return { text: message.role, className: message.role === "you" ? styles.you : undefined };
}

/** A chat, action, note or reply row. */
export function MessageRow({ message, live, progress, onRetry }: MessageRowProps) {
  const label = labelFor(message);
  const origin = retryOrigin(message);
  const bodyClasses = [styles.body, message.delivery === "sending" && styles.sending].filter(
    Boolean,
  );
  return (
    <div className={`${styles.msg} ${live ? "anim-row" : ""}`}>
      <div className={styles.gutter}>
        {formatClock(message.at)}
        {GUTTER_GAP}
        <span className={label.className}>{label.text}</span>
      </div>
      <div className={bodyClasses.join(" ")}>
        <Body message={message} progress={progress} />
        {message.delivery === "failed" && (
          <div className={styles.failed}>
            <span>failed: {message.error ?? "not delivered"}</span>
            {origin && <Button onClick={() => onRetry(origin)}>Retry</Button>}
          </div>
        )}
      </div>
    </div>
  );
}
