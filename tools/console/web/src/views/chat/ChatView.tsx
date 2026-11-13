// The default view: the session log with day dividers, the working row and
// the `↓ N new` pill. Rows that arrive after mount animate in; replayed
// history does not.
import { Fragment, useState } from "react";
import type { RefObject } from "react";
import { NewPill, useFollow } from "../../scroll";
import { actionProgress, useStore } from "../../state";
import { isSameDay, toMs } from "../../time";
import styles from "./chat.module.css";
import { DateDivider } from "./DateDivider";
import { EmptyChat } from "./EmptyChat";
import { MessageRow } from "./MessageRow";
import { WorkingRow } from "./WorkingRow";

/** The chat stream inside the shared scrolling `<main>`. */
export function ChatView({ scrollRef }: { scrollRef: RefObject<HTMLElement | null> }) {
  const { state, sender } = useStore();
  const { messages, busySince, server } = state;
  const [mountedAt] = useState(() => Date.now());
  const follow = useFollow(scrollRef, messages.length + (busySince === null ? 0 : 1));

  return (
    <div className={`col ${styles.view}`}>
      {messages.length === 0 && <EmptyChat label={server?.orchestrator.label} />}
      {messages.map((message, index) => (
        // A local send keeps its temp id as the key, so taking the server id does not remount the row.
        <Fragment key={message.localId ?? message.id}>
          {(index === 0 || !isSameDay(messages[index - 1].at, message.at)) && (
            <DateDivider at={message.at} />
          )}
          <MessageRow
            message={message}
            live={toMs(message.at) >= mountedAt}
            progress={message.kind === "action" ? actionProgress(message) : undefined}
            onRetry={sender.retry}
          />
        </Fragment>
      ))}
      <WorkingRow busySince={busySince} />
      <NewPill count={follow.newCount} onClick={follow.jumpToBottom} />
    </div>
  );
}
