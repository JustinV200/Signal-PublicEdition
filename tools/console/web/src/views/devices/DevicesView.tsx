// The Connected devices page: every device Signal uses with its live state in
// words, polled from GET /api/devices while open. The webcam row's Open camera
// button shows its live stream below the list (a read, like every status
// here; nothing goes to Claude). The owner's Away/Here toggle sits at the top.
import { useState } from "react";
import { formatRelative, useTicker } from "../../time";
import { Button } from "../../ui";
import { AwayControl } from "./AwayControl";
import { CameraPanel } from "./CameraPanel";
import { DeviceRow } from "./DeviceRow";
import styles from "./devices.module.css";
import { useDevices } from "./useDevices";

const HINT =
  "Live state of everything Signal uses, checked every 5 seconds while this page is open. Open camera shows the whiteboard webcam here; it doesn't move or switch anything.";
const NO_CAMERA = "the camera isn't live";
const AGE_TICK_MS = 5000;

/** The devices view. */
export function DevicesView() {
  const { payload, error, readAt, setAway } = useDevices();
  const [isCameraOpen, setCameraOpen] = useState(false);
  const now = useTicker(AGE_TICK_MS);

  return (
    <div className={`col ${styles.view}`}>
      <div className={styles.header}>
        <span className="hud-label">Devices</span>
        <span className={styles.meta}>
          {error
            ? `Not updating: ${error}`
            : readAt
              ? `checked ${formatRelative(readAt, now)}`
              : "checking…"}
        </span>
      </div>
      <p className={styles.hint}>{HINT}</p>
      {payload && <AwayControl away={payload.away} onChange={setAway} />}
      <ul className={styles.list}>
        {payload?.devices.map((device) => (
          <DeviceRow key={device.id} device={device}>
            {device.id === "webcam" &&
              (isCameraOpen ? (
                <Button onClick={() => setCameraOpen(false)}>Close camera</Button>
              ) : (
                <Button
                  onClick={() => setCameraOpen(true)}
                  disabledReason={device.canOpen ? undefined : NO_CAMERA}
                >
                  Open camera
                </Button>
              ))}
          </DeviceRow>
        ))}
      </ul>
      {isCameraOpen && <CameraPanel onClose={() => setCameraOpen(false)} />}
    </div>
  );
}
