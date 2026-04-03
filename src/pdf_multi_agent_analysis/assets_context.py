from __future__ import annotations

from html import unescape
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import zipfile

TEXT_EXTENSIONS = {".md", ".txt", ".json", ".yaml", ".yml"}


def _read_text_file(path: Path, max_chars: int) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")[:max_chars].strip()


def _normalize_extracted_text(text: str) -> str:
    text = text.replace("\x00", "")
    text = re.sub(r"(?<!\w)(?:[A-Za-z]\s){3,}[A-Za-z](?!\w)", lambda m: m.group(0).replace(" ", ""), text)
    text = re.sub(r"[^\S\n]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_pdf_text_native(path: Path, max_chars: int) -> str:
    try:
        from pypdf import PdfReader
    except Exception:
        return ""

    reader = PdfReader(str(path))
    parts: list[str] = []
    remaining = max_chars

    for page in reader.pages:
        if remaining <= 0:
            break
        text = (page.extract_text() or "").strip()
        if not text:
            continue
        cleaned = _normalize_extracted_text(text)
        if not cleaned:
            continue
        snippet = cleaned[:remaining]
        parts.append(snippet)
        remaining -= len(snippet)

    return "\n\n".join(parts).strip()


def _extract_pdf_text_ocr(path: Path, max_chars: int, max_pages: int) -> str:
    if max_pages <= 0:
        return ""
    if shutil.which("pdftoppm") is None or shutil.which("tesseract") is None:
        return ""

    collected: list[str] = []
    remaining = max_chars

    with tempfile.TemporaryDirectory(prefix="asset-ocr-") as tmp:
        prefix = Path(tmp) / "page"
        render = [
            "pdftoppm",
            "-f",
            "1",
            "-l",
            str(max_pages),
            "-png",
            str(path),
            str(prefix),
        ]
        try:
            subprocess.run(render, check=True, capture_output=True, text=True)
        except Exception:
            return ""

        images = sorted(Path(tmp).glob("page-*.png"))
        for image in images:
            if remaining <= 0:
                break
            try:
                ocr = subprocess.run(
                    ["tesseract", str(image), "stdout"],
                    check=True,
                    capture_output=True,
                    text=True,
                )
            except Exception:
                continue

            text = ocr.stdout.strip()
            if not text:
                continue
            cleaned = _normalize_extracted_text(text)
            if not cleaned:
                continue
            snippet = cleaned[:remaining]
            collected.append(snippet)
            remaining -= len(snippet)

    return "\n\n".join(collected).strip()


def _read_pdf_file(path: Path, max_chars: int, ocr_fallback: bool, ocr_max_pages: int) -> str:
    native = _extract_pdf_text_native(path, max_chars)
    if native:
        return native

    if ocr_fallback:
        ocr = _extract_pdf_text_ocr(path, max_chars, ocr_max_pages)
        if ocr:
            return ocr
        return "[pdf reference present; no extractable text found with native extraction or OCR fallback]"

    return "[pdf reference present; no extractable text found]"


def _read_docx_file(path: Path, max_chars: int) -> str:
    try:
        with zipfile.ZipFile(path) as zf:
            raw_xml = zf.read("word/document.xml").decode("utf-8", errors="ignore")
    except Exception:
        return "[docx reference present; unable to extract text]"

    no_tags = re.sub(r"<[^>]+>", " ", raw_xml)
    collapsed = re.sub(r"\s+", " ", unescape(no_tags)).strip()
    if not collapsed:
        return "[docx reference present; no extractable text found]"
    return collapsed[:max_chars]


def build_assets_context(
    assets_dir: Path,
    max_chars_per_file: int = 4000,
    pdf_ocr_fallback: bool = False,
    pdf_ocr_max_pages: int = 6,
) -> str:
    """Build a deterministic markdown context block from reference assets."""
    if not assets_dir.exists() or not assets_dir.is_dir():
        return ""

    sections: list[str] = ["# Assets Context", ""]

    for path in sorted(p for p in assets_dir.rglob("*") if p.is_file()):
        rel = path.relative_to(assets_dir)
        suffix = path.suffix.lower()

        if suffix in TEXT_EXTENSIONS:
            content = _read_text_file(path, max_chars_per_file)
        elif suffix == ".pdf":
            content = _read_pdf_file(
                path,
                max_chars_per_file,
                ocr_fallback=pdf_ocr_fallback,
                ocr_max_pages=pdf_ocr_max_pages,
            )
        elif suffix == ".docx":
            content = _read_docx_file(path, max_chars_per_file)
        else:
            content = "[unsupported/binary reference file type]"

        if not content:
            content = "[no content extracted]"

        sections.append(f"## {rel.as_posix()}")
        sections.append(content)
        sections.append("")

    if len(sections) <= 2:
        return ""

    return "\n".join(sections).strip() + "\n"
