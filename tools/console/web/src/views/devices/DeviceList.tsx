// The device rows: every device Signal uses with its live state in words (from
// useDevices' poll). The webcam row's Open camera button shows its live
// stream below the list (a read, like every status here; nothing goes to
// Claude). Part of System's DEVICES group.
import { useState } from "react";
import type { DeviceRow as Device } from "../../api";
import { Button } from "../../ui";
import { CameraPanel } from "./CameraPanel";
import { DeviceRow } from "./DeviceRow";
import styles from "./devices.module.css";

const NO_CAMERA = "the camera isn't live";

/**
 * The rows, then the camera panel while it's open.
 *
 * @param devices The last good read's rows; empty before the first.
 */
export function DeviceList({ devices }: { devices: readonly Device[] }) {
  const [isCameraOpen, setCameraOpen] = useState(false);
  return (
    <>
      <ul className={styles.list}>
        {devices.map((device) => (
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
    </>
  );
}
