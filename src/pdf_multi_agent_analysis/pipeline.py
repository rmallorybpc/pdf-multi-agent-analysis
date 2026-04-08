from pathlib import Path
from datetime import datetime, timezone
import re

from .agents import AnalystAgent, ExtractorAgent, LegalRiskAgent, ReviewerAgent, SynthesizerAgent
from .assets_context import build_assets_context_with_warnings
from .chunking import chunk_markdown
from .config import PipelineConfig
from .converter import pdf_to_markdown


FINAL_OUTPUT_DIR = Path("rfp-markdown/generated")

SCORECARD_CATEGORIES: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = [
    (
        "Confidentiality obligations",
        ("confidential", "proprietary", "non-disclosure", "nondisclosure", "trade secret"),
        ("breach", "disclose", "unauthorized", "injunct", "damages"),
    ),
    (
        "Liability and indemnification",
        ("liability", "liable", "indemn", "hold harmless", "damages", "losses"),
        ("unlimited", "any and all", "consequential", "punitive", "gross negligence"),
    ),
    (
        "Termination rights",
        ("terminate", "termination", "term", "survive", "expiration"),
        ("immediate", "for convenience", "without cause", "material breach"),
    ),
    (
        "Intellectual property",
        ("intellectual property", "ip", "ownership", "license", "derivative"),
        ("irrevocable", "perpetual", "assign", "exclusive", "royalty-free"),
    ),
    (
        "Jurisdiction and governing law",
        ("governing law", "jurisdiction", "venue", "arbitration", "forum"),
        ("exclusive", "waive", "foreign", "mandatory", "binding"),
    ),
    (
        "Data protection and security",
        ("data", "security", "privacy", "personal information", "breach notification"),
        ("incident", "access", "encrypt", "compliance", "unauthorized"),
    ),
]

RISK_ORDER = {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "NOT FOUND": 0}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _build_final_markdown(report_title: str, source_label: str, synthesized_sections: list[str]) -> str:
    chunks = [section.strip() for section in synthesized_sections if section.strip()]
    body_lines = [f"# Final Synthesized Output: {report_title}", ""]
    if not chunks:
        body_lines.append("No synthesized output was generated.")
    else:
        for i, section in enumerate(chunks, start=1):
            body_lines.append(f"## Chunk {i}")
            body_lines.append(section)
            body_lines.append("")

    frontmatter = [
        "---",
        f'title: "{report_title.replace("\"", "\\\"")}"',
        f'source: "{source_label.replace("\"", "\\\"")}"',
        f'last_run: "{_utc_now_iso()}"',
        "---",
        "",
    ]
    return "\n".join(frontmatter + body_lines).strip() + "\n"


def _final_output_path(source_name: str) -> Path:
    stem = Path(source_name).stem
    final_stem = stem if stem.endswith("-final") else f"{stem}-final"
    return FINAL_OUTPUT_DIR / f"{final_stem}.md"


