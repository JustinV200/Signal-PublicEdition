// The camera view cuts JPEGs out of the MJPEG stream by Content-Length, so a
// frame split across chunks still comes out whole, and a broken stream throws
// instead of buffering forever.
import { describe, expect, it } from "vitest";
import { createMjpegParser } from "../../../src/api";

const encoder = new TextEncoder();

function part(body: string): Uint8Array {
  const head = `--frame\r\nContent-Type: image/jpeg\r\nContent-Length: ${body.length}\r\n\r\n`;
  return encoder.encode(`${head}${body}\r\n`);
}

describe("createMjpegParser", () => {
  it("returns each frame whole, even when chunks split headers and bodies", () => {
    const stream = new Uint8Array([...part("JPEG-ONE"), ...part("two")]);
    const parser = createMjpegParser();
    const frames = [5, 40, 1, stream.length].flatMap((cut, i, cuts) =>
      parser.feed(stream.subarray(i === 0 ? 0 : cuts[i - 1], Math.min(cut, stream.length))),
    );
    expect(frames.map((frame) => new TextDecoder().decode(frame))).toEqual(["JPEG-ONE", "two"]);
  });

  it.each([
    ["an impossible frame size", "--frame\r\nContent-Length: 999999999\r\n\r\n"],
    ["headers that never end", "x".repeat(5000)],
  ])("throws on %s", (_, text) => {
    expect(() => createMjpegParser().feed(encoder.encode(text))).toThrow(/camera stream/);
  });
});
