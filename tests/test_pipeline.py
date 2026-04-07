from pathlib import Path

from pdf_multi_agent_analysis.config import PipelineConfig
from pdf_multi_agent_analysis.pipeline import run_markdown_analysis


def test_run_markdown_analysis_with_assets(tmp_path: Path) -> None:
    md_file = tmp_path / "input.md"
    md_file.write_text("# NDA\n\nConfidential Information must be protected.", encoding="utf-8")

    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    (assets_dir / "notes.txt").write_text(
        "Confidential information obligations and disclosure exceptions.",
        encoding="utf-8",
    )

    cfg = PipelineConfig(output_dir=tmp_path / "out", chunk_size_chars=120, overlap_chars=20)
    result = run_markdown_analysis(md_file, cfg, assets_dir=assets_dir)

    report_path = result["report_path"]
    issues_path = result["issues_path"]
    final_path = result["final_path"]
    assert report_path.exists()
    assert issues_path.exists()
    assert final_path.exists()
    report = report_path.read_text(encoding="utf-8")
    issues = issues_path.read_text(encoding="utf-8")
    final = final_path.read_text(encoding="utf-8")
    assert "# Analysis Report" in report
    assert "# Contract Issues Summary" in issues
    assert "last_run:" in final
    assert "# Final Synthesized Output:" in final
    assert "## Reference Assets" in report
    assert "notes.txt" in report
    assert result["assets_context_included"] is True


def test_run_markdown_analysis_without_assets(tmp_path: Path) -> None:
    md_file = tmp_path / "input.md"
    md_file.write_text("# Section\n\nSimple body text.", encoding="utf-8")

    cfg = PipelineConfig(output_dir=tmp_path / "out", chunk_size_chars=80, overlap_chars=10)
    result = run_markdown_analysis(md_file, cfg, assets_dir=tmp_path / "missing-assets")

    report_path = result["report_path"]
    issues_path = result["issues_path"]
    final_path = result["final_path"]
    report = report_path.read_text(encoding="utf-8")
    issues = issues_path.read_text(encoding="utf-8")
    final = final_path.read_text(encoding="utf-8")
    assert "## Reference Assets" not in report
    assert "# Contract Issues Summary" in issues
    assert "last_run:" in final
    assert "# Final Synthesized Output:" in final
    assert result["assets_context_included"] is False
