from pathlib import Path


def pdf_to_markdown(pdf_path: Path) -> str:
    """Convert a PDF into a simple page-structured markdown string.

    Each page is emitted as:
    ## Page N
    <extracted text>
    """
    try:
        from pypdf import PdfReader
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "Missing dependency 'pypdf'. Install requirements before running conversion."
        ) from exc

    reader = PdfReader(str(pdf_path))
    parts: list[str] = [f"# Converted: {pdf_path.name}"]

    for i, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if not text:
            text = "[No text extracted from this page]"
        parts.append(f"\n## Page {i}\n\n{text}")

    return "\n".join(parts).strip() + "\n"
