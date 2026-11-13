// AudioWorklet for the phone page: the mic, low-passed and downsampled to 16 kHz mono int16,
// posted to app.js in fixed chunks. The hub's Whisper and VAD want 16 kHz; the phone's audio
// runs at its own rate (usually 48 kHz), so resample here, off the main thread.

const CHUNK_SAMPLES = 1024; // 64 ms at 16 kHz per WebSocket message
const CUTOFF_HZ = 7000; // just under the 8 kHz Nyquist limit of the output
const INT16_MAX = 32767;

/** RBJ cookbook low-pass biquad (Q = 1/sqrt 2) with its own state. */
function lowPass(cutoffHz, rate) {
  const w0 = (2 * Math.PI * cutoffHz) / rate;
  const alpha = Math.sin(w0) * Math.SQRT1_2;
  const cos = Math.cos(w0);
  const a0 = 1 + alpha;
  return {
    b0: (1 - cos) / 2 / a0, b1: (1 - cos) / a0, b2: (1 - cos) / 2 / a0,
    a1: (-2 * cos) / a0, a2: (1 - alpha) / a0,
    x1: 0, x2: 0, y1: 0, y2: 0,
  };
}

function filterSample(f, x) {
  const y = f.b0 * x + f.b1 * f.x1 + f.b2 * f.x2 - f.a1 * f.y1 - f.a2 * f.y2;
  f.x2 = f.x1; f.x1 = x; f.y2 = f.y1; f.y1 = y;
  return y;
}

class MicDownsampler extends AudioWorkletProcessor {
  constructor(options) {
    super();
    // `sampleRate` is the worklet scope's global: the context's rate.
    this.step = sampleRate / options.processorOptions.targetRate;
    // Two biquads in a row (24 dB/octave) keep aliased hiss out of the speech band.
    this.filters = this.step > 1 ? [lowPass(CUTOFF_HZ, sampleRate), lowPass(CUTOFF_HZ, sampleRate)] : [];
    // Input position of the next output sample, relative to the current block.
    // It can be -1..0, between the previous block's last sample and this block's first.
    this.position = 0;
    this.previous = 0;
    this.chunk = new Int16Array(CHUNK_SAMPLES);
    this.filled = 0;
  }

  process(inputs) {
    const input = inputs[0] && inputs[0][0];
    if (!input) return true;
    const samples = input.map((x) => this.filters.reduce((y, f) => filterSample(f, y), x));
    // Linear interpolation between neighbouring (filtered) input samples.
    while (this.position < samples.length - 1) {
      const index = Math.floor(this.position);
      const fraction = this.position - index;
      const before = index < 0 ? this.previous : samples[index];
      this.emit(before + (samples[index + 1] - before) * fraction);
      this.position += this.step;
    }
    this.position -= samples.length;
    this.previous = samples[samples.length - 1];
    return true;
  }

  emit(value) {
    this.chunk[this.filled++] = Math.round(Math.max(-1, Math.min(1, value)) * INT16_MAX);
    if (this.filled < CHUNK_SAMPLES) return;
    this.port.postMessage(this.chunk.buffer, [this.chunk.buffer]);
    this.chunk = new Int16Array(CHUNK_SAMPLES);
    this.filled = 0;
  }
}

registerProcessor("mic-downsampler", MicDownsampler);
