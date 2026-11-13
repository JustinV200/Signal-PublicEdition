// What the chat view shows before the first message.
import styles from "./chat.module.css";

/** Three faint lines: who we are connected to, how to start, where the rest is. */
export function EmptyChat({ label }: { label: string | undefined }) {
  return (
    <div className={styles.empty}>
      <div>Connected to {label || "the console"}.</div>
      <div>Type a message below and press Enter, or click Send. Claude answers here.</div>
      <div>
        The Scope tab is the radar, Voice and Boards hold the voice hub and the projector, and Help
        lists the shortcuts.
      </div>
    </div>
  );
}
