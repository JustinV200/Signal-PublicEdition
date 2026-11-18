// The webcam's live view for System's camera panel: GET /api/camera/stream
// with the page's own X-Console-Token (the console server adds the
// whiteboard's token upstream, so this page never holds it). Frames come out as blob: URLs for an
// <img>; the caller revokes each one when the next replaces it. Closing aborts
// the fetch, which ends the stream on the server and frees the camera's slot.
import { errorMessage, fetchOrExplain, rejectUnauthorized } from "../client";
import { createMjpegParser } from "./mjpeg";
import { authHeaders } from "../token";

const STREAM_PATH = "/api/camera/stream";

export interface CameraHandlers {
  /** A new frame's blob: URL. */
  onFrame: (url: string) => void;
  /** The stream could not open or broke; `message` is plain words for the page. */
  onError: (message: string) => void;
  /** The server ended the stream (the camera stopped or the whiteboard went away). */
  onEnd: () => void;
}

async function readFrames(handlers: CameraHandlers, signal: AbortSignal): Promise<void> {
  const response = await fetchOrExplain(STREAM_PATH, {
    headers: authHeaders(),
    credentials: "same-origin",
    signal,
  });
  rejectUnauthorized(response);
  if (!response.ok || !response.body) {
    handlers.onError(await errorMessage(STREAM_PATH, response));
    return;
  }
  const reader = response.body.getReader();
  const parser = createMjpegParser();
  for (;;) {
    const { value, done } = await reader.read();
    if (done) return handlers.onEnd();
    for (const frame of parser.feed(value)) {
      handlers.onFrame(URL.createObjectURL(new Blob([frame], { type: "image/jpeg" })));
    }
  }
}

/** Opens the camera stream. Returns a function that closes it. */
export function openCameraStream(handlers: CameraHandlers): () => void {
  const controller = new AbortController();
  readFrames(handlers, controller.signal).catch((error: unknown) => {
    if (controller.signal.aborted) return;
    handlers.onError(error instanceof Error ? error.message : String(error));
  });
  return () => controller.abort();
}
