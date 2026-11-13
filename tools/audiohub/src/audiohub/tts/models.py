"""Locate the Kokoro v1.0 model files, downloading any that are missing.

The model (`kokoro-v1.0.onnx`, full-precision fp32) and the voice styles
(`voices-v1.0.bin`) come from the official kokoro-onnx GitHub release and
live in the gitignored `tools/audiohub/models/` folder (`config.MODELS_DIR`).
"""

from pathlib import Path

from audiohub.tts.download import download_file

# model-files-v1.1 is the release the installed kokoro-onnx 0.6.1 README
# links to. It re-publishes the v1.0 model, re-exported for this library.
RELEASE_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1"
MODEL_FILENAME = "kokoro-v1.0.onnx"
VOICES_FILENAME = "voices-v1.0.bin"


def ensure_models(models_dir: Path) -> tuple[Path, Path]:
    """Make sure the Kokoro model and voices files are in `models_dir`.

    Files that already exist are left alone. Missing ones are downloaded
    with a progress line on stderr. `models_dir` is created if needed.

    Args:
        models_dir: Folder that holds (or will hold) the model files.

    Returns:
        `(model_path, voices_path)`.

    Raises:
        ModelDownloadError: If a missing file can't be downloaded.
        OSError: If `models_dir` can't be created.
    """
    models_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for filename in (MODEL_FILENAME, VOICES_FILENAME):
        path = models_dir / filename
        if not path.is_file():
            download_file(f"{RELEASE_URL}/{filename}", path)
        paths.append(path)
    model_path, voices_path = paths
    return model_path, voices_path
