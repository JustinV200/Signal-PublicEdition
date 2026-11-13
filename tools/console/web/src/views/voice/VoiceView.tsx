// The voice buffer: the hub's state in words, Start and Stop buttons (the one
// that does not apply is disabled with its reason; the one just clicked reads
// "Working…" until the console has run it), the last click's outcome, a hint,
// then the feed. A hub still loading reads "starting": Stop works, Start waits.
import { useState } from "react";
import type { RefObject } from "react";
import { NewPill, useFollow } from "../../scroll";
import { usePendingActions, useStore } from "../../state";
import { PhaseDot, toDotPhase } from "../../status";
import { toMs } from "../../time";
import { Button } from "../../ui";
import { FeedRow } from "./FeedRow";
import { lastVoiceAction } from "./lastAction";
import styles from "./voice.module.css";

const HINT =
  "Start and Stop run at once in the console; the result shows above and in Chat. What the hub hears and says shows below.";
const ALREADY_RUNNING = "already running";
const STARTING = "starting";
const NOT_RUNNING = "not running";

/** The voice view inside the shared scrolling `<main>`. */
export function VoiceView({ scrollRef }: { scrollRef: RefObject<HTMLElement | null> }) {
  const { state, sender } = useStore();
  const pending = usePendingActions();
  const voice = state.server?.voice;
  const feed = state.voiceFeed;
  const [mountedAt] = useState(() => Date.now());
  const follow = useFollow(scrollRef, feed.length);

  const running = voice?.running ?? false;
  const phase = toDotPhase(voice);
  const lastAction = lastVoiceAction(state.messages);

  return (
    <div className={`col ${styles.view}`}>
      <div className={styles.header}>
        <span className="hud-label">Voice</span>
        <span className={styles.status}>
          <PhaseDot phase={phase} />
          {running ? (
            <>
              Running <span className={styles.sep}>·</span> {phase}
            </>
          ) : (
            "Stopped"
          )}
        </span>
        {running && voice?.startedBy && (
          <span className={styles.meta}>started by {voice.startedBy}</span>
        )}
        <span className={styles.actions}>
          <Button
            onClick={() => void sender.runAction("voice.start")}
            pending={pending.has("voice.start")}
            disabledReason={phase === "starting" ? STARTING : running ? ALREADY_RUNNING : undefined}
          >
            Start voice
          </Button>
          <Button
            onClick={() => void sender.runAction("voice.stop")}
            pending={pending.has("voice.stop")}
            disabledReason={running ? undefined : NOT_RUNNING}
          >
            Stop voice
          </Button>
        </span>
      </div>
      {lastAction && <p className={styles.lastAction}>{lastAction}</p>}
      <p className={styles.hint}>{HINT}</p>
      {feed.length === 0 && <div className={styles.empty}>Nothing heard yet.</div>}
      <div className={styles.feed}>
        {feed.map((event) => (
          <FeedRow key={event.id} event={event} live={toMs(event.at) >= mountedAt} />
        ))}
      </div>
      <NewPill count={follow.newCount} onClick={follow.jumpToBottom} />
    </div>
  );
}
