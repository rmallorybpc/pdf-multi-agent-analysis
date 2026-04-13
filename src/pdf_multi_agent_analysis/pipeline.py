from pathlib import Path
from datetime import datetime, timezone
import os
import re
from difflib import SequenceMatcher

from .agents import AnalystAgent, ExtractorAgent, LegalRiskAgent, ReviewerAgent, SynthesizerAgent
from .assets_context import build_assets_context_with_status
from .chunking import chunk_markdown
from .config import PipelineConfig
from .converter import pdf_to_markdown


FINAL_OUTPUT_DIR = Path("rfp-markdown/generated")
AUDIT_ROOT_DIR = Path("rfp-markdown/audit")

SCORECARD_CATEGORIES: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = [
    (
        "Confidentiality obligations",
        (
            "confidential",
            "confidentiality",
            "confidential information",
            "proprietary",
            "proprietary information",
            "non-disclosure",
            "nondisclosure",
            "trade secret",
        ),
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

MUTUAL_PROTECTIVE_TERMS: tuple[str, ...] = (
    "mutual",
    "each party",
    "both parties",
    "reasonable care",
    "commercially reasonable",
    "except as required by law",
    "confidential information shall not include",
)

ONE_SIDED_TERMS: tuple[str, ...] = (
    "sole discretion",
    "solely by",
    "unilateral",
    "exclusive remedy",
    "receiving party shall",
)

GAP_TERMS: tuple[str, ...] = (
    "missing",
    "not stated",
    "not specified",
    "silent",
    "unclear",
    "not provided",
)

CATEGORY_PROTECTIVE_TERMS: dict[str, tuple[str, ...]] = {
    "Confidentiality obligations": (
        "no less than reasonable care",
        "confidential information shall not include",
        "required by applicable law",
    ),
    "Liability and indemnification": (
        "no liability",
        "limited liability",
        "except for",
    ),
    "Termination rights": (
        "for material breach",
        "written notice",
        "cure period",
    ),
    "Intellectual property": (
        "remains the property",
        "no license",
        "sole property",
    ),
    "Jurisdiction and governing law": (
        "non-exclusive",
        "mutual consent",
        "good faith",
    ),
    "Data protection and security": (
        "reasonable safeguards",
        "industry standard",
        "security measures",
    ),
}

DEFAULT_FIRST_SECTION_HEADING = "Definitions and Interpretation"

PIPELINE_STAGE_LABELS: tuple[str, ...] = (
    "Stage C Final Markdown",
    "Stage B Executive Refinement",
    "Stage A Notes",
    "Stage A Critique",
    "Stage D",
)

KNOWN_CONTRACT_SECTION_HEADINGS: tuple[str, ...] = (
    "Definitions",
    "Definitions and Interpretation",
    "Services and Fees",
    "Services",
    "Term",
    "Termination",
    "Confidentiality",
    "Indemnification",
    "Limitation of Liability",
    "Data Protection",
    "Governing Law",
    "Notices",
    "Miscellaneous",
)

KNOWN_COMPLETE_LEADING_WORDS: set[str] = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "if",
    "in",
    "is",
    "it",
    "may",
    "must",
    "of",
    "on",
    "or",
    "shall",
    "the",
    "to",
    "with",
    "without",
    "will",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _make_audit_run_id() -> str:
    run_id = os.getenv("GITHUB_RUN_ID", "").strip()
    run_attempt = os.getenv("GITHUB_RUN_ATTEMPT", "").strip()
    if run_id and run_attempt:
        return f"{run_id}-{run_attempt}"
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _normalize_bullet_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _canonicalize_exact_clause_text(text: str) -> str:
    # Exact-match dedupe key for legal clause extracts: case-insensitive + trim-only.
    return text.strip().lower()


def _canonicalize_bullet_text(text: str) -> str:
    normalized = _normalize_bullet_text(text).lower()
    # Strip punctuation for stable deduplication keys while preserving token order.
    normalized = re.sub(r"[^a-z0-9\s]", "", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _is_reference_assets_boilerplate(text: str) -> bool:
    canonical = _canonicalize_bullet_text(text)
    if not canonical:
        return False

    has_reference_assets = bool(
        re.search(r"\b(reference\s+assets?|assets?)\b", canonical)
        and re.search(r"\b(available|loaded|load|provided|included|attached|supplied|present)\b", canonical)
    )
    has_redline_strategy = bool(
        re.search(r"\bredline\w*\b", canonical)
        and re.search(r"\b(strategy|strategic|approach|plan|playbook|method)\b", canonical)
    )
    has_internal_standards = bool(re.search(r"\binternal\s+(standard|standards|baseline|playbook|templates?)\b", canonical))
    return has_reference_assets and has_redline_strategy and has_internal_standards


def _strip_numbered_heading_prefix(text: str) -> str:
    stripped = text.strip()
    return re.sub(r"^\d+\.\s*", "", stripped).strip()


def _looks_like_known_heading_vocabulary(text: str) -> bool:
    base = _strip_numbered_heading_prefix(text).lower()
    return any(base == heading.lower() for heading in KNOWN_CONTRACT_SECTION_HEADINGS)


def _contains_action_verb(text: str) -> bool:
    lowered = _strip_numbered_heading_prefix(text).lower()
    return bool(
        re.search(
            r"\b(?:maintain(?:s|ed|ing)?|provide(?:s|d|ing)?|terminate(?:s|d|ing)?|perform(?:s|ed|ing)?|deliver(?:s|ed|ing)?|execute(?:s|d|ing)?|shall|may|agree(?:s|d|ing)?)\b",
            lowered,
        )
    )


def _strip_leading_partial_word(text: str) -> str:
    stripped = text.strip()
    match = re.match(r"^([a-z]{1,3})\s+(.+)$", stripped)
    if not match:
        return stripped
    leading = match.group(1)
    if leading in KNOWN_COMPLETE_LEADING_WORDS:
        return stripped
    return match.group(2).strip()


def _canonicalize_legal_risk_text(text: str) -> str:
    stripped = _normalize_bullet_text(text)
    if not stripped:
        return ""
    lowered = _strip_leading_partial_word(stripped).strip().lower()
    lowered = re.sub(r"^(?:the|a|an)\s+", "", lowered)
    return re.sub(r"\s+", " ", lowered)


def _is_more_complete_legal_risk(candidate: str, existing: str) -> bool:
    candidate_clean = _normalize_bullet_text(candidate)
    existing_clean = _normalize_bullet_text(existing)
    if len(candidate_clean) != len(existing_clean):
        return len(candidate_clean) > len(existing_clean)

    candidate_has_partial_prefix = _strip_leading_partial_word(candidate_clean) != candidate_clean
    existing_has_partial_prefix = _strip_leading_partial_word(existing_clean) != existing_clean
    if candidate_has_partial_prefix != existing_has_partial_prefix:
        return not candidate_has_partial_prefix

    return candidate_clean < existing_clean


def _are_near_duplicate_bullets(existing: str, candidate: str) -> bool:
    existing_key = _canonicalize_bullet_text(existing)
    candidate_key = _canonicalize_bullet_text(candidate)
    if not existing_key or not candidate_key:
        return False
    if existing_key == candidate_key:
        return True

    existing_tokens = set(existing_key.split())
    candidate_tokens = set(candidate_key.split())
    if not existing_tokens or not candidate_tokens:
        return False

    intersection = existing_tokens & candidate_tokens
    union = existing_tokens | candidate_tokens
    token_jaccard = len(intersection) / len(union)
    overlap_existing = len(intersection) / len(existing_tokens)
    overlap_candidate = len(intersection) / len(candidate_tokens)
    seq_ratio = SequenceMatcher(None, existing_key, candidate_key).ratio()

    # Conservative near-duplicate rules to avoid collapsing distinct legal insights.
    if seq_ratio >= 0.95 and token_jaccard >= 0.8:
        return True
    if min(len(existing_key), len(candidate_key)) >= 50 and (
        existing_key in candidate_key or candidate_key in existing_key
    ) and max(overlap_existing, overlap_candidate) >= 0.9:
        return True
    return False


def _append_unique_bullet(
    items: list[str],
    seen_exact_keys: set[str],
    candidate: str,
) -> bool:
    normalized = _normalize_bullet_text(candidate)
    key = _canonicalize_bullet_text(normalized)
    if not normalized or not key or key in seen_exact_keys:
        return False
    if any(_are_near_duplicate_bullets(existing, normalized) for existing in items):
        return False
    seen_exact_keys.add(key)
    items.append(normalized)
    return True


def _parse_assets_context_sections(assets_context: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current_name: str | None = None

    for line in assets_context.splitlines():
        header = re.match(r"^##\s+(.+)$", line.strip())
        if header:
            current_name = header.group(1).strip()
            sections[current_name] = []
            continue
        if current_name is None:
            continue
        sections[current_name].append(line)

    return {name: "\n".join(lines).strip() for name, lines in sections.items()}


def _append_reference_assets_section(
    lines: list[str],
    assets_context: str,
    asset_statuses: list[dict[str, str]],
) -> None:
    if not asset_statuses:
        return

    content_by_asset = _parse_assets_context_sections(assets_context)
    lines.append("## Reference Assets")
    lines.append("")

    for entry in asset_statuses:
        name = entry.get("name", "")
        status = entry.get("status", "")
        message = entry.get("message", "")
        if not name:
            continue

        lines.append(f"### {name}")
        if status == "failed":
            lines.append(f"- {message}")
            lines.append("")
            continue

        content = content_by_asset.get(name, "")
        if content:
            lines.append(content)
        elif message:
            lines.append(f"- {message}")
        lines.append("")


def _append_reference_document_status_section(lines: list[str], asset_statuses: list[dict[str, str]]) -> None:
    if not asset_statuses:
        return

    lines.append("## Reference Document Status")
    lines.append("")
    for entry in asset_statuses:
        message = entry.get("message", "")
        if message:
            lines.append(f"- {message}")
    lines.append("")


def _extract_synth_list(synth_content: str, heading: str) -> list[str]:
    heading_key = heading.strip().lower()
    lines = synth_content.splitlines()
    collecting = False
    collected_lines: list[str] = []

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            if collecting:
                collected_lines.append(line)
            continue

        canonical_heading = line.lower().lstrip("#").strip().rstrip(":").strip()
        is_heading_line = canonical_heading == heading_key
        is_other_heading = bool(re.match(r"^[A-Z][^\n]*:\s*$", line)) or line.startswith("#")

        if is_heading_line:
            collecting = True
            continue

        if collecting and is_other_heading:
            break

        if collecting:
            collected_lines.append(line)

    if not collected_lines:
        return []

    bullets: list[str] = []
    for line in collected_lines:
        if line.startswith("- "):
            cleaned = _normalize_bullet_text(line[2:])
            if cleaned and not _is_pipeline_stage_label(cleaned):
                bullets.append(cleaned)
        elif re.match(r"^\d+\.\s+", line):
            cleaned = _normalize_bullet_text(re.sub(r"^\d+\.\s+", "", line))
            if cleaned and not _is_pipeline_stage_label(cleaned):
                bullets.append(cleaned)
    return bullets


def _topic_from_legal_risk(text: str) -> str | None:
    lowered = text.lower()
    topics: list[tuple[str, tuple[str, ...]]] = [
        ("Confidentiality and Information Use", ("confidential", "proprietary", "disclos", "non-disclosure", "nondisclosure")),
        ("Liability and Indemnification", ("liability", "liable", "indemn", "damages", "hold harmless")),
        ("Termination and Survival", ("terminate", "termination", "survive", "expiration", "for convenience")),
        ("Data Protection and Security", ("data", "privacy", "security", "personal information", "breach notification")),
        ("Governing Law and Disputes", ("governed by", "governing law", "jurisdiction", "venue", "arbitration", "forum")),
        ("Remedies and Enforcement", ("injunct", "equitable", "specific performance", "waive", "waiver")),
    ]

    best_topic: str | None = None
    best_score = 0
    for label, keywords in topics:
        score = sum(lowered.count(keyword) for keyword in keywords)
        if score > best_score:
            best_topic = label
            best_score = score
    if best_score <= 0:
        return None
    return best_topic


def _is_pipeline_stage_label(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return False
    if re.match(r"^stage\b", normalized, flags=re.IGNORECASE):
        return True
    return normalized.lower() in {label.lower() for label in PIPELINE_STAGE_LABELS}


def _clean_heading_candidate(text: str | None) -> str | None:
    if text is None:
        return None

    heading = re.sub(r"\s+", " ", text).strip().rstrip(":")
    if not heading or _is_pipeline_stage_label(heading):
        return None

    # Apply promotion rejection rules before any heading promotion logic.
    if len(heading.split()) > 15:
        return None

    if not _looks_like_known_heading_vocabulary(heading) and _contains_action_verb(heading):
        return None

    numbered_match = re.match(r"^(\d+)\.\s+([A-Z][^\n]{1,200})$", heading)
    if numbered_match:
        return f"{numbered_match.group(1)}. {numbered_match.group(2).strip()}"

    if re.match(r"^\d+\.\d+", heading):
        return None

    for allowed in KNOWN_CONTRACT_SECTION_HEADINGS:
        if heading.lower() == allowed.lower():
            return allowed

    return None


def _filter_pipeline_stage_lines(text: str) -> str:
    if not text.strip():
        return text

    filtered_lines: list[str] = []
    for line in text.splitlines():
        if _is_pipeline_stage_label(line.strip()):
            continue
        filtered_lines.append(line)
    return "\n".join(filtered_lines).strip()


def _find_heading_candidate(text: str) -> str | None:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for line in lines:
        if line == "---" or re.match(r"^(title|source|last_run)\s*:", line, flags=re.IGNORECASE):
            continue

        detected_match = re.match(r"^Detected section heading:\s*(.+)$", line, flags=re.IGNORECASE)
        if detected_match:
            heading = _clean_heading_candidate(detected_match.group(1))
            if heading is not None:
                return heading
            continue

        md_match = re.match(r"^#{1,6}\s+(.+)$", line)
        if md_match:
            heading = _clean_heading_candidate(md_match.group(1))
            if heading is not None:
                return heading
            continue

        formal_patterns = [
            r"^(\d+)\.\s+([A-Z][^\n]{2,140})$",
            r"^(Section\s+[A-Za-z0-9.\-]+\s*[:.-]?\s*[^\n]{2,160})$",
            r"^(Article\s+[A-Za-z0-9.\-]+\s*[:.-]?\s*[^\n]{2,160})$",
        ]
        for pattern in formal_patterns:
            match = re.match(pattern, line, flags=re.IGNORECASE)
            if not match:
                continue
            if len(match.groups()) >= 2:
                heading = _clean_heading_candidate(f"{match.group(1)}. {match.group(2).strip()}")
            else:
                heading = _clean_heading_candidate(match.group(1).strip())
            if heading is not None:
                return heading
    return None


def _extract_legal_risk_bullets(legal_risk_content: str) -> list[str]:
    bullets: list[str] = []
    for line in legal_risk_content.splitlines():
        line = line.strip()
        if line.startswith("- "):
            cleaned = _normalize_bullet_text(line[2:])
            if cleaned and not _is_pipeline_stage_label(cleaned):
                bullets.append(cleaned)
    return bullets


def _build_diagnostics_report(report_title: str, chunk_diagnostics: list[dict[str, str]]) -> str:
    lines = [f"# Chunk Diagnostics: {report_title}", ""]
    if not chunk_diagnostics:
        lines.append("No chunk diagnostics were generated.")
        return "\n".join(lines).strip() + "\n"

    for item in chunk_diagnostics:
        lines.append(f"## Chunk {item['chunk_index']}")
        lines.append(f"### Section assignment")
        lines.append(item["section_name"])
        lines.append("")
        lines.append("### extractor")
        lines.append(item["extractor"])
        lines.append("")
        lines.append("### reviewer")
        lines.append(item["reviewer"])
        lines.append("")
        lines.append("### analyst")
        lines.append(item["analyst"])
        lines.append("")
        lines.append("### synthesizer")
        lines.append(item["synthesizer"])
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _build_sectioned_analysis_report(
    report_title: str,
    chunk_count: int,
    section_order: list[str],
    section_buckets: dict[str, dict[str, list[str]]],
    assets_context: str,
    asset_statuses: list[dict[str, str]],
) -> str:
    lines = [f"# Analysis Report: {report_title}", ""]
    lines.append("## Document Overview")
    lines.append(f"- Chunks processed: {chunk_count}. Sections detected: {len(section_order)}.")
    lines.append("")

    legal_risk_index_by_key: dict[str, tuple[str, int]] = {}
    deduped_by_section: dict[str, dict[str, list[str]]] = {}

    for section_name in section_order:
        bucket = section_buckets[section_name]
        deduped_legal_risks: list[str] = []
        deduped_takeaways: list[str] = []
        deduped_actions: list[str] = []
        seen_takeaways_section: set[str] = set()
        seen_actions_section: set[str] = set()

        for risk in bucket["legal_risks"]:
            normalized = _normalize_bullet_text(risk)
            key = _canonicalize_legal_risk_text(normalized)
            if not normalized or not key:
                continue
            existing_location = legal_risk_index_by_key.get(key)
            if existing_location is None:
                legal_risk_index_by_key[key] = (section_name, len(deduped_legal_risks))
                deduped_legal_risks.append(normalized)
                continue

            existing_section, existing_index = existing_location
            existing_text = deduped_by_section.get(existing_section, {}).get("legal_risks", [])
            if existing_index >= len(existing_text):
                continue
            if _is_more_complete_legal_risk(normalized, existing_text[existing_index]):
                deduped_by_section[existing_section]["legal_risks"][existing_index] = normalized

        for takeaway in bucket["takeaways"]:
            _append_unique_bullet(deduped_takeaways, seen_takeaways_section, takeaway)

        for action in bucket["actions"]:
            _append_unique_bullet(deduped_actions, seen_actions_section, action)

        deduped_by_section[section_name] = {
            "legal_risks": deduped_legal_risks,
            "takeaways": deduped_takeaways,
            "actions": deduped_actions,
        }

    for section_name in section_order:
        legal_risks = deduped_by_section[section_name]["legal_risks"]
        takeaways = deduped_by_section[section_name]["takeaways"]
        actions = deduped_by_section[section_name]["actions"]

        lines.append(f"## {section_name}")
        lines.append("")
        lines.append("### Legal Risk Findings")
        if legal_risks:
            for risk in legal_risks:
                lines.append(f"- {risk}")
        else:
            lines.append("- No explicit obligation or risk clauses were identified in this section.")

        lines.append("")
        section_takeaways: list[str] = []
        for takeaway in takeaways:
            normalized = _normalize_bullet_text(takeaway)
            if not normalized:
                continue
            if any(_are_near_duplicate_bullets(existing, normalized) for existing in section_takeaways):
                continue
            if _is_reference_assets_boilerplate(normalized):
                continue
            section_takeaways.append(normalized)
        if section_takeaways:
            lines.append("### Strategic Takeaways")
            for takeaway in section_takeaways:
                lines.append(f"- {takeaway}")

        lines.append("")
        section_actions: list[str] = []
        for action in actions:
            normalized = _normalize_bullet_text(action)
            if not normalized:
                continue
            if any(_are_near_duplicate_bullets(existing, normalized) for existing in section_actions):
                continue
            section_actions.append(normalized)
        if section_actions:
            lines.append("### Recommended Next Actions")
            for action in section_actions:
                lines.append(f"- {action}")

        lines.append("")

    _append_reference_assets_section(lines, assets_context, asset_statuses)
    _append_reference_document_status_section(lines, asset_statuses)

    return "\n".join(lines).strip() + "\n"


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


def _strip_reference_sections(report: str) -> str:
    marker_positions = [
        idx
        for idx in (
            report.find("\n## Reference Assets"),
            report.find("\n## Reference Document Status"),
        )
        if idx != -1
    ]
    if not marker_positions:
        return report
    return report[: min(marker_positions)].strip()


def _contains_term(text: str, term: str) -> bool:
    pattern = r"\b" + re.escape(term.lower()) + r"\b"
    return re.search(pattern, text.lower()) is not None


def _contains_any_term(text: str, terms: tuple[str, ...]) -> bool:
    return any(_contains_term(text, term) for term in terms)


def _clean_party_candidate(candidate: str) -> str:
    cleaned = re.sub(r"\([^)]*\)", "", candidate)
    cleaned = cleaned.strip(" ,;:-\"'")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def _is_confident_party_name(candidate: str) -> bool:
    cleaned = _clean_party_candidate(candidate)
    if not cleaned:
        return False
    if len(cleaned.split()) > 10:
        return False
    if len(cleaned) > 90:
        return False
    lowered = cleaned.lower()
    if any(token in lowered for token in ("proprietary information", "terms and conditions", "agreement shall", "representatives")):
        return False
    return bool(re.search(r"[A-Za-z]", cleaned))


def _extract_parties_from_text(full_text: str) -> str:
    between_patterns = (
        r"\bbetween\s+(.{2,120}?)\s+and\s+(.{2,120}?)(?:,|\.|\sas\sof\b|\sdated\b|\sfor\sthe\spurpose\b)",
        r"\bby\s+and\s+between\s+(.{2,120}?)\s+and\s+(.{2,120}?)(?:,|\.|\sas\sof\b|\sdated\b)",
    )
    for pattern in between_patterns:
        match = re.search(pattern, full_text, flags=re.IGNORECASE)
        if not match:
            continue
        first = _clean_party_candidate(match.group(1))
        second = _clean_party_candidate(match.group(2))
        if _is_confident_party_name(first) and _is_confident_party_name(second):
            return f"{first} and {second}"

    signature_match = re.search(
        r"(?:IN WITNESS WHEREOF|By:)\s+(.{2,80}?)\s+(?:By:|Name:)\s+(.{2,80}?)(?:\s+Title:\s+.{2,80})?",
        full_text,
        flags=re.IGNORECASE,
    )
    if signature_match:
        entity = _clean_party_candidate(signature_match.group(1))
        signatory = _clean_party_candidate(signature_match.group(2))
        if _is_confident_party_name(entity) and _is_confident_party_name(signatory):
            return f"{entity} (signatory: {signatory})"

    return "See contract preamble"


def _build_contract_description(contract_type: str, analysis_report: str) -> list[str]:
    text = _strip_reference_sections(analysis_report)
    lowered = text.lower()

    if contract_type != "Non-disclosure agreement":
        return [
            "This agreement defines the parties' core rights, obligations, and enforcement mechanics for the stated commercial relationship.",
            "Key sections should be reviewed against internal standards before execution.",
        ]

    if _contains_any_term(lowered, ("mutual non-disclosure", "mutual nondisclosure", "each party shall")):
        nda_type = "This appears to be a mutual NDA with obligations on both sides."
    elif _contains_any_term(lowered, ("disclosing party", "receiving party")):
        nda_type = "This appears to be a one-way NDA with primary restrictions on the receiving party."
    else:
        nda_type = "This NDA's directionality is not explicit in the extracted text."

    purpose = "Purpose of disclosure is not clearly stated in extracted text."
    purpose_match = re.search(
        r"(?:for the purpose of|to evaluate|in connection with)\s+(.{8,180}?)(?:\.|;)",
        text,
        flags=re.IGNORECASE,
    )
    if purpose_match:
        purpose_text = _normalize_bullet_text(purpose_match.group(1))
        purpose = f"Stated purpose: {purpose_text}."

    term = "Confidentiality period is not clearly stated."
    term_match = re.search(
        r"(?:for a period of\s+[^.;]{3,80}|terminate on the\s+[^.;]{3,80}|survive[^.;]{0,80})",
        text,
        flags=re.IGNORECASE,
    )
    if term_match:
        term = f"Confidentiality duration signal: {_normalize_bullet_text(term_match.group(0))}."

    notable_items: list[str] = []
    if _contains_any_term(lowered, ("standstill",)):
        notable_items.append("standstill")
    if _contains_any_term(lowered, ("non-solicitation", "no solicitation", "no-solicitation")):
        notable_items.append("non-solicitation")
    if _contains_any_term(lowered, ("injunctive", "equitable relief", "immediate injunction")):
        notable_items.append("injunctive relief")
    notable = "Notable provisions: none clearly distinguished from a baseline template."
    if notable_items:
        notable = "Notable provisions: " + ", ".join(notable_items) + "."

    return [nda_type, purpose, term, notable]


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
    core_analysis = _strip_reference_sections(analysis_report)
    full_text = f"{core_analysis}\n{issues_report}"
    sentences = _extract_sentences(full_text)
    score_rows: list[dict[str, str]] = []

    for category, primary_terms, elevated_terms in SCORECARD_CATEGORIES:
        matching_sentences = [
            sentence
            for sentence in sentences
            if _contains_any_term(sentence, primary_terms)
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
            if _contains_any_term(sentence, elevated_terms)
        )
        protective_terms = CATEGORY_PROTECTIVE_TERMS.get(category, ())
        protective_hits = sum(1 for sentence in matching_sentences if _contains_any_term(sentence, protective_terms))
        mutual_hits = sum(1 for sentence in matching_sentences if _contains_any_term(sentence, MUTUAL_PROTECTIVE_TERMS))
        one_sided_hits = sum(1 for sentence in matching_sentences if _contains_any_term(sentence, ONE_SIDED_TERMS))
        gap_hits = sum(1 for sentence in matching_sentences if _contains_any_term(sentence, GAP_TERMS))

        if elevated_hits >= 2 or (elevated_hits >= 1 and one_sided_hits >= 1):
            risk = "HIGH"
        elif gap_hits >= 1 and elevated_hits == 0:
            risk = "MEDIUM"
        elif elevated_hits >= 1:
            risk = "MEDIUM"
        elif protective_hits >= 1 or mutual_hits >= 1:
            risk = "LOW"
        else:
            risk = "MEDIUM"

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

        if risk == "LOW":
            rationale = f"Detected clause language appears standard or mutual; sample: {rationale_clean}"
        elif gap_hits >= 1 and elevated_hits == 0:
            rationale = f"Detected category language includes a protection gap or omission signal; sample: {rationale_clean}"
        else:
            rationale = f"Detected clause language indicates {risk.lower()} exposure; sample: {rationale_clean}"

        score_rows.append(
            {
                "category": category,
                "risk": risk,
                "confidence": confidence,
                "rationale": rationale,
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
    core_text = _strip_reference_sections(analysis_report)
    full_text = re.sub(r"\s+", " ", core_text)
    lowered = full_text.lower()

    contract_type = "Commercial agreement"
    if any(term in lowered for term in ("non-disclosure", "nondisclosure", "confidentiality")):
        contract_type = "Non-disclosure agreement"
    elif "service" in lowered:
        contract_type = "Services agreement"
    elif "purchase" in lowered:
        contract_type = "Purchase agreement"

    parties = _extract_parties_from_text(full_text)

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
    contract_description = _build_contract_description(contract_type, analysis_report)
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
    for row in score_rows:
        if len(actions) >= 5:
            break
        if row["risk"] == "MEDIUM" and "gap" in row["rationale"].lower():
            actions.append(f"Address {row['category'].lower()} protection gap before approval.")
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
        *contract_description,
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
    asset_statuses: list[dict[str, str]] | None = None,
) -> dict:
    chunks = chunk_markdown(markdown, config.chunk_size_chars, config.overlap_chars)
    agents = [ExtractorAgent(), ReviewerAgent(), AnalystAgent(), LegalRiskAgent(), SynthesizerAgent()]

    issues_lines = [f"# Contract Issues Summary: {report_title}", ""]
    statuses = asset_statuses or []
    section_buckets: dict[str, dict[str, list[str]]] = {}
    section_order: list[str] = []
    chunk_diagnostics: list[dict[str, str]] = []
    synthesized_sections: list[str] = []
    current_section: str | None = None

    def ensure_section(name: str) -> dict[str, list[str]]:
        if name not in section_buckets:
            section_buckets[name] = {
                "legal_risks": [],
                "takeaways": [],
                "actions": [],
            }
            section_order.append(name)
        return section_buckets[name]

    for i, chunk in enumerate(chunks, start=1):
        per_agent: dict[str, str] = {}
        for agent in agents:
            result = agent.run(chunk, assets_context=assets_context)
            per_agent[result.agent_name] = result.content
            if result.agent_name == "legal-risk":
                issues_lines.append(f"## Chunk {i}")
                issues_lines.append(result.content)
                issues_lines.append("")

        extractor_output = _filter_pipeline_stage_lines(per_agent.get("extractor", ""))
        heading_candidate = _find_heading_candidate(extractor_output) or _find_heading_candidate(chunk)
        if heading_candidate:
            current_section = heading_candidate
            section_name = heading_candidate
        elif current_section is not None:
            section_name = current_section
        elif i == 1:
            section_name = DEFAULT_FIRST_SECTION_HEADING
            current_section = section_name
        else:
            topic_source = "\n".join(
                [
                    chunk,
                    per_agent.get("legal-risk", ""),
                    per_agent.get("synthesizer", ""),
                ]
            )
            fallback_topic = _topic_from_legal_risk(topic_source)
            if fallback_topic and fallback_topic in section_buckets:
                section_name = fallback_topic
            elif section_order:
                section_name = section_order[-1]
            else:
                section_name = DEFAULT_FIRST_SECTION_HEADING
                current_section = section_name

        bucket = ensure_section(section_name)

        legal_risk_bullets = _extract_legal_risk_bullets(per_agent.get("legal-risk", ""))
        for bullet in legal_risk_bullets:
            if bullet not in bucket["legal_risks"]:
                bucket["legal_risks"].append(bullet)

        takeaways = _extract_synth_list(per_agent.get("synthesizer", ""), "Strategic takeaways")
        actions = _extract_synth_list(per_agent.get("synthesizer", ""), "Recommended next actions")
        bucket["takeaways"].extend(takeaways)
        bucket["actions"].extend(actions)
        if per_agent.get("synthesizer", "").strip():
            synthesized_sections.append(per_agent["synthesizer"])

        chunk_diagnostics.append(
            {
                "chunk_index": str(i),
                "section_name": section_name,
                "extractor": extractor_output,
                "reviewer": per_agent.get("reviewer", ""),
                "analyst": per_agent.get("analyst", ""),
                "synthesizer": per_agent.get("synthesizer", ""),
            }
        )

    report = _build_sectioned_analysis_report(
        report_title=report_title,
        chunk_count=len(chunks),
        section_order=section_order,
        section_buckets=section_buckets,
        assets_context=assets_context,
        asset_statuses=statuses,
    )
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
        "chunk_diagnostics_report": _build_diagnostics_report(report_title, chunk_diagnostics),
        "section_count": len(section_order),
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
    audit_run_dir = AUDIT_ROOT_DIR / _make_audit_run_id()
    audit_run_dir.mkdir(parents=True, exist_ok=True)
    diagnostics_name = f"{Path(pdf_path.name).stem}-chunk-diagnostics.md"
    diagnostics_path = audit_run_dir / diagnostics_name
    final_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(analysis["report"], encoding="utf-8")
    issues_path.write_text(analysis["issues_report"], encoding="utf-8")
    scorecard_path.write_text(analysis["scorecard"], encoding="utf-8")
    executive_summary_path.write_text(analysis["executive_summary"], encoding="utf-8")
    final_path.write_text(analysis["final_markdown"], encoding="utf-8")
    diagnostics_path.write_text(analysis["chunk_diagnostics_report"], encoding="utf-8")

    return {
        "markdown_path": md_path,
        "report_path": report_path,
        "issues_path": issues_path,
        "scorecard_path": scorecard_path,
        "executive_summary_path": executive_summary_path,
        "final_path": final_path,
        "chunk_diagnostics_path": diagnostics_path,
        "section_count": analysis["section_count"],
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
    asset_statuses: list[dict[str, str]] = []
    if assets_dir is not None:
        assets_context, asset_statuses = build_assets_context_with_status(
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
        asset_statuses=asset_statuses,
    )
    report_path = cfg.output_dir / f"{markdown_path.stem}.analysis.md"
    issues_path = cfg.output_dir / f"{markdown_path.stem}.issues.md"
    scorecard_path = cfg.output_dir / f"{markdown_path.stem}.scorecard.md"
    executive_summary_path = cfg.output_dir / f"{markdown_path.stem}.executive-summary.md"
    final_path = _final_output_path(markdown_path.name)
    audit_run_dir = AUDIT_ROOT_DIR / _make_audit_run_id()
    audit_run_dir.mkdir(parents=True, exist_ok=True)
    diagnostics_name = f"{markdown_path.stem}-chunk-diagnostics.md"
    diagnostics_path = audit_run_dir / diagnostics_name
    final_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(analysis["report"], encoding="utf-8")
    issues_path.write_text(analysis["issues_report"], encoding="utf-8")
    scorecard_path.write_text(analysis["scorecard"], encoding="utf-8")
    executive_summary_path.write_text(analysis["executive_summary"], encoding="utf-8")
    final_path.write_text(analysis["final_markdown"], encoding="utf-8")
    diagnostics_path.write_text(analysis["chunk_diagnostics_report"], encoding="utf-8")

    return {
        "report_path": report_path,
        "issues_path": issues_path,
        "scorecard_path": scorecard_path,
        "executive_summary_path": executive_summary_path,
        "final_path": final_path,
        "chunk_diagnostics_path": diagnostics_path,
        "section_count": analysis["section_count"],
        "chunk_count": analysis["chunk_count"],
        "assets_context_included": bool(assets_context.strip()),
        "asset_warnings": [entry["warning"] for entry in asset_statuses if "warning" in entry],
        "asset_statuses": asset_statuses,
    }
