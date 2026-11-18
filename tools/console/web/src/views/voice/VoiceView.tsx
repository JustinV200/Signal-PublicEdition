// The voice buffer: Voice's state in words, one button whose label follows
// it (Start voice when stopped, Stop voice while running or starting;
// "Working…" only while its own action runs), then the feed. A click's
// outcome shows on the shell's result strip (app/ResultStrip).
import { useState } from "react";
import type { RefObject } from "react";
import { EmptyState } from "../../empty";
import { NewPill, useFollow } from "../../scroll";
import { useConfirmGate, usePendingActions, useStore } from "../../state";
import { PhaseDot, startedByWords, toDotPhase } from "../../status";
import { toMs } from "../../time";
import { Button } from "../../ui";
import { FeedRow } from "./FeedRow";
import { voiceButton } from "./voiceButton";
import styles from "./voice.module.css";

/** The voice view inside the shared scrolling `<main>`. */
export function VoiceView({ scrollRef }: { scrollRef: RefObject<HTMLElement | null> }) {
  const { state } = useStore();
  const { request } = useConfirmGate();
  const pending = usePendingActions();
  const voice = state.server?.voice;
  const feed = state.voiceFeed;
  const [mountedAt] = useState(() => Date.now());
  const follow = useFollow(scrollRef, feed.length);

  const running = voice?.running ?? false;
  const phase = toDotPhase(voice);
  const button = voiceButton(voice, pending);
  const startedBy = startedByWords(voice?.startedBy);

  return (
    <div className="frame view">
      <div className="view-header">
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
        {running && startedBy && <span className={styles.meta}>{startedBy}</span>}
        <span className={styles.actions}>
          <Button onClick={() => request(button.action)} pending={button.pending}>
            {button.label}
          </Button>
        </span>
      </div>
      {feed.length === 0 && (
        <EmptyState label="Nothing heard yet">
          When Voice hears or says something, it shows here.
        </EmptyState>
      )}
      <div className={styles.feed}>
        {feed.map((event) => (
          <FeedRow key={event.id} event={event} live={toMs(event.at) >= mountedAt} />
        ))}
      </div>
      <NewPill count={follow.newCount} onClick={follow.jumpToBottom} />
    </div>
  );
}
