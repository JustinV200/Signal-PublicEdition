# audiohub.tts

Text-to-speech for audiohub. It turns a reply into clean, speakable sentences and then into audio, using the [Kokoro](https://github.com/thewh1teagle/kokoro-onnx) v1.0 ONNX model. The default voice is British male `bm_george`, language `en-gb`, with 24 kHz mono float32 output.

The voice output (`loop`) runs this pipeline for every message:
1. `clean_for_speech`
2. `split_sentences`
3. `Synthesizer.synthesize` once per chunk, in an executor

## Public API (`from audiohub.tts import ...`)

| Name | What it does |
|---|---|
| `clean_for_speech(text) -> str` | Strips markdown: bold, italics, strikethrough, headings, bullet and number markers, blockquotes, inline backticks. Fenced code becomes "code omitted". URLs become "a link". Markdown links keep their text. Headings and list items are spoken as separate sentences. |
| `split_sentences(text, max_chars=250) -> list[str]` | Splits after `.`, `!` and `?`. It doesn't split after abbreviations ("Mr.", "e.g.", "U.S.") or inside numbers ("3.5"). Over-long sentences break at a clause, then at a word, then mid-word as a last resort. |
| `Synthesizer(tts_settings, models_dir)` | Its `.synthesize(text, voice=None) -> (samples, sample_rate)` is synchronous and thread-safe. The model loads on the first call, and is downloaded first if missing. |
| `ensure_models(models_dir) -> (model_path, voices_path)` | Downloads `kokoro-v1.0.onnx` (fp32, ~310 MB) and `voices-v1.0.bin` (~27 MB) if missing, with a progress line on stderr. |
| `BRITISH_MALE_VOICES` | `("bm_george", "bm_fable", "bm_lewis", "bm_daniel")` |
| `ModelDownloadError` | Raised when a model file can't be downloaded completely. |

## Model files

The files come from the official kokoro-onnx GitHub release `model-files-v1.1`, which the installed kokoro-onnx 0.6.1 README links to. They are saved to `tools/audiohub/models/` (`config.MODELS_DIR`, gitignored). Each download streams to `<name>.part` and is renamed into place only once complete, so an interrupted download is simply retried next time.

The same release also has an int8 build (~110 MB). We use the fp32 build because the brief names it and it gives the best quality. It is already much faster than real time on this PC's CPU.

## Dependencies

- `kokoro-onnx` (which brings in onnxruntime, phonemizer and a bundled espeak-ng)
- `numpy`
- `audiohub.config` (`TtsSettings`)
- the standard library (`urllib` for downloads)

It never imports `audiohub.audio`; playback is the caller's job.

## Files

- `cleaning.py`: inline markdown, code blocks and URLs
- `blocks.py`: line structure (paragraphs, headings, list items)
- `sentences.py`: sentence chunking
- `synthesizer.py`: the lazy Kokoro wrapper
- `models.py` and `download.py`: model files
- `voices.py`: voice names
