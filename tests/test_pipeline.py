from pathlib import Path

from pdf_multi_agent_analysis.config import PipelineConfig
from pdf_multi_agent_analysis import pipeline as pipeline_module
from pdf_multi_agent_analysis.pipeline import _analyze_markdown, _build_sectioned_analysis_report, _find_heading_candidate, run_markdown_analysis


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


def test_sectioned_report_dedupes_legal_risks_and_preserves_section_guidance() -> None:
    section_order = ["Section A", "Section B"]
    section_buckets = {
        "Section A": {
            "legal_risks": [
                "Confidentiality duty is broad.",
                "Confidentiality duty is broad.",
                "TERMINATION requires 30 days notice.",
            ],
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
            "legal_risks": [
                "termination requires 30 days notice.",
                "Termination may be immediate for minor breach.",
            ],
            "takeaways": [
                "Reference assets are available, enabling a redline strategy anchored to internal standards rather than ad hoc clause-by-clause edits.",
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

    assert report.count("- Confidentiality duty is broad.") == 1
    assert report.count("- TERMINATION requires 30 days notice.") == 1
    assert report.count("- termination requires 30 days notice.") == 0
    assert report.count("- Cap liability for indirect damages.") == 2
    assert report.count("- Propose a mutual indemnity framework.") == 2
    assert report.lower().count("reference assets are available") == 0
    assert "- Confidentiality duties appear linked to use limitations." in report
    assert "- Confidentiality obligations are present but scope and carve-outs should be tightened." in report
    assert "- Negotiate a materiality qualifier for breach triggers." in report


def test_sectioned_report_suppresses_reference_assets_boilerplate_in_all_sections() -> None:
    section_order = ["Definitions and Interpretation", "Section B"]
    section_buckets = {
        "Definitions and Interpretation": {
            "legal_risks": ["Clause imposes broad disclosure obligations."],
            "takeaways": [
                "Reference assets are loaded, supporting a redline plan aligned to internal standards.",
                "Narrow disclosure triggers to objective criteria.",
            ],
            "actions": ["Request explicit approval workflow for third-party sharing."],
        },
        "Section B": {
            "legal_risks": ["Clause has unilateral injunctive remedy language."],
            "takeaways": [
                "Assets are available and support a redline strategy anchored to internal standards.",
                "Clarify carve-outs for compelled disclosures.",
            ],
            "actions": ["Add cure period language before termination."],
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

    assert "Reference assets are loaded" not in report
    assert "Assets are available and support a redline strategy" not in report
    assert "- Narrow disclosure triggers to objective criteria." in report
    assert "- Clarify carve-outs for compelled disclosures." in report


def test_sectioned_report_dedupes_legal_risk_fragments_and_keeps_complete_clause() -> None:
    section_order = ["Termination", "Limitation of Liability and Indemnification"]
    section_buckets = {
        "Termination": {
            "legal_risks": [
                "he provisions of this Agreement except portions that are inapplicable to such continuing services shall survive the termination of this Agreement.",
            ],
            "takeaways": ["Add mutual survival carve-outs for operational transitions."],
            "actions": ["Confirm sunset periods for surviving obligations."],
        },
        "Limitation of Liability and Indemnification": {
            "legal_risks": [
                "The provisions of this Agreement except portions that are inapplicable to such continuing services shall survive the termination of this Agreement.",
            ],
            "takeaways": ["Align survival language with liability caps."],
            "actions": ["Ensure indemnity obligations do not survive indefinitely."],
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

    assert report.count("- The provisions of this Agreement except portions that are inapplicable to such continuing services shall survive the termination of this Agreement.") == 1
    assert "- he provisions of this Agreement except portions that are inapplicable to such continuing services shall survive the termination of this Agreement." not in report


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
    assert "### Strategic Takeaways" in section_b
    assert "- Narrow disclosure triggers to objective criteria." in section_b
    assert "### Recommended Next Actions" in section_b
    assert "- Request explicit approval workflow for third-party sharing." in section_b


def test_find_heading_candidate_rejects_stage_and_subsection_labels() -> None:
    assert _find_heading_candidate("Detected section heading: Stage C Final Markdown") is None
    assert _find_heading_candidate("## Stage A Notes") is None
    assert _find_heading_candidate("Detected section heading: 7.3 SS&C represents and warrants to Fund that") is None
    assert _find_heading_candidate("Detected section heading: 2. Services and Fees") == "2. Services and Fees"
    assert _find_heading_candidate("Detected section heading: Termination") == "Termination"
    assert (
        _find_heading_candidate(
            "Detected section heading: 5. Termination 5.1. A Party also may, by written notice to the other Party, terminate this Agreement if any of the following events occur"
        )
        is None
    )
    assert _find_heading_candidate("Detected section heading: 5. Maintain books and records with respect to the Services.") is None


def test_analyze_markdown_defaults_first_section_and_reuses_latest_valid_section(monkeypatch) -> None:
    class _FakeAgent:
        def __init__(self, name: str, outputs: list[str]) -> None:
            self.name = name
            self._outputs = outputs
            self._index = 0

        def run(self, markdown_chunk: str, assets_context: str = ""):
            from pdf_multi_agent_analysis.agents import AgentResult

            output = self._outputs[self._index]
            self._index += 1
            return AgentResult(self.name, output)

    chunks = ["frontmatter chunk", "mid chunk with subsection text", "final chunk"]
    monkeypatch.setattr(pipeline_module, "chunk_markdown", lambda *_args, **_kwargs: chunks)
    monkeypatch.setattr(
        pipeline_module,
        "ExtractorAgent",
        lambda: _FakeAgent(
            "extractor",
            [
                "title: Test\nsource: test.md",
                "Detected section heading: 7.3 SS&C represents and warrants to Fund that",
                "Detected section heading: Stage A Notes",
            ],
        ),
    )
    monkeypatch.setattr(pipeline_module, "ReviewerAgent", lambda: _FakeAgent("reviewer", ["ok", "ok", "ok"]))
    monkeypatch.setattr(pipeline_module, "AnalystAgent", lambda: _FakeAgent("analyst", ["ok", "ok", "ok"]))
    monkeypatch.setattr(
        pipeline_module,
        "LegalRiskAgent",
        lambda: _FakeAgent(
            "legal-risk",
            [
                "Potential obligations/risks:\n- Confidentiality obligations apply.",
                "Potential obligations/risks:\n- Stage C Final Markdown",
                "Potential obligations/risks:\n- Liability obligations apply.",
            ],
        ),
    )
    monkeypatch.setattr(
        pipeline_module,
        "SynthesizerAgent",
        lambda: _FakeAgent(
            "synthesizer",
            [
                "Strategic takeaways:\n- Clarify definitions.\n\nRecommended next actions:\n- Tighten scope.",
                "Strategic takeaways:\n- Stage B Executive Refinement\n\nRecommended next actions:\n- Preserve parent section.",
                "Strategic takeaways:\n- Confirm liability scope.\n\nRecommended next actions:\n- Track negotiation points.",
            ],
        ),
    )

    cfg = PipelineConfig(chunk_size_chars=50, overlap_chars=0)
    analysis = _analyze_markdown("ignored", "contract.md", cfg)
    report = analysis["report"]

    assert "## Definitions and Interpretation" in report
    assert "## 7.3 SS&C represents and warrants to Fund that" not in report
    assert "Stage C Final Markdown" not in report
    assert "Stage B Executive Refinement" not in report
    assert analysis["section_count"] == 1
