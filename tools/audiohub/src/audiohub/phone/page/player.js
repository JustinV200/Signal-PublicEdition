// Speech from the hub, played gaplessly through WebAudio on whatever the phone outputs to
// (the paired glasses). Each binary message is one chunk: an 8-byte header (uint32 id,
// uint32 sample rate, little-endian) then int16 mono PCM; see audiohub/phone/protocol.py.

const HEADER_BYTES = 8;
const INT16_FULL_SCALE = 32768;
// Ack this long before a chunk ends, so the hub's next chunk arrives in time to be
// queued right behind it. The hub's echo tail covers this lead after the last chunk.
const ACK_LEAD_S = 0.3;
// Start a chunk this far after "now" so its first samples aren't clipped.
const START_LEAD_S = 0.05;

export class SpeechPlayer {
  /**
   * @param {AudioContext} context Plays the speech.
   * @param {(id: number) => void} onPlayed Called with a chunk's id when it has (nearly) played.
   */
  constructor(context, onPlayed) {
    this.context = context;
    this.onPlayed = onPlayed;
    // When the last queued chunk ends, in context time; the next one starts there.
    this.queueEnd = 0;
    // Playing or queued source node -> its ack timer.
    this.playing = new Map();
  }

  /** Queue one speech chunk (an ArrayBuffer from the socket) behind any that are playing. */
  play(message) {
    const header = new DataView(message, 0, HEADER_BYTES);
    const id = header.getUint32(0, true);
    const rate = header.getUint32(4, true);
    const pcm = new Int16Array(message, HEADER_BYTES);
    if (pcm.length === 0) {
      this.onPlayed(id);
      return;
    }
    const buffer = this.context.createBuffer(1, pcm.length, rate);
    const channel = buffer.getChannelData(0);
    for (let i = 0; i < pcm.length; i++) channel[i] = pcm[i] / INT16_FULL_SCALE;
    const node = this.context.createBufferSource();
    node.buffer = buffer;
    node.connect(this.context.destination);
    const startAt = Math.max(this.context.currentTime + START_LEAD_S, this.queueEnd);
    node.start(startAt);
    this.queueEnd = startAt + buffer.duration;
    const ackInMs = Math.max(0, (this.queueEnd - ACK_LEAD_S - this.context.currentTime) * 1000);
    this.playing.set(node, setTimeout(() => this.onPlayed(id), ackInMs));
    node.onended = () => this.playing.delete(node);
  }

  /** Cut everything playing or queued, without acking it (the hub already moved on). */
  stop() {
    for (const [node, timer] of this.playing) {
      clearTimeout(timer);
      node.onended = null;
      node.stop();
    }
    this.playing.clear();
    this.queueEnd = 0;
  }
}
