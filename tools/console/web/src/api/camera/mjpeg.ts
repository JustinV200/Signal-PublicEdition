// Reads the JPEG frames out of the whiteboard camera's MJPEG stream
// (multipart/x-mixed-replace), as the console server passes it through. Each
// part has a Content-Length header, so a frame is cut by its length instead
// of scanning the image bytes for the boundary.

// A 960 px JPEG is well under 1 MB; anything near this is a broken stream.
export const MAX_FRAME_BYTES = 8 * 1024 * 1024;
const HEADER_END = [13, 10, 13, 10]; // \r\n\r\n
// Headers longer than this with no blank line mean the stream isn't MJPEG.
const MAX_HEADER_BYTES = 4096;
const CONTENT_LENGTH = /content-length:\s*(\d+)/i;

export interface MjpegParser {
  /** Adds bytes from the stream; returns the frames they completed. Throws on a broken stream. */
  feed(chunk: Uint8Array): Uint8Array<ArrayBuffer>[];
}

function indexOfHeaderEnd(buffer: Uint8Array): number {
  outer: for (let i = 0; i + HEADER_END.length <= buffer.length; i++) {
    for (let j = 0; j < HEADER_END.length; j++) if (buffer[i + j] !== HEADER_END[j]) continue outer;
    return i;
  }
  return -1;
}

function concat(a: Uint8Array, b: Uint8Array): Uint8Array {
  const joined = new Uint8Array(a.length + b.length);
  joined.set(a);
  joined.set(b, a.length);
  return joined;
}

/** A parser holding the bytes of a part that has not fully arrived. */
export function createMjpegParser(): MjpegParser {
  let buffer: Uint8Array = new Uint8Array(0);
  // The current part's length once its headers are read; null while reading headers.
  let length: number | null = null;

  const nextFrame = (): Uint8Array<ArrayBuffer> | null => {
    if (length === null) {
      const end = indexOfHeaderEnd(buffer);
      if (end < 0) {
        if (buffer.length > MAX_HEADER_BYTES) throw new Error("camera stream: no part headers");
        return null;
      }
      const headers = new TextDecoder().decode(buffer.subarray(0, end));
      buffer = buffer.subarray(end + HEADER_END.length);
      const match = CONTENT_LENGTH.exec(headers);
      if (!match) return nextFrame(); // a stray blank line between parts
      length = Number(match[1]);
      if (length <= 0 || length > MAX_FRAME_BYTES) throw new Error("camera stream: bad frame size");
    }
    if (buffer.length < length) return null;
    const frame = buffer.slice(0, length);
    buffer = buffer.subarray(length);
    length = null;
    return frame;
  };

  return {
    feed(chunk) {
      buffer = concat(buffer, chunk);
      const frames: Uint8Array<ArrayBuffer>[] = [];
      for (let frame = nextFrame(); frame; frame = nextFrame()) frames.push(frame);
      return frames;
    },
  };
}