def _extract_sentences(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []
    return [s.strip() for s in re.split(r"(?<=[.!?;])\s+", normalized) if s.strip()]


def _score_issue_line(line: str) -> int:
    lowered = line.lower()
    score = 0
    if any(term in lowered for term in ("unlimited", "any and all", "exclusive", "irrevocable", "immediate", "injunct", "indemn")):
        score += 3
    if any(term in lowered for term in ("liable", "liability", "termination", "breach", "damages", "waive", "personal information")):
        score += 2
    if any(term in lowered for term in ("shall", "must", "will", "obligation", "required")):
        score += 1
    return score


def _issue_risk_label(score: int) -> str:
    if score >= 5:
        return "HIGH"
    if score >= 3:
        return "MEDIUM"
    return "LOW"


def _collect_issue_lines(issues_report: str) -> list[str]:
    lines = [ln.strip() for ln in issues_report.splitlines()]
    collected: list[str] = []
    for line in lines:
        if line.startswith("- "):
            collected.append(line[2:].strip())
        elif line and not line.startswith("#") and line.lower() != "potential obligations/risks:":
            collected.append(line)
    deduped: list[str] = []
    seen: set[str] = set()
    for line in collected:
        key = line.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(line)
    return deduped


def _build_scorecard(analysis_report: str, issues_report: str) -> tuple[str, str, list[str], list[dict[str, str]]]:
    full_text = f"{analysis_report}\n{issues_report}"
    sentences = _extract_sentences(full_text)
    score_rows: list[dict[str, str]] = []

    for category, primary_terms, elevated_terms in SCORECARD_CATEGORIES:
        matching_sentences = [
            sentence
            for sentence in sentences
            if any(term in sentence.lower() for term in primary_terms)
        ]
        if not matching_sentences:
            score_rows.append(
                {
                    "category": category,
                    "risk": "NOT FOUND",
                    "confidence": "LOW",
                    "rationale": "No supporting contract text detected for this category; treat as a missing clause gap.",
                }
            )
            continue

        sentence_hits = len(matching_sentences)
        elevated_hits = sum(
            1
            for sentence in matching_sentences
            if any(term in sentence.lower() for term in elevated_terms)
        )
        if elevated_hits >= 2 or sentence_hits >= 5:
            risk = "HIGH"
        elif elevated_hits >= 1 or sentence_hits >= 2:
            risk = "MEDIUM"
        else:
            risk = "LOW"

        if sentence_hits >= 4:
            confidence = "HIGH"
        elif sentence_hits >= 2:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"

        rationale_source = matching_sentences[0]
        rationale_clean = rationale_source[:160].strip()
        if len(rationale_source) > 160:
            rationale_clean += "..."

        score_rows.append(
            {
                "category": category,
                "risk": risk,
                "confidence": confidence,
                "rationale": f"Detected clause language indicates {risk.lower()} exposure; sample: {rationale_clean}",
            }
        )

    overall_value = max((RISK_ORDER[row["risk"]] for row in score_rows), default=0)
    overall_rating = next((label for label, value in RISK_ORDER.items() if value == overall_value), "NOT FOUND")
    if overall_rating == "NOT FOUND":
        overall_rating = "MEDIUM"

    scored_issues = [
        {
            "text": line,
            "score": _score_issue_line(line),
        }
        for line in _collect_issue_lines(issues_report)
    ]
    scored_issues.sort(key=lambda item: item["score"], reverse=True)
    top_issues = [
        {
            "risk": _issue_risk_label(item["score"]),
            "text": item["text"],
        }
        for item in scored_issues[:3]
    ]

    not_found_categories = [row["category"] for row in score_rows if row["risk"] == "NOT FOUND"]

    lines = [f"Overall contract risk rating: {overall_rating}", ""]
    lines.append("| Category | Risk Rating | Confidence | Rationale |")
    lines.append("| --- | --- | --- | --- |")
    for row in score_rows:
        rationale = row["rationale"].replace("|", "/")
        lines.append(f"| {row['category']} | {row['risk']} | {row['confidence']} | {rationale} |")
    lines.append("")
    lines.append("Top 3 highest-priority issues:")
    if top_issues:
        for i, issue in enumerate(top_issues, start=1):
            lines.append(f"{i}. [{issue['risk']}] {issue['text']}")
    else:
        lines.append("1. [LOW] No explicit issue lines were detected in the issues summary.")

    scorecard = "\n".join(lines).strip() + "\n"
    return scorecard, overall_rating, not_found_categories, score_rows


def _extract_contract_metadata(report_title: str, analysis_report: str) -> tuple[str, str, str, str]:
    contract_name = Path(report_title).stem
    full_text = re.sub(r"\s+", " ", analysis_report)
    lowered = full_text.lower()

    contract_type = "Commercial agreement"
    if any(term in lowered for term in ("non-disclosure", "nondisclosure", "confidentiality")):
        contract_type = "Non-disclosure agreement"
    elif "service" in lowered:
        contract_type = "Services agreement"
    elif "purchase" in lowered:
        contract_type = "Purchase agreement"

    parties = "Not clearly identified"
    between_match = re.search(r"between\s+([^.;]+)", full_text, flags=re.IGNORECASE)
    if between_match:
        parties = between_match.group(1).strip()

    effective_date = "Not stated"
    date_match = re.search(
        r"(?:effective\s+date|dated|effective\s+as\s+of)[:\s]+([A-Za-z]+\s+\d{1,2},\s+\d{4}|\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4})",
        full_text,
        flags=re.IGNORECASE,
    )
    if date_match:
        effective_date = date_match.group(1).strip()

    return contract_name, contract_type, parties, effective_date


def _not_found_categories_from_scorecard(scorecard: str) -> list[str]:
    categories: list[str] = []
    for line in scorecard.splitlines():
        if not line.startswith("|"):
            continue
        if "| NOT FOUND |" not in line:
            continue
        cells = [cell.strip() for cell in line.split("|")]
        if len(cells) >= 3 and cells[1] and cells[1] != "Category":
            categories.append(cells[1])
    return categories


def _build_executive_summary(
    report_title: str,
    analysis_report: str,
    scorecard: str,
    overall_rating: str,
    score_rows: list[dict[str, str]],
) -> str:
    contract_name, contract_type, parties, effective_date = _extract_contract_metadata(report_title, analysis_report)
    run_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    not_found_categories = _not_found_categories_from_scorecard(scorecard)

    high_or_medium = [row for row in score_rows if row["risk"] in ("HIGH", "MEDIUM")]
    high_or_medium.sort(key=lambda row: RISK_ORDER[row["risk"]], reverse=True)

    key_risks: list[str] = []
    for row in high_or_medium[:5]:
        key_risks.append(f"{row['category']}: {row['risk']} risk exposure.")
    if not key_risks:
        key_risks.append("No major risk triggers were detected.")

    actions: list[str] = []
    for category in not_found_categories:
        actions.append(f"Add {category.lower()} clause; legal review required before signing.")
    for row in high_or_medium:
        if len(actions) >= 5:
            break
        actions.append(f"Negotiate {row['category'].lower()} terms before approval.")
    if len(actions) < 3:
        actions.append("Confirm business owner accepts residual contract risk profile.")

    open_questions = [
        "Who owns final approval authority for unresolved risks?",
        "Which fallback terms are acceptable if counterparty rejects edits?",
        "Can signing proceed if mandatory missing clauses remain unresolved?",
    ]

    summary_lines = [
        "## Contract Metadata",
        f"- Contract name: {contract_name}",
        f"- Contract type: {contract_type}",
        f"- Parties involved: {parties}",
        f"- Effective date: {effective_date}",
        f"- Analysis run date: {run_date}",
        "",
        "## What This Contract Does",
        "This agreement sets rules for sharing and handling sensitive business information between the parties.",
        "It defines allowed use, restrictions, and consequences if obligations are not met.",
        "It also sets practical terms that affect enforcement, exit options, and operational risk.",
        "",
        "## Overall Risk Assessment",
        f"Overall contract risk is {overall_rating} based on the consolidated scorecard.",
        "",
        "## Key Risks Requiring Attention",
    ]
    summary_lines.extend(f"- {item[:118]}" for item in key_risks[:5])
    summary_lines.extend(["", "## Recommended Actions Before Signing"])
    summary_lines.extend(f"- {item[:118]}" for item in actions[:5])
    summary_lines.extend(["", "## Open Questions For Legal Review"])
    summary_lines.extend(f"- {item}" for item in open_questions[:3])

    return "\n".join(summary_lines).strip() + "\n"


def _analyze_markdown(
    markdown: str,
    report_title: str,
    config: PipelineConfig,
    assets_context: str = "",
    asset_warnings: list[str] | None = None,
) -> dict:
    chunks = chunk_markdown(markdown, config.chunk_size_chars, config.overlap_chars)
    agents = [ExtractorAgent(), ReviewerAgent(), AnalystAgent(), LegalRiskAgent(), SynthesizerAgent()]

    report_lines = [f"# Analysis Report: {report_title}", ""]
    issues_lines = [f"# Contract Issues Summary: {report_title}", ""]
    synthesized_sections: list[str] = []
    warnings = asset_warnings or []
    if warnings:
        report_lines.append("## Asset Extraction Warnings")
        for warning in warnings:
            report_lines.append(f"- WARNING: {warning}")
        report_lines.append("")

    if assets_context.strip():
        report_lines.append("## Reference Assets")
        report_lines.append(assets_context[:4000].strip())
        report_lines.append("")

    for i, chunk in enumerate(chunks, start=1):
        report_lines.append(f"## Chunk {i}")
        for agent in agents:
            result = agent.run(chunk, assets_context=assets_context)
            report_lines.append(f"### {result.agent_name}")
            report_lines.append(result.content)
            report_lines.append("")
            if result.agent_name == "legal-risk":
                issues_lines.append(f"## Chunk {i}")
                issues_lines.append(result.content)
                issues_lines.append("")
            if result.agent_name == "synthesizer":
                synthesized_sections.append(result.content)

    report = "\n".join(report_lines).strip() + "\n"
    issues_report = "\n".join(issues_lines).strip() + "\n"
    scorecard, overall_rating, _not_found_categories, score_rows = _build_scorecard(report, issues_report)
    executive_summary = _build_executive_summary(
        report_title,
        report,
        scorecard,
        overall_rating,
        score_rows,
    )
    return {
        "report": report,
        "issues_report": issues_report,
        "scorecard": scorecard,
        "executive_summary": executive_summary,
        "final_markdown": _build_final_markdown(report_title, report_title, synthesized_sections),
        "chunk_count": len(chunks),
    }


def run_pipeline(pdf_path: Path, config: PipelineConfig | None = None) -> dict:
    """Run PDF->Markdown conversion and multi-agent analysis."""
    cfg = config or PipelineConfig()
    cfg.output_dir.mkdir(parents=True, exist_ok=True)

    markdown = pdf_to_markdown(pdf_path)
    md_path = cfg.output_dir / f"{pdf_path.stem}.md"
    md_path.write_text(markdown, encoding="utf-8")

    analysis = _analyze_markdown(markdown, pdf_path.name, cfg)
    report_path = cfg.output_dir / f"{pdf_path.stem}.analysis.md"
    issues_path = cfg.output_dir / f"{pdf_path.stem}.issues.md"
    scorecard_path = cfg.output_dir / f"{pdf_path.stem}.scorecard.md"
    executive_summary_path = cfg.output_dir / f"{pdf_path.stem}.executive-summary.md"
    final_path = _final_output_path(pdf_path.name)
    final_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(analysis["report"], encoding="utf-8")
    issues_path.write_text(analysis["issues_report"], encoding="utf-8")
    scorecard_path.write_text(analysis["scorecard"], encoding="utf-8")
    executive_summary_path.write_text(analysis["executive_summary"], encoding="utf-8")
    final_path.write_text(analysis["final_markdown"], encoding="utf-8")

    return {
        "markdown_path": md_path,
        "report_path": report_path,
        "issues_path": issues_path,
        "scorecard_path": scorecard_path,
        "executive_summary_path": executive_summary_path,
        "final_path": final_path,
        "chunk_count": analysis["chunk_count"],
    }


def run_markdown_analysis(
    markdown_path: Path,
    config: PipelineConfig | None = None,
    assets_dir: Path | None = None,
) -> dict:
    """Run multi-agent analysis for an existing markdown file."""
    cfg = config or PipelineConfig()
    cfg.output_dir.mkdir(parents=True, exist_ok=True)

    markdown = markdown_path.read_text(encoding="utf-8")
    assets_context = ""
    asset_warnings: list[str] = []
    if assets_dir is not None:
        assets_context, asset_warnings = build_assets_context_with_warnings(
            assets_dir,
            max_chars_per_file=cfg.max_asset_chars_per_file,
            pdf_ocr_fallback=cfg.asset_pdf_ocr_fallback,
            pdf_ocr_max_pages=cfg.asset_pdf_ocr_max_pages,
            pdf_min_text_chars=cfg.asset_pdf_min_text_chars,
            pdf_max_single_char_token_ratio=cfg.asset_pdf_max_single_char_token_ratio,
        )

    analysis = _analyze_markdown(
        markdown,
        markdown_path.name,
        cfg,
        assets_context=assets_context,
        asset_warnings=asset_warnings,
    )
    report_path = cfg.output_dir / f"{markdown_path.stem}.analysis.md"
    issues_path = cfg.output_dir / f"{markdown_path.stem}.issues.md"
    scorecard_path = cfg.output_dir / f"{markdown_path.stem}.scorecard.md"
    executive_summary_path = cfg.output_dir / f"{markdown_path.stem}.executive-summary.md"
    final_path = _final_output_path(markdown_path.name)
    final_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(analysis["report"], encoding="utf-8")
    issues_path.write_text(analysis["issues_report"], encoding="utf-8")
    scorecard_path.write_text(analysis["scorecard"], encoding="utf-8")
    executive_summary_path.write_text(analysis["executive_summary"], encoding="utf-8")
    final_path.write_text(analysis["final_markdown"], encoding="utf-8")

    return {
        "report_path": report_path,
        "issues_path": issues_path,
        "scorecard_path": scorecard_path,
        "executive_summary_path": executive_summary_path,
        "final_path": final_path,
        "chunk_count": analysis["chunk_count"],
        "assets_context_included": bool(assets_context.strip()),
        "asset_warnings": asset_warnings,
    }
