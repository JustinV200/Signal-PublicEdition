// The System page (Ctrl+6; Ctrl+7 and Ctrl+8 too): YOU (the Away/Here
// switch), CONSOLE (the console's own health checks), TOOLS (every tool's
// health and its Set up button), DEVICES (the device rows and the camera),
// MODELS (the pickers) and APPEARANCE (dark or light). CONSOLE and TOOLS are
// two groups of one health list (setup's HealthList). It holds the one
// devices poll (YOU and DEVICES share its answer), so the poll runs only
// while System is open and the page is visible.
import { AwayControl, DeviceList, DevicesMeta, useDevices } from "../devices";
import { AppearanceSection } from "./AppearanceSection";
import { ConsoleSection } from "./ConsoleSection";
import { ModelsSection } from "./ModelsSection";
import { Section } from "./Section";
import { ToolsSection } from "./ToolsSection";

/** The system view. */
export function SystemView() {
  const { payload, error, readAt, setAway } = useDevices();
  return (
    <div className="frame view">
      <div className="view-header">
        <span className="hud-label">System</span>
      </div>
      {payload && <AwayControl away={payload.away} onChange={setAway} />}
      <ConsoleSection />
      <ToolsSection />
      <Section title="Devices" meta={<DevicesMeta error={error} readAt={readAt} />}>
        <DeviceList devices={payload?.devices ?? []} />
      </Section>
      <ModelsSection />
      <AppearanceSection />
    </div>
  );
}
