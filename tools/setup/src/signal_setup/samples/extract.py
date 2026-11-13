"""Text out of the files a user points at: .txt/.md/code as-is, .docx by its XML, .pdf via pypdf.

.docx needs nothing extra (it's a zip of XML). .pdf runs pypdf through `uv run --with`
(pinned, the version the browser tool uses) so setup itself stays stdlib only.
"""

import re
import subprocess
import zipfile
from pathlib import Path

from signal_setup.samples.store import save_sample

TEXT_SUFFIXES = {".txt", ".md", ".py", ".java", ".c", ".cpp", ".js", ".ts", ".sql", ".html"}
PYPDF = "pypdf==6.21.2"
PDF_SCRIPT = (
    "import sys, pypdf; "
    "print('\n'.join(p.extract_text() or '' for p in pypdf.PdfReader(sys.argv[1]).pages))"
)


def _docx_text(path: Path) -> str:
    """The paragraphs of a .docx, one per line."""
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("word/document.xml").decode("utf-8")
    paragraphs = re.split(r"</w:p>", xml)
    return "\n".join(re.sub(r"<[^>]+>", "", p) for p in paragraphs).strip()


def _pdf_text(path: Path) -> str:
    """A PDF's text through pypdf. Raises ValueError if extraction fails."""
    result = subprocess.run(
        ["uv", "run", "--no-project", "--with", PYPDF, "python", "-I", "-c", PDF_SCRIPT, str(path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ValueError(f"couldn't read {path.name}; paste its text instead")
    return result.stdout


def file_text(path: Path) -> str:
    """The text of one file. Raises ValueError for a type it can't read."""
    suffix = path.suffix.lower()
    if suffix in TEXT_SUFFIXES:
        return path.read_text("utf-8", errors="replace")
    if suffix == ".docx":
        return _docx_text(path)
    if suffix == ".pdf":
        return _pdf_text(path)
    raise ValueError(f"{path.name}: use .docx, .pdf, .txt, .md or a code file")


def import_paths(root: Path, paths: list[Path], kind: str) -> list[str]:
    """Import each file (folders are walked) as a sample. Returns one line per file."""
    files = [f for p in paths for f in (sorted(p.rglob("*")) if p.is_dir() else [p]) if f.is_file()]
    report = []
    for file in files:
        try:
            saved = save_sample(root, kind, file.stem, file_text(file))
            report.append(f"added {saved.name}")
        except (OSError, ValueError, zipfile.BadZipFile, KeyError) as error:
            report.append(f"skipped {file.name}: {error}")
    return report
