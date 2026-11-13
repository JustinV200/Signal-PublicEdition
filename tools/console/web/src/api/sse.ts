// A text/event-stream parser for streams read with fetch (EventSource cannot
// send the token header). Pure: feed it text chunks, get events back.
// Handles chunks split anywhere, CRLF, multi-line data and `:` comments.

export interface SseEvent {
  /** The `event:` field, or `message` when absent (as EventSource does). */
  event: string;
  /** The `data:` lines joined with newlines. */
  data: string;
}

const DEFAULT_EVENT = "message";

export interface SseParser {
  /** Parses `chunk` and returns the events completed by it. */
  feed: (chunk: string) => SseEvent[];
}

/** Creates a parser that keeps partial lines and the open event between chunks. */
export function createSseParser(): SseParser {
  let buffered = "";
  let eventName = DEFAULT_EVENT;
  let dataLines: string[] = [];

  const applyLine = (line: string, out: SseEvent[]) => {
    if (line === "") {
      // Blank line dispatches, but only if any data was seen (per the spec).
      if (dataLines.length > 0) out.push({ event: eventName, data: dataLines.join("\n") });
      eventName = DEFAULT_EVENT;
      dataLines = [];
      return;
    }
    if (line.startsWith(":")) return;
    const colon = line.indexOf(":");
    const field = colon === -1 ? line : line.slice(0, colon);
    // One space after the colon is part of the separator, not the value.
    const value = colon === -1 ? "" : line.slice(colon + 1).replace(/^ /, "");
    if (field === "event") eventName = value;
    else if (field === "data") dataLines.push(value);
    // `id` and `retry` are ignored: reconnect is handled by events.ts.
  };

  return {
    feed(chunk) {
      buffered += chunk;
      // A trailing `\r` may be half of a CRLF split across chunks: hold it back,
      // or the `\n` that follows would count as a second, spurious line end.
      const heldCr = buffered.endsWith("\r") ? "\r" : "";
      const lines = buffered.slice(0, buffered.length - heldCr.length).split(/\r\n|\r|\n/);
      // The last piece is either empty (chunk ended on a newline) or a partial line.
      buffered = (lines.pop() ?? "") + heldCr;
      const out: SseEvent[] = [];
      for (const line of lines) applyLine(line, out);
      return out;
    },
  };
}
