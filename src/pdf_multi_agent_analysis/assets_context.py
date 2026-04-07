from __future__ import annotations

from html import unescape
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import zipfile

TEXT_EXTENSIONS = {".md", ".txt", ".json", ".yaml", ".yml"}

PDF_MIN_TEXT_CHARS_DEFAULT = 100
PDF_MAX_SINGLE_CHAR_TOKEN_RATIO_DEFAULT = 0.40


def _collapse_character_spaced_words(text: str) -> str:
    # Collapse OCR outputs like "t h e" and "s u i t a b l y" into words.
    pattern = re.compile(r"(?<!\w)(?:[A-Za-z]\s+){2,}[A-Za-z](?!\w)")
    previous = None
    current = text
    while current != previous:
        previous = current
        current = pattern.sub(lambda m: m.group(0).replace(" ", ""), current)
    return current


def _should_join_lines(previous_line: str, next_line: str) -> bool:
    prev = previous_line.strip()
    nxt = next_line.strip()
    if not prev or not nxt:
        return False

    # Keep hard separators and list-like formatting intact.
    if prev.endswith(":"):
        return False
    if nxt.startswith(("-", "*", ">")) or re.match(r"^\d+[.)]\s", nxt):
        return False

    prev_tokens = re.findall(r"\b[\w']+\b", prev)
    prev_token_count = len(prev_tokens)
    prev_last_token = prev_tokens[-1] if prev_tokens else ""
    next_starts_sentence = bool(re.match(r"^[a-z0-9(\"']", nxt))
    next_is_word_start = bool(re.match(r"^[A-Za-z0-9]", nxt))

    # Join short trailing fragments (single-word or short-token line endings)
    # and hard-wrapped lines that continue a sentence.
    if prev_token_count <= 2 and len(prev_last_token) <= 12 and next_is_word_start:
        return True

    if prev.endswith((".", "!", "?")):
        return False

    return next_starts_sentence


def _normalize_column_line_breaks(text: str) -> str:
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    normalized: list[str] = []

    for paragraph in paragraphs:
        lines = [line.strip() for line in paragraph.split("\n") if line.strip()]
        if not lines:
            continue

        merged: list[str] = [lines[0]]
        for line in lines[1:]:
            if _should_join_lines(merged[-1], line):
                merged[-1] = f"{merged[-1]} {line}"
            else:
                merged.append(line)

        normalized.append("\n".join(merged))

    return "\n\n".join(normalized)


def _read_text_file(path: Path, max_chars: int) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")[:max_chars].strip()


def _normalize_extracted_text(text: str) -> str:
    text = text.replace("\x00", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _collapse_character_spaced_words(text)

    # Join soft line-wrap hyphenation before broader line-break normalization.
    text = re.sub(r"(?<=\w)-\n(?=\w)", "", text)
    text = _normalize_column_line_breaks(text)

    # After merging lines, collapse residual character spacing once more.
    text = _collapse_character_spaced_words(text)

    # Remove excessive token spacing while preserving intended newlines.
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"[ ]+\n", "\n", text)
    text = re.sub(r"\n[ ]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _single_char_token_ratio(text: str) -> float:
    tokens = re.findall(r"\b[\w']+\b", text)
    if not tokens:
        return 1.0
    single_char_count = sum(1 for token in tokens if len(token) == 1)
    return single_char_count / len(tokens)


def _asset_text_quality_failure(
    text: str,
    min_chars: int,
    max_single_char_token_ratio: float,
) -> str | None:
    if not text.strip():
        return "no extractable text"
    if len(text) < min_chars:
        return f"text too short ({len(text)} chars < {min_chars})"
    ratio = _single_char_token_ratio(text)
    if ratio > max_single_char_token_ratio:
        return (
            "single-character token ratio too high "
            f"({ratio:.0%} > {max_single_char_token_ratio:.0%})"
        )
    return None


def _pdf_extraction_failure_message(path: Path, reason: str) -> str:
    return f"Asset extraction failed for {path.as_posix()}: {reason}"


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


def _read_pdf_file(
    path: Path,
    max_chars: int,
    ocr_fallback: bool,
    ocr_max_pages: int,
    min_text_chars: int,
    max_single_char_token_ratio: float,
) -> tuple[str, str | None]:
    native = _extract_pdf_text_native(path, max_chars)
    native_quality_failure = _asset_text_quality_failure(
        native,
        min_chars=min_text_chars,
        max_single_char_token_ratio=max_single_char_token_ratio,
    )
    if native and native_quality_failure is None:
        return native, None

    if ocr_fallback:
        ocr = _extract_pdf_text_ocr(path, max_chars, ocr_max_pages)
        ocr_quality_failure = _asset_text_quality_failure(
            ocr,
            min_chars=min_text_chars,
            max_single_char_token_ratio=max_single_char_token_ratio,
        )
        if ocr and ocr_quality_failure is None:
            return ocr, None

        if not native and not ocr:
            return "", "no extractable text found with native extraction or OCR fallback"

        reasons: list[str] = []
        if native_quality_failure is not None:
            reasons.append(f"native extraction failed quality checks: {native_quality_failure}")
        if ocr_quality_failure is not None:
            reasons.append(f"OCR fallback failed quality checks: {ocr_quality_failure}")
        reason_text = "; ".join(reasons) if reasons else "extraction failed quality checks"
        return "", reason_text

    if not native:
        return "", "no extractable text found with native extraction"

    return "", f"native extraction failed quality checks: {native_quality_failure}"


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
    pdf_min_text_chars: int = PDF_MIN_TEXT_CHARS_DEFAULT,
    pdf_max_single_char_token_ratio: float = PDF_MAX_SINGLE_CHAR_TOKEN_RATIO_DEFAULT,
) -> str:
    context, _warnings = build_assets_context_with_warnings(
        assets_dir,
        max_chars_per_file=max_chars_per_file,
        pdf_ocr_fallback=pdf_ocr_fallback,
        pdf_ocr_max_pages=pdf_ocr_max_pages,
        pdf_min_text_chars=pdf_min_text_chars,
        pdf_max_single_char_token_ratio=pdf_max_single_char_token_ratio,
    )
    return context


