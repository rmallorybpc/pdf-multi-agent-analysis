from pathlib import Path

from pdf_multi_agent_analysis.config import PipelineConfig
from pdf_multi_agent_analysis.pipeline import _build_sectioned_analysis_report, run_markdown_analysis


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
    scorecard_path = result["scorecard_path"]
    executive_summary_path = result["executive_summary_path"]
    final_path = result["final_path"]
    diagnostics_path = result["chunk_diagnostics_path"]
    assert report_path.exists()
    assert issues_path.exists()
    assert scorecard_path.exists()
    assert executive_summary_path.exists()
    assert final_path.exists()
    assert diagnostics_path.exists()
    report = report_path.read_text(encoding="utf-8")
    issues = issues_path.read_text(encoding="utf-8")
    scorecard = scorecard_path.read_text(encoding="utf-8")
    executive_summary = executive_summary_path.read_text(encoding="utf-8")
    final = final_path.read_text(encoding="utf-8")
    assert "# Analysis Report" in report
    assert "# Contract Issues Summary" in issues
    assert "Overall contract risk rating:" in scorecard
    assert "| Category | Risk Rating | Confidence | Rationale |" in scorecard
    assert "## Contract Metadata" in executive_summary
    assert "last_run:" in final
    assert "# Final Synthesized Output:" in final
    assert "## Document Overview" in report
    assert "## Reference Assets" in report
    assert "### notes.txt" in report
    assert "Confidential information obligations and disclosure exceptions." in report
    assert "## Reference Document Status" in report
    assert "notes.txt - loaded successfully." in report
    assert "Summary preview:" not in report
    assert "Reference anchors:" not in report
    diagnostics = diagnostics_path.read_text(encoding="utf-8")
    assert "# Chunk Diagnostics:" in diagnostics
    assert "### extractor" in diagnostics
    assert "Summary preview:" in diagnostics
    assert result["assets_context_included"] is True


def test_run_markdown_analysis_without_assets(tmp_path: Path) -> None:
    md_file = tmp_path / "input.md"
    md_file.write_text("# Section\n\nSimple body text.", encoding="utf-8")

    cfg = PipelineConfig(output_dir=tmp_path / "out", chunk_size_chars=80, overlap_chars=10)
    result = run_markdown_analysis(md_file, cfg, assets_dir=tmp_path / "missing-assets")

    report_path = result["report_path"]
    issues_path = result["issues_path"]
    scorecard_path = result["scorecard_path"]
    executive_summary_path = result["executive_summary_path"]
    final_path = result["final_path"]
    report = report_path.read_text(encoding="utf-8")
    issues = issues_path.read_text(encoding="utf-8")
    scorecard = scorecard_path.read_text(encoding="utf-8")
    executive_summary = executive_summary_path.read_text(encoding="utf-8")
    final = final_path.read_text(encoding="utf-8")
    assert "## Reference Assets" not in report
    assert "## Reference Document Status" not in report
    assert "## Document Overview" in report
    assert "# Contract Issues Summary" in issues
    assert "NOT FOUND" in scorecard
    assert "legal review required before signing" in executive_summary
    assert "last_run:" in final
    assert "# Final Synthesized Output:" in final
    assert result["assets_context_included"] is False


def test_sectioned_report_dedupes_takeaways_and_actions() -> None:
    section_order = ["Section A", "Section B"]
    section_buckets = {
        "Section A": {
            "legal_risks": ["Confidentiality duty is broad."],
            "takeaways": [
                "Reference assets are available, enabling a redline strategy anchored to internal standards rather than ad hoc clause-by-clause edits.",
                "Cap liability for indirect damages.",
                "Cap liability for indirect damages!",
                "Confidentiality duties appear linked to use limitations.",
            ],
            "actions": [
                "Propose a mutual indemnity framework.",
                "Propose a mutual indemnity framework",
                "Add cure period language before termination.",
            ],
        },
        "Section B": {
            "legal_risks": ["Termination may be immediate for minor breach."],
            "takeaways": [
                "Cap liability for indirect damages.",
                "Confidentiality obligations are present but scope and carve-outs should be tightened.",
            ],
            "actions": [
                "Propose a mutual indemnity framework.",
                "Negotiate a materiality qualifier for breach triggers.",
            ],
        },
    }

    report = _build_sectioned_analysis_report(
        report_title="Sample",
        chunk_count=4,
        section_order=section_order,
        section_buckets=section_buckets,
        assets_context="",
        asset_statuses=[],
    )

    assert report.count("- Cap liability for indirect damages.") == 1
    assert "reference assets are available" not in report.lower()
    assert report.count("- Propose a mutual indemnity framework.") == 1
    assert "- Confidentiality duties appear linked to use limitations." in report
    assert "- Confidentiality obligations are present but scope and carve-outs should be tightened." in report
    assert "- Negotiate a materiality qualifier for breach triggers." in report


def test_reference_document_status_is_last_section() -> None:
    report = _build_sectioned_analysis_report(
        report_title="Sample",
        chunk_count=1,
        section_order=["Section A"],
        section_buckets={
            "Section A": {
                "legal_risks": ["Broad confidentiality scope."],
                "takeaways": ["Clarify use limitations."],
                "actions": ["Request explicit residuals language."],
            }
        },
        assets_context="# Assets Context\n\n## reference.txt\nAsset prose.\n",
        asset_statuses=[
            {
                "name": "reference.txt",
                "status": "loaded",
                "message": "reference.txt - loaded successfully.",
            }
        ],
    )

    assert report.rstrip().endswith("- reference.txt - loaded successfully.")


def test_sectioned_report_omits_empty_strategic_subsections() -> None:
    section_order = ["Section A", "Section B"]
    section_buckets = {
        "Section A": {
            "legal_risks": ["Clause imposes broad disclosure obligations."],
            "takeaways": ["Narrow disclosure triggers to objective criteria."],
            "actions": ["Request explicit approval workflow for third-party sharing."],
        },
        "Section B": {
            "legal_risks": ["Clause has unilateral injunctive remedy language."],
            "takeaways": ["Narrow disclosure triggers to objective criteria."],
            "actions": ["Request explicit approval workflow for third-party sharing."],
        },
    }

    report = _build_sectioned_analysis_report(
        report_title="Sample",
        chunk_count=2,
        section_order=section_order,
        section_buckets=section_buckets,
        assets_context="",
        asset_statuses=[],
    )

    section_b = report.split("## Section B", maxsplit=1)[1]
    assert "### Legal Risk Findings" in section_b
    assert "- Clause has unilateral injunctive remedy language." in section_b
    assert "### Strategic Takeaways" not in section_b
    assert "### Recommended Next Actions" not in section_b
