// The webcam's live view, open while this panel is mounted. It reads the
// console's camera proxy (api's openCameraStream), shows each frame as it
// arrives, and closes the stream on unmount, which frees the whiteboard's
// viewer slot. Errors (the 2-viewer cap, no picture) come from the server
// already in words. Each old frame's blob: URL is revoked when replaced.
import { useEffect, useState } from "react";
import { openCameraStream } from "../../api";
import { Button } from "../../ui";
import styles from "./devices.module.css";

interface CameraPanelProps {
  onClose: () => void;
}

type CameraView =
  | { kind: "connecting" }
  | { kind: "live"; url: string }
  | { kind: "error"; message: string }
  | { kind: "ended" };

const ENDED = "The camera stream ended (the camera stopped, or the whiteboard went away).";

/** The camera panel with its Close camera button. */
export function CameraPanel({ onClose }: CameraPanelProps) {
  const [view, setView] = useState<CameraView>({ kind: "connecting" });

  useEffect(() => {
    let lastUrl: string | null = null;
    const close = openCameraStream({
      onFrame: (url) => {
        if (lastUrl) URL.revokeObjectURL(lastUrl);
        lastUrl = url;
        setView({ kind: "live", url });
      },
      onError: (message) => setView({ kind: "error", message }),
      onEnd: () => setView({ kind: "ended" }),
    });
    return () => {
      close();
      if (lastUrl) URL.revokeObjectURL(lastUrl);
    };
  }, []);

  return (
    <section className={`panel ${styles.camera}`} aria-label="camera view">
      <div className={styles.cameraHead}>
        <span>
          Camera:{" "}
          {view.kind === "live" ? "live" : view.kind === "connecting" ? "connecting…" : "stopped"}
        </span>
        <Button onClick={onClose}>Close camera</Button>
      </div>
      {view.kind === "live" && (
        <img className={styles.frame} src={view.url} alt="The whiteboard webcam, live" />
      )}
      {view.kind === "error" && <p className={styles.problem}>{view.message}</p>}
      {view.kind === "ended" && <p className={styles.problem}>{ENDED}</p>}
    </section>
  );
}
