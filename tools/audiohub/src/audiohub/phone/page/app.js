// The phone page of audiohub's phone bridge: streams the phone mic to the hub on the PC and
// plays the hub's speech on whatever the phone outputs to (the paired glasses). One
// WebSocket carries both; audiohub/phone/protocol.py defines the messages.
import { SpeechPlayer } from "./player.js";

const MIC_RATE = 16000;
// Sent by the hub when a newer page took over; this page then stops reconnecting.
const REPLACED_CLOSE_CODE = 4000;
const RECONNECT_FIRST_MS = 1000;
const RECONNECT_MAX_MS = 15000;
// Failed reconnects before suggesting the link is stale (a restarted hub has a new token).
const STALE_LINK_ATTEMPTS = 4;
// Mic audio stuck on a stalled connection beyond this is dropped, so it can't lag behind.
const MAX_BUFFERED_BYTES = 64 * 1024;

const ui = {
  toggle: document.getElementById("toggle"),
  status: document.getElementById("status"),
  detail: document.getElementById("detail"),
  connection: document.getElementById("connection"),
  warning: document.getElementById("warning"),
};

let session = null;

/** One Start..Stop run: the audio graph, the screen wake lock and the socket. */
class Session {
  constructor() {
    this.isActive = true;
    this.isMicOn = true;
    this.socket = null;
    this.retryMs = RECONNECT_FIRST_MS;
    this.failedAttempts = 0;
    this.wakeLock = null;
  }

  async start() {
    // Created inside the tap: phones only let audio start from a user gesture.
    this.context = new AudioContext({ latencyHint: "interactive" });
    await this.context.resume();
    this.player = new SpeechPlayer(this.context, (id) => this.send({ type: "played", id }));
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 },
    });
    await this.context.audioWorklet.addModule("/mic-worklet.js");
    const mic = this.context.createMediaStreamSource(this.stream);
    const downsampler = new AudioWorkletNode(this.context, "mic-downsampler", {
      processorOptions: { targetRate: MIC_RATE },
    });
    downsampler.port.onmessage = (event) => this.sendMic(event.data);
    // The worklet outputs silence; connecting it to the output keeps it running.
    mic.connect(downsampler).connect(this.context.destination);
    await this.keepScreenOn();
    // Stop may have been tapped while the mic permission prompt was up.
    if (this.isActive) this.connect();
    else this.stop();
  }

  stop() {
    this.isActive = false;
    clearTimeout(this.retryTimer);
    this.socket?.close(1000, "stopped");
    this.player?.stop();
    this.stream?.getTracks().forEach((track) => track.stop());
    if (this.context && this.context.state !== "closed") this.context.close();
    this.wakeLock?.release();
    this.wakeLock = null;
  }

  connect() {
    const scheme = location.protocol === "https:" ? "wss" : "ws";
    const socket = new WebSocket(`${scheme}://${location.host}/ws`);
    socket.binaryType = "arraybuffer";
    socket.onopen = () => {
      this.retryMs = RECONNECT_FIRST_MS;
      this.failedAttempts = 0;
      ui.connection.textContent = "Connected to the PC.";
    };
    socket.onmessage = (event) => this.receive(event.data);
    socket.onclose = (event) => this.closed(socket, event);
    this.socket = socket;
  }

  closed(socket, event) {
    if (socket !== this.socket) return;
    this.socket = null;
    this.player.stop();
    if (!this.isActive) return;
    if (event.code === REPLACED_CLOSE_CODE) {
      stopSession("Opened on another page. Tap Start to use this one instead.");
      return;
    }
    this.failedAttempts += 1;
    const hint = this.failedAttempts >= STALE_LINK_ATTEMPTS
      ? " If the hub restarted, open the new link from `audiohub phone-link`."
      : "";
    ui.connection.textContent = `Not connected; retrying in ${Math.round(this.retryMs / 1000)} s.${hint}`;
    this.retryTimer = setTimeout(() => this.connect(), this.retryMs);
    this.retryMs = Math.min(this.retryMs * 2, RECONNECT_MAX_MS);
  }

  receive(data) {
    if (typeof data !== "string") {
      this.player.play(data);
      return;
    }
    const message = JSON.parse(data);
    if (message.type === "mic") this.isMicOn = message.on;
    else if (message.type === "stop") this.player.stop();
    else if (message.type === "status") showStatus(message.label, message.detail);
  }

  sendMic(pcm) {
    const socket = this.socket;
    // With barge-in off the hub turns the mic off while it speaks (half-duplex), so the
    // glasses don't hear it. With barge-in on the mic stays on and the hub filters echoes.
    if (!this.isMicOn || socket?.readyState !== WebSocket.OPEN) return;
    if (socket.bufferedAmount > MAX_BUFFERED_BYTES) return;
    socket.send(pcm);
  }

  send(message) {
    if (this.socket?.readyState === WebSocket.OPEN) this.socket.send(JSON.stringify(message));
  }

  async keepScreenOn() {
    if (!("wakeLock" in navigator)) {
      ui.warning.textContent = "This browser can't keep the screen on: turn auto-lock off while talking.";
      return;
    }
    try {
      this.wakeLock = await navigator.wakeLock.request("screen");
      ui.warning.textContent = "";
    } catch (error) {
      ui.warning.textContent = `Couldn't keep the screen on (${error.message}); turn auto-lock off.`;
    }
  }
}

function showStatus(label, detail) {
  ui.status.textContent = label;
  ui.detail.textContent = detail;
}

function stopSession(reason) {
  session?.stop();
  session = null;
  ui.toggle.textContent = "Start";
  ui.toggle.setAttribute("aria-pressed", "false");
  showStatus("stopped", "");
  ui.connection.textContent = reason;
}

ui.toggle.addEventListener("click", async () => {
  if (session) {
    stopSession("Stopped.");
    return;
  }
  session = new Session();
  ui.toggle.textContent = "Stop";
  ui.toggle.setAttribute("aria-pressed", "true");
  ui.connection.textContent = "Starting...";
  try {
    await session.start();
  } catch (error) {
    stopSession(`Couldn't start: ${error.message}`);
  }
});

// The wake lock ends whenever the page is hidden, and phones may suspend its audio,
// so take both back when the owner returns to the page.
document.addEventListener("visibilitychange", () => {
  if (!session || document.visibilityState !== "visible") return;
  session.context?.resume();
  session.keepScreenOn();
});
