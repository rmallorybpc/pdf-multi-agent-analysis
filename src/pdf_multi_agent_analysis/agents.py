from dataclasses import dataclass
import re


@dataclass
class AgentResult:
    agent_name: str
    content: str


class BaseAgent:
    name = "base"

    def run(self, markdown_chunk: str, assets_context: str = "") -> AgentResult:
        raise NotImplementedError


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text.lower()))


def _summary_preview(text: str, max_chars: int = 500) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if not compact:
        return "No summary available"
    if len(compact) <= max_chars:
        return compact

    window = compact[:max_chars]
    cut_points = [window.rfind(sep) for sep in (". ", "? ", "! ", "; ")]
    cut = max(cut_points)
    if cut >= 80:
        return window[: cut + 1].strip()

    word_cut = window.rfind(" ")
    if word_cut >= 80:
        return window[:word_cut].strip() + "..."
    return window.strip() + "..."


def _find_clause_signals(text: str) -> dict[str, bool]:
    lowered = text.lower()
    return {
        "confidentiality_scope": any(term in lowered for term in ("confidential", "proprietary", "trade secret")),
        "use_restriction": any(term in lowered for term in ("use", "purpose", "permitted")),
        "term_and_termination": any(term in lowered for term in ("term", "terminate", "termination", "survive")),
        "liability_or_indemnity": any(term in lowered for term in ("liability", "liable", "indemn", "damages")),
        "injunctive_relief": "injunct" in lowered,
        "legal_forum": any(term in lowered for term in ("governed by", "jurisdiction", "venue", "arbitration")),
        "public_disclosure": any(term in lowered for term in ("public announcement", "disclose", "press release")),
    }


def _detect_section_heading(text: str) -> str | None:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for line in lines:
        md_match = re.match(r"^#{1,6}\s+(.+)$", line)
        if md_match:
            return md_match.group(1).strip()

        numbered_match = re.match(r"^(\d+(?:\.\d+)*)\s*[.)-]?\s+([A-Z][^\n]{2,140})$", line)
        if numbered_match:
            return f"{numbered_match.group(1)} {numbered_match.group(2).strip()}"

        section_match = re.match(r"^(Section\s+[A-Za-z0-9.\-]+\s*[:.-]?\s*[^\n]{2,160})$", line, flags=re.IGNORECASE)
        if section_match:
            return section_match.group(1).strip()

        article_match = re.match(r"^(Article\s+[A-Za-z0-9.\-]+\s*[:.-]?\s*[^\n]{2,160})$", line, flags=re.IGNORECASE)
        if article_match:
            return article_match.group(1).strip()

    return None


def _strategic_takeaways(signals: dict[str, bool], assets_context: str) -> list[str]:
    takeaways: list[str] = []

    if signals["confidentiality_scope"] and signals["use_restriction"]:
        takeaways.append("Confidentiality duties appear linked to use limitations, so operational handling controls should be aligned with stated purpose restrictions.")
    elif signals["confidentiality_scope"]:
        takeaways.append("Confidentiality obligations are present, but scope and carve-outs should be tightened to reduce interpretation risk.")

    if signals["term_and_termination"]:
        takeaways.append("Term and survival language can shift long-tail exposure; negotiation should confirm exactly which obligations survive and for how long.")

    if signals["liability_or_indemnity"] or signals["injunctive_relief"]:
        takeaways.append("Remedies appear asymmetrical or high-impact, creating leverage points around liability caps, indemnity triggers, and equitable relief scope.")

    if signals["legal_forum"]:
        takeaways.append("Forum and governing-law provisions may create practical enforcement costs, so venue should match expected dispute profile.")

    if signals["public_disclosure"]:
        takeaways.append("Public disclosure language may conflict with transaction secrecy goals; align announcement rights with communications governance.")

    if assets_context.strip():
        takeaways.append("Reference assets are available, enabling a redline strategy anchored to internal standards rather than ad hoc clause-by-clause edits.")

    if not takeaways:
        takeaways.append("This chunk is operationally neutral; prioritize cross-chunk synthesis before setting negotiation posture.")

    return takeaways[:4]


def _strategic_next_steps(signals: dict[str, bool], has_assets: bool) -> list[str]:
    actions = [
        "Classify this chunk as accept, clarify, or negotiate based on business criticality.",
    ]

    if signals["liability_or_indemnity"] or signals["injunctive_relief"]:
        actions.append("Prepare fallback drafting for remedies to control downside while preserving enforceability.")

    if signals["term_and_termination"]:
        actions.append("Validate survival period and termination mechanics against your retention and exit requirements.")

    if signals["public_disclosure"]:
        actions.append("Define approval workflow for announcements to avoid accidental disclosure during active deal activity.")

    if has_assets:
        actions.append("Map identified clauses to precedent language in assets and rank redlines by expected negotiation resistance.")

    return actions[:4]


