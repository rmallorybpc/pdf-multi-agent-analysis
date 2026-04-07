from pathlib import Path

from pdf_multi_agent_analysis import assets_context
from pdf_multi_agent_analysis.assets_context import (
    PDF_MAX_SINGLE_CHAR_TOKEN_RATIO_DEFAULT,
    PDF_MIN_TEXT_CHARS_DEFAULT,
    _asset_text_quality_failure,
    _normalize_extracted_text,
    build_assets_context_with_warnings,
    write_assets_cache,
)
from pdf_multi_agent_analysis.config import PipelineConfig
from pdf_multi_agent_analysis.pipeline import run_markdown_analysis


def test_ocr_cleanup_collapses_character_spacing_and_layout_breaks() -> None:
    raw = "t h e  agreement\nshall be applied\ne f f e c t i v e l y"
    cleaned = _normalize_extracted_text(raw)

    assert "the agreement shall be applied effectively" in cleaned
    assert "e f f e c t i v e l y" not in cleaned


def test_ocr_cleanup_joins_single_word_line_artifacts() -> None:
    raw = "Confidential\nInformation shall\nremain protected"
    cleaned = _normalize_extracted_text(raw)

    assert "Confidential Information shall remain protected" in cleaned


def test_quality_failure_detects_short_or_noisy_text() -> None:
    short_reason = _asset_text_quality_failure("brief", min_chars=100, max_single_char_token_ratio=0.4)
    noisy_reason = _asset_text_quality_failure(
        "a b c d e f g h valid", min_chars=5, max_single_char_token_ratio=0.4
    )

    assert short_reason == "text too short (5 chars < 100)"
    assert noisy_reason is not None
    assert "single-character token ratio too high" in noisy_reason


def test_failed_pdf_extraction_returns_warning_and_no_context(tmp_path: Path, monkeypatch) -> None:
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    (assets_dir / "reference.pdf").write_bytes(b"%PDF-1.4\n")

    def fake_read_pdf_file(*_args, **_kwargs):
        return "", "no extractable text found with native extraction or OCR fallback"

    monkeypatch.setattr(assets_context, "_read_pdf_file", fake_read_pdf_file)

    context, warnings = build_assets_context_with_warnings(assets_dir)

    assert context == ""
    assert len(warnings) == 1
    assert "Asset extraction failed for reference.pdf" in warnings[0]


def test_run_markdown_analysis_writes_asset_warning_section(tmp_path: Path, monkeypatch) -> None:
    md_file = tmp_path / "input.md"
    md_file.write_text("# NDA\n\nBody.", encoding="utf-8")

    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    (assets_dir / "reference.pdf").write_bytes(b"%PDF-1.4\n")

    def fake_read_pdf_file(*_args, **_kwargs):
        return "", "native extraction failed quality checks: text too short (12 chars < 100)"

    monkeypatch.setattr(assets_context, "_read_pdf_file", fake_read_pdf_file)

    result = run_markdown_analysis(md_file, PipelineConfig(output_dir=tmp_path / "out"), assets_dir=assets_dir)
    report = result["report_path"].read_text(encoding="utf-8")

    assert result["assets_context_included"] is False
    assert len(result["asset_warnings"]) == 1
    assert "reference.pdf" in result["asset_warnings"][0]
    assert "## Asset Extraction Warnings" in report
    assert "WARNING: Asset extraction failed for reference.pdf" in report


def test_shared_cache_writer_uses_pdf_quality_failure_warning(tmp_path: Path, monkeypatch) -> None:
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    (assets_dir / "reference.pdf").write_bytes(b"%PDF-1.4\n")

    def fake_read_pdf_file(*_args, **_kwargs):
        return "", "no extractable text found with native extraction or OCR fallback"

    monkeypatch.setattr(assets_context, "_read_pdf_file", fake_read_pdf_file)

    cache_dir = tmp_path / "cache"
    entries, warnings = write_assets_cache(
        assets_dir,
        cache_dir,
        pdf_min_text_chars=PDF_MIN_TEXT_CHARS_DEFAULT,
        pdf_max_single_char_token_ratio=PDF_MAX_SINGLE_CHAR_TOKEN_RATIO_DEFAULT,
    )

    assert entries == [("assets/reference.pdf", "reference.pdf.txt")]
    assert len(warnings) == 1
    assert "Asset extraction failed for reference.pdf" in warnings[0]

    cached_text = (cache_dir / "reference.pdf.txt").read_text(encoding="utf-8")
    assert "[ASSET EXTRACTION FAILED] Asset extraction failed for reference.pdf" in cached_text
