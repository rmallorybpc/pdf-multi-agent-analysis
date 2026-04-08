from __future__ import annotations

from html import unescape
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import zipfile

TEXT_EXTENSIONS = {".md", ".txt", ".json", ".yaml", ".yml"}

ASSET_STATUS_LOADED = "loaded"
ASSET_STATUS_PARTIAL = "partial"
ASSET_STATUS_FAILED = "failed"

PDF_MIN_TEXT_CHARS_DEFAULT = 100
PDF_MAX_SINGLE_CHAR_TOKEN_RATIO_DEFAULT = 0.40

COMMON_WORD_SPLIT_TERMS = {
    "a",
    "about",
    "all",
    "an",
    "and",
    "any",
    "are",
    "as",
    "at",
    "be",
    "before",
    "between",
    "business",
    "by",
    "can",
    "company",
    "confidential",
    "content",
    "contract",
    "controls",
    "data",
    "description",
    "designed",
    "document",
    "effective",
    "effectively",
    "examination",
    "for",
    "from",
    "has",
    "have",
    "in",
    "independent",
    "information",
    "internal",
    "is",
    "it",
    "its",
    "legal",
    "may",
    "must",
    "not",
    "of",
    "on",
    "or",
    "operated",
    "our",
    "out",
    "presents",
    "privacy",
    "process",
    "report",
    "requirements",
    "review",
    "risk",
    "security",
    "service",
    "shall",
    "should",
    "soc",
    "standards",
    "suitable",
    "that",
    "the",
    "their",
    "there",
    "these",
    "this",
    "to",
    "use",
    "was",
    "we",
    "with",
    "xyz",
}


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


def _split_run_together_token(token: str) -> str:
    lowered = token.lower()
    if len(lowered) <= 10 or not lowered.isalpha():
        return token

    n = len(lowered)
    dp: list[tuple[int, int, int, list[str]] | None] = [None] * (n + 1)
    dp[0] = (0, 0, 0, [])

    for i in range(n):
        state = dp[i]
        if state is None:
            continue
        score, known_chars, known_parts, parts = state
        for j in range(i + 2, min(n, i + 18) + 1):
            piece = lowered[i:j]
            if piece in COMMON_WORD_SPLIT_TERMS:
                piece_score = max(2, len(piece))
                next_state = (
                    score + piece_score,
                    known_chars + len(piece),
                    known_parts + 1,
                    parts + [piece],
                )
            elif len(piece) >= 8:
                next_state = (score - 1, known_chars, known_parts, parts + [piece])
            else:
                continue

            current = dp[j]
            if current is None or next_state[:3] > current[:3]:
                dp[j] = next_state

    best = dp[n]
    if best is None:
        return token

    _, known_chars, known_parts, parts = best
    if len(parts) < 2:
        return token
    if known_parts < 2:
        return token

    known_ratio = known_chars / n
    if known_ratio < 0.55:
        return token

    rebuilt = " ".join(parts)
    if token[:1].isupper():
        rebuilt = rebuilt[:1].upper() + rebuilt[1:]
    return rebuilt


def _reconstruct_run_together_words(text: str) -> str:
    # Repair run-together OCR artifacts across the full text body.
    return re.sub(r"\b[A-Za-z]{11,}\b", lambda m: _split_run_together_token(m.group(0)), text)


def _read_text_file(path: Path, max_chars: int) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")[:max_chars].strip()


def _normalize_extracted_text(text: str) -> str:
    text = text.replace("\x00", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _collapse_character_spaced_words(text)
    text = _reconstruct_run_together_words(text)

    # Normalize punctuation spacing from OCR artifacts like "Company ' s".
    text = re.sub(r"([A-Za-z])\s+'\s+([A-Za-z])", r"\1'\2", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"([,.;:!?])([A-Za-z(\"'])", r"\1 \2", text)
    text = re.sub(r"\(\s+", "(", text)
    text = re.sub(r"\s+\)", ")", text)

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


def _business_status_line(path: Path, status: str) -> str:
    name = path.as_posix()
    if status == ASSET_STATUS_FAILED:
        return (
            f"Note: {name} could not be read automatically. Findings in this analysis do not reflect its contents. "
            "Manual review of this document is recommended before finalizing any redline strategy."
        )
    if status == ASSET_STATUS_PARTIAL:
        return (
            f"Note: {name} was partially parsed. Some content may be incomplete. "
            "Treat references to this document in the analysis with caution."
        )
    return f"{name} - loaded successfully."


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
) -> tuple[str, str | None, str]:
    native = _extract_pdf_text_native(path, max_chars)
    native_quality_failure = _asset_text_quality_failure(
        native,
        min_chars=min_text_chars,
        max_single_char_token_ratio=max_single_char_token_ratio,
    )
    if native and native_quality_failure is None:
        return native, None, ASSET_STATUS_LOADED

    if ocr_fallback:
        ocr = _extract_pdf_text_ocr(path, max_chars, ocr_max_pages)
        ocr_quality_failure = _asset_text_quality_failure(
            ocr,
            min_chars=min_text_chars,
            max_single_char_token_ratio=max_single_char_token_ratio,
        )
        if ocr and ocr_quality_failure is None:
            return ocr, None, ASSET_STATUS_PARTIAL

        if not native and not ocr:
            return "", "no extractable text found with native extraction or OCR fallback", ASSET_STATUS_FAILED

        reasons: list[str] = []
        if native_quality_failure is not None:
            reasons.append(f"native extraction failed quality checks: {native_quality_failure}")
        if ocr_quality_failure is not None:
            reasons.append(f"OCR fallback failed quality checks: {ocr_quality_failure}")
        reason_text = "; ".join(reasons) if reasons else "extraction failed quality checks"
        return "", reason_text, ASSET_STATUS_FAILED

    if not native:
        return "", "no extractable text found with native extraction", ASSET_STATUS_FAILED

    return "", f"native extraction failed quality checks: {native_quality_failure}", ASSET_STATUS_FAILED


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


