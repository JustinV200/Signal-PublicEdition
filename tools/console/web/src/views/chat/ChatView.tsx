// The chat view: the session log with day dividers, the working row and
// the `↓ N new` pill, and the claim help while no Claude session is linked.
// While it is scrolled to the bottom it marks every row seen (the tab's count).
// Rows that arrive after mount animate in; replayed history does not. It sits
// on the shared frame (one left edge with the status line) inside a 96ch
// reading column.
import { Fragment, useState } from "react";
import type { RefObject } from "react";
import { NewPill, useFollow } from "../../scroll";
import { actionProgress, claudeLink, useStore } from "../../state";
import { isSameDay, toMs } from "../../time";
import { ClaimHelp } from "./ClaimHelp";
import { DateDivider } from "./DateDivider";
import { EmptyChat } from "./EmptyChat";
import { MessageRow } from "./MessageRow";
import { WorkingRow } from "./WorkingRow";

/** The chat stream inside the shared scrolling `<main>`. */
export function ChatView({ scrollRef }: { scrollRef: RefObject<HTMLElement | null> }) {
  const { state, dispatch, sender } = useStore();
  const { messages, busySince, server } = state;
  const [mountedAt] = useState(() => Date.now());
  // Live (MessageRow's own test), and not the owner's own send: only a row
  // that arrived after mount is shown top-first when tall; replayed history
  // always lands at the end.
  const newest = messages.at(-1);
  const isLiveEnd = newest !== undefined && newest.role !== "you" && toMs(newest.at) >= mountedAt;
  // Only messages are rows the pill counts. The working row is the tail: it
  // re-pins the end as it comes and goes. A reply and the end of its turn can
  // land in one render, so netting the two into one count would hide the reply.
  const follow = useFollow(scrollRef, messages.length, {
    // At the bottom, every row is seen: the tab's and the window title's `N new` clear.
    onAtBottom: () => dispatch({ type: "chatSeen" }),
    isLiveEnd,
    tailKey: busySince,
  });
  const link = server ? claudeLink(server.orchestrator) : undefined;

  return (
    <div className="frame view">
      <div className="col">
        {messages.length === 0 && (
          <EmptyChat link={link} label={server?.orchestrator.label ?? ""} />
        )}
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
        {messages.length > 0 && link && link !== "linked" && <ClaimHelp link={link} />}
        <WorkingRow busySince={busySince} />
        <NewPill count={follow.newCount} onClick={follow.jumpToBottom} />
      </div>
    </div>
  );
}
