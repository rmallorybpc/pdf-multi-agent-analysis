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


class ExtractorAgent(BaseAgent):
    name = "extractor"

    def run(self, markdown_chunk: str, assets_context: str = "") -> AgentResult:
        lines = [ln.strip() for ln in markdown_chunk.splitlines() if ln.strip()]
        key_lines = lines[:5]
        content = "\n".join(key_lines) if key_lines else "No content"

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
        if not assets_context.strip():
            return AgentResult(self.name, f"Summary preview: {preview}")

        ref_terms = sorted(_tokenize(markdown_chunk) & _tokenize(assets_context))
        if ref_terms:
            return AgentResult(
                self.name,
                f"Summary preview: {preview}\n\nReference anchors: {', '.join(ref_terms[:10])}",
            )
        return AgentResult(self.name, f"Summary preview: {preview}\n\nReference anchors: none detected")