def build_assets_context_with_warnings(
    assets_dir: Path,
    max_chars_per_file: int = 4000,
    pdf_ocr_fallback: bool = False,
    pdf_ocr_max_pages: int = 6,
    pdf_min_text_chars: int = PDF_MIN_TEXT_CHARS_DEFAULT,
    pdf_max_single_char_token_ratio: float = PDF_MAX_SINGLE_CHAR_TOKEN_RATIO_DEFAULT,
) -> tuple[str, list[str]]:
    """Build a deterministic markdown context block from reference assets."""
    if not assets_dir.exists() or not assets_dir.is_dir():
        return "", []

    sections: list[str] = ["# Assets Context", ""]
    warnings: list[str] = []

    for path in sorted(p for p in assets_dir.rglob("*") if p.is_file()):
        rel = path.relative_to(assets_dir)
        suffix = path.suffix.lower()

        if suffix in TEXT_EXTENSIONS:
            content = _read_text_file(path, max_chars_per_file)
        elif suffix == ".pdf":
            content, extraction_warning = _read_pdf_file(
                path,
                max_chars_per_file,
                ocr_fallback=pdf_ocr_fallback,
                ocr_max_pages=pdf_ocr_max_pages,
                min_text_chars=pdf_min_text_chars,
                max_single_char_token_ratio=pdf_max_single_char_token_ratio,
            )
            if extraction_warning is not None:
                warnings.append(_pdf_extraction_failure_message(rel, extraction_warning))
        elif suffix == ".docx":
            content = _read_docx_file(path, max_chars_per_file)
        else:
            content = "[unsupported/binary reference file type]"

        if not content:
            continue

        sections.append(f"## {rel.as_posix()}")
        sections.append(content)
        sections.append("")

    if len(sections) <= 2:
        return "", warnings

    return "\n".join(sections).strip() + "\n", warnings


def write_assets_cache(
    assets_dir: Path,
    cache_dir: Path,
    max_chars_per_file: int = 4000,
    pdf_ocr_fallback: bool = False,
    pdf_ocr_max_pages: int = 6,
    pdf_min_text_chars: int = PDF_MIN_TEXT_CHARS_DEFAULT,
    pdf_max_single_char_token_ratio: float = PDF_MAX_SINGLE_CHAR_TOKEN_RATIO_DEFAULT,
) -> tuple[list[tuple[str, str]], list[str]]:
    """Write deterministic text cache artifacts and return (source, cache file) entries plus warnings."""
    if not assets_dir.exists() or not assets_dir.is_dir():
        return [], []

    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_entries: list[tuple[str, str]] = []
    warnings: list[str] = []

    for path in sorted(p for p in assets_dir.rglob("*") if p.is_file()):
        rel = path.relative_to(assets_dir)
        suffix = path.suffix.lower()
        safe_name = rel.as_posix().replace("/", "__")
        out_path = cache_dir / f"{safe_name}.txt"
        extraction_warning_message: str | None = None

        if suffix in TEXT_EXTENSIONS:
            content = _read_text_file(path, max_chars_per_file)
        elif suffix == ".pdf":
            content, extraction_warning = _read_pdf_file(
                path,
                max_chars_per_file,
                ocr_fallback=pdf_ocr_fallback,
                ocr_max_pages=pdf_ocr_max_pages,
                min_text_chars=pdf_min_text_chars,
                max_single_char_token_ratio=pdf_max_single_char_token_ratio,
            )
            if extraction_warning is not None:
                extraction_warning_message = _pdf_extraction_failure_message(rel, extraction_warning)
                warnings.append(extraction_warning_message)
        elif suffix == ".docx":
            content = _read_docx_file(path, max_chars_per_file)
        else:
            content = "[unsupported/binary reference file type]"

        lines = [f"# source: assets/{rel.as_posix()}", ""]
        if content:
            lines.append(content)

        if not content and extraction_warning_message is not None:
            lines.append(f"[ASSET EXTRACTION FAILED] {extraction_warning_message}")

        out_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
        cache_entries.append((f"assets/{rel.as_posix()}", out_path.name))

    return cache_entries, warnings
