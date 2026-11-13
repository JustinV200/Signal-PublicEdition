"""Names of the Kokoro voices audiohub offers.

Claude speaks in a British male voice. The default comes from
`TtsSettings.voice`; these are the alternatives the `voices` CLI command
demos. Each name is checked against the real `voices-v1.0.bin` by
`tests/tts/test_voices.py` whenever the model files are present.
"""

# The British English ("b") male ("m") voices in voices-v1.0.bin.
BRITISH_MALE_VOICES: tuple[str, ...] = ("bm_george", "bm_fable", "bm_lewis", "bm_daniel")
