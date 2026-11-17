"""Where fetched content lands in the run folder, and the manifest source records.

Extracts go to `extracts/<nnn>-<label>.md`, raw downloads to `data/raw/<nnn>-<name>`.
The number is one more than the highest number already there, and the file is
created exclusively ("x"), so two writers never overwrite each other and names
read in fetch order.
"""

import re
from pathlib import Path

from analysis_chamber.runs import utc_now_iso

EXTRACTS_DIR = "extracts"
RAW_DIR = Path("data") / "raw"
_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")
_NUMBER_PREFIX = re.compile(r"(\d+)-")
MAX_LABEL_CHARS = 60
# Exclusive-create retries when another writer takes the same number first.
MAX_CREATE_ATTEMPTS = 20


def safe_label(text: str) -> str:
    """`text` as a short file-name-safe label ("source" if nothing is left)."""
    return _UNSAFE.sub("-", text).strip("-.")[:MAX_LABEL_CHARS] or "source"


def _next_number(folder: Path) -> int:
    """One more than the highest `<nnn>-` prefix in `folder` (1 if there is none)."""
    numbers = [int(m.group(1)) for p in folder.iterdir() if (m := _NUMBER_PREFIX.match(p.name))]
    return max(numbers, default=0) + 1


def _write_numbered(folder: Path, name: str, data: bytes) -> Path:
    """Create `folder/<nnn>-<name>` exclusively with `data`; makes the folder.

    Raises:
        OSError: The file can't be written, or every attempt found its number taken.
    """
    folder.mkdir(parents=True, exist_ok=True)
    for _ in range(MAX_CREATE_ATTEMPTS):
        path = folder / f"{_next_number(folder):03d}-{name}"
        try:
            with path.open("xb") as handle:
                handle.write(data)
        except FileExistsError:
            continue  # another writer took this number; look again
        return path
    raise OSError(f"no free file number in {folder}")


def save_extract(run_dir: Path, label: str, source: str, extract: str) -> Path:
    """Write an extract with its source and fetch date. Returns its path. Raises OSError."""
    text = f"# Extract\n\nSource: {source}\nFetched: {utc_now_iso()}\n\n{extract}\n"
    return _write_numbered(run_dir / EXTRACTS_DIR, f"{safe_label(label)}.md", text.encode())


def save_raw(run_dir: Path, name: str, body: bytes, subfolder: str = "") -> Path:
    """Write raw bytes under data/raw (or data/raw/<subfolder>). Returns the path.

    Raises:
        OSError: The file can't be written.
    """
    return _write_numbered(run_dir / RAW_DIR / subfolder, safe_label(name), body)


def source_record(name: str, url: str, status: str, note: str) -> dict:
    """A manifest.sources entry: {name, url, status, note, fetched_at}."""
    return {"name": name, "url": url, "status": status, "note": note, "fetched_at": utc_now_iso()}