def build_assets_context_with_status(
    assets_dir: Path,
    max_chars_per_file: int = 4000,
    pdf_ocr_fallback: bool = False,
    pdf_ocr_max_pages: int = 6,
    pdf_min_text_chars: int = PDF_MIN_TEXT_CHARS_DEFAULT,
    pdf_max_single_char_token_ratio: float = PDF_MAX_SINGLE_CHAR_TOKEN_RATIO_DEFAULT,
) -> tuple[str, list[dict[str, str]]]:
    """Build markdown context and business-facing status entries for reference assets."""
    if not assets_dir.exists() or not assets_dir.is_dir():
        return "", []

    sections: list[str] = ["# Assets Context", ""]
    statuses: list[dict[str, str]] = []

    for path in sorted(p for p in assets_dir.rglob("*") if p.is_file()):
        rel = path.relative_to(assets_dir)
        suffix = path.suffix.lower()

        status = ASSET_STATUS_LOADED
        technical_reason: str | None = None

        if suffix in TEXT_EXTENSIONS:
            content = _normalize_extracted_text(_read_text_file(path, max_chars_per_file))
        elif suffix == ".pdf":
            content, extraction_warning, status = _read_pdf_file(
                path,
                max_chars_per_file,
                ocr_fallback=pdf_ocr_fallback,
                ocr_max_pages=pdf_ocr_max_pages,
                min_text_chars=pdf_min_text_chars,
                max_single_char_token_ratio=pdf_max_single_char_token_ratio,
            )
            if extraction_warning is not None:
                technical_reason = extraction_warning
        elif suffix == ".docx":
            content = _normalize_extracted_text(_read_docx_file(path, max_chars_per_file))
            if content.startswith("[docx reference present;"):
                status = ASSET_STATUS_PARTIAL
        else:
            content = ""
            status = ASSET_STATUS_PARTIAL

        business_note = _business_status_line(rel, status)
        status_entry: dict[str, str] = {
            "name": rel.as_posix(),
            "status": status,
            "message": business_note,
        }
        if technical_reason:
            status_entry["warning"] = _pdf_extraction_failure_message(rel, technical_reason)
        statuses.append(status_entry)

        if status == ASSET_STATUS_FAILED or not content:
            continue

        sections.append(f"## {rel.as_posix()}")
        sections.append(content)
        sections.append("")

    if len(sections) <= 2:
        return "", statuses

    return "\n".join(sections).strip() + "\n", statuses


def build_assets_context_with_warnings(
    assets_dir: Path,
    max_chars_per_file: int = 4000,
    pdf_ocr_fallback: bool = False,
    pdf_ocr_max_pages: int = 6,
    pdf_min_text_chars: int = PDF_MIN_TEXT_CHARS_DEFAULT,
    pdf_max_single_char_token_ratio: float = PDF_MAX_SINGLE_CHAR_TOKEN_RATIO_DEFAULT,
) -> tuple[str, list[str]]:
    """Compatibility wrapper returning legacy warning strings for failed assets only."""
    context, statuses = build_assets_context_with_status(
        assets_dir,
        max_chars_per_file=max_chars_per_file,
        pdf_ocr_fallback=pdf_ocr_fallback,
        pdf_ocr_max_pages=pdf_ocr_max_pages,
        pdf_min_text_chars=pdf_min_text_chars,
        pdf_max_single_char_token_ratio=pdf_max_single_char_token_ratio,
    )
    warnings = [entry["warning"] for entry in statuses if "warning" in entry]
    return context, warnings


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
            content = _normalize_extracted_text(_read_text_file(path, max_chars_per_file))
        elif suffix == ".pdf":
            content, extraction_warning, _status = _read_pdf_file(
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
            content = _normalize_extracted_text(_read_docx_file(path, max_chars_per_file))
        else:
            content = ""

        lines = [f"# source: assets/{rel.as_posix()}", ""]
        if content:
            lines.append(content)

        if not content and extraction_warning_message is not None:
            lines.append(f"[ASSET EXTRACTION FAILED] {extraction_warning_message}")

        out_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
        cache_entries.append((f"assets/{rel.as_posix()}", out_path.name))

    return cache_entries, warnings
