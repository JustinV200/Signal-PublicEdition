// The Voice view's one button: Start while stopped, Stop while running or
// starting (so a slow or hung start can be stopped), and "Working…" only for a
// pending action of the label shown.
import { describe, expect, it } from "vitest";
import type { ActionName, VoiceState } from "../../../src/api";
import { voiceButton } from "../../../src/views/voice";

const STOPPED: VoiceState = { running: false, phase: "off", startedBy: null };
const STARTING: VoiceState = { running: true, phase: "starting", startedBy: "console" };
const RUNNING: VoiceState = { running: true, phase: "listening", startedBy: "console" };

describe("voiceButton", () => {
  it.each<[string, VoiceState | undefined, ActionName[], string, boolean]>([
    ["stopped", STOPPED, [], "Start voice", false],
    ["before the first snapshot", undefined, [], "Start voice", false],
    ["stopped, start sent", STOPPED, ["voice.start"], "Start voice", true],
    ["starting, start still pending", STARTING, ["voice.start"], "Stop voice", false],
    ["running", RUNNING, [], "Stop voice", false],
    ["running, stop sent", RUNNING, ["voice.stop"], "Stop voice", true],
  ])("%s", (_case, voice, pending, label, isPending) => {
    expect(voiceButton(voice, new Set(pending))).toMatchObject({ label, pending: isPending });
  });
});
