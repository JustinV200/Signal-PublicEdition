// The hand-rolled text/event-stream parser must cope with chunks split
// anywhere (a CRLF pair included), comments and multi-line data.
import { describe, expect, it } from "vitest";
import { createSseParser } from "../../src/api";

// Mixed CRLF and LF endings; 1-char chunks hit every split point, 7 is a middling one.
const STREAM =
  ': keepalive\r\n\r\nevent: state\r\ndata: {"a":1}\r\n\r\nevent: message\ndata: line one\ndata: line two\n\ndata: tail\n\n';
const CHUNK_SIZES = [1, 7];

describe("createSseParser", () => {
  it("reassembles events across arbitrary chunk boundaries, including inside a CRLF", () => {
    for (const size of CHUNK_SIZES) {
      const parser = createSseParser();
      const events = [];
      for (let i = 0; i < STREAM.length; i += size)
        events.push(...parser.feed(STREAM.slice(i, i + size)));
      expect(events, `chunk size ${size}`).toEqual([
        { event: "state", data: '{"a":1}' },
        { event: "message", data: "line one\nline two" },
        { event: "message", data: "tail" },
      ]);
    }
  });
});