class ExtractorAgent(BaseAgent):
    name = "extractor"

    def run(self, markdown_chunk: str, assets_context: str = "") -> AgentResult:
        lines = [ln.strip() for ln in markdown_chunk.splitlines() if ln.strip()]
        key_lines = lines[:5]
        content = "\n".join(key_lines) if key_lines else "No content"
        heading = _detect_section_heading(markdown_chunk)

        if heading:
            content += f"\n\nDetected section heading: {heading}"

        if assets_context.strip() and key_lines:
            overlap = sorted(_tokenize(" ".join(key_lines)) & _tokenize(assets_context))
            if overlap:
                content += "\n\nReference overlap terms: " + ", ".join(overlap[:12])
            else:
                content += "\n\nReference overlap terms: none detected"

        return AgentResult(self.name, content)


class ReviewerAgent(BaseAgent):
    name = "reviewer"

    def run(self, markdown_chunk: str, assets_context: str = "") -> AgentResult:
        checks = []
        if "TODO" in markdown_chunk:
            checks.append("Found TODO markers needing resolution.")
        if len(markdown_chunk) < 200:
            checks.append("Chunk is short; context may be incomplete.")
        if assets_context.strip():
            overlap_count = len(_tokenize(markdown_chunk) & _tokenize(assets_context))
            checks.append(f"Reference alignment terms detected: {overlap_count}.")
        if not checks:
            checks.append("No obvious structural issues detected.")
        return AgentResult(self.name, " ".join(checks))


class AnalystAgent(BaseAgent):
    name = "analyst"

    def run(self, markdown_chunk: str, assets_context: str = "") -> AgentResult:
        words = [w for w in markdown_chunk.replace("\n", " ").split(" ") if w]
        unique = len(set(w.lower() for w in words))
        if assets_context.strip():
            shared = len(_tokenize(markdown_chunk) & _tokenize(assets_context))
            ref_terms = len(_tokenize(assets_context))
            return AgentResult(
                self.name,
                f"Word count: {len(words)}; unique terms: {unique}; shared-with-assets: {shared}/{ref_terms}.",
            )
        return AgentResult(
            self.name,
            f"Word count: {len(words)}; unique terms: {unique}.",
        )


class LegalRiskAgent(BaseAgent):
    name = "legal-risk"

    _keyword_pattern = re.compile(
        r"\b(shall|must|will\s+not|terminate|termination|breach|liable|liability|"
        r"indemn|injunctive|governed\s+by|exclusive\s+jurisdiction|waive)\b",
        re.IGNORECASE,
    )

    def run(self, markdown_chunk: str, assets_context: str = "") -> AgentResult:
        sentences = [
            s.strip()
            for s in re.split(r"(?<=[.!?;])\s+|\n+", markdown_chunk)
            if s.strip()
        ]
        matches: list[str] = []
        seen: set[str] = set()

        for sentence in sentences:
            if not self._keyword_pattern.search(sentence):
                continue
            compact = re.sub(r"\s+", " ", sentence)
            key = compact.lower()
            if key in seen:
                continue
            seen.add(key)
            matches.append(f"- {compact}")
            if len(matches) >= 8:
                break

        if not matches:
            return AgentResult(self.name, "No explicit obligation or risk clauses detected in this chunk.")

        return AgentResult(
            self.name,
            "Potential obligations/risks:\n" + "\n".join(matches),
        )


class SynthesizerAgent(BaseAgent):
    name = "synthesizer"

    def run(self, markdown_chunk: str, assets_context: str = "") -> AgentResult:
        preview = _summary_preview(markdown_chunk)
        signals = _find_clause_signals(markdown_chunk)
        has_assets = bool(assets_context.strip())
        takeaways = _strategic_takeaways(signals, assets_context)
        next_steps = _strategic_next_steps(signals, has_assets)
        heading = _detect_section_heading(markdown_chunk)

        output_lines = ["Summary preview: " + preview]
        if heading:
            output_lines.extend(["", "Section heading candidate: " + heading])
        output_lines.extend(["", "Strategic takeaways:"])
        output_lines.extend(f"- {item}" for item in takeaways)
        output_lines.append("")
        output_lines.append("Recommended next actions:")
        output_lines.extend(f"- {item}" for item in next_steps)

        if not has_assets:
            output_lines.append("")
            output_lines.append("Reference anchors: none detected")
            return AgentResult(self.name, "\n".join(output_lines))

        ref_terms = sorted(_tokenize(markdown_chunk) & _tokenize(assets_context))
        output_lines.append("")
        if ref_terms:
            output_lines.append("Reference anchors: " + ", ".join(ref_terms[:10]))
        else:
            output_lines.append("Reference anchors: none detected")
        return AgentResult(self.name, "\n".join(output_lines))
