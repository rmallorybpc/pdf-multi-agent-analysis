from dataclasses import dataclass


@dataclass
class AgentResult:
    agent_name: str
    content: str


class BaseAgent:
    name = "base"

    def run(self, markdown_chunk: str) -> AgentResult:
        raise NotImplementedError


class ExtractorAgent(BaseAgent):
    name = "extractor"

    def run(self, markdown_chunk: str) -> AgentResult:
        lines = [ln.strip() for ln in markdown_chunk.splitlines() if ln.strip()]
        key_lines = lines[:5]
        return AgentResult(self.name, "\n".join(key_lines) if key_lines else "No content")


class ReviewerAgent(BaseAgent):
    name = "reviewer"

    def run(self, markdown_chunk: str) -> AgentResult:
        checks = []
        if "TODO" in markdown_chunk:
            checks.append("Found TODO markers needing resolution.")
        if len(markdown_chunk) < 200:
            checks.append("Chunk is short; context may be incomplete.")
        if not checks:
            checks.append("No obvious structural issues detected.")
        return AgentResult(self.name, " ".join(checks))


class AnalystAgent(BaseAgent):
    name = "analyst"

    def run(self, markdown_chunk: str) -> AgentResult:
        words = [w for w in markdown_chunk.replace("\n", " ").split(" ") if w]
        unique = len(set(w.lower() for w in words))
        return AgentResult(
            self.name,
            f"Word count: {len(words)}; unique terms: {unique}.",
        )


class SynthesizerAgent(BaseAgent):
    name = "synthesizer"

    def run(self, markdown_chunk: str) -> AgentResult:
        preview = markdown_chunk[:280].replace("\n", " ").strip()
        if not preview:
            preview = "No summary available"
        return AgentResult(self.name, f"Summary preview: {preview}")
