from pathlib import Path

from .agents import AnalystAgent, ExtractorAgent, ReviewerAgent, SynthesizerAgent
from .chunking import chunk_markdown
from .config import PipelineConfig
from .converter import pdf_to_markdown


def run_pipeline(pdf_path: Path, config: PipelineConfig | None = None) -> dict:
    """Run PDF->Markdown conversion and multi-agent analysis."""
    cfg = config or PipelineConfig()
    cfg.output_dir.mkdir(parents=True, exist_ok=True)

    markdown = pdf_to_markdown(pdf_path)
    md_path = cfg.output_dir / f"{pdf_path.stem}.md"
    md_path.write_text(markdown, encoding="utf-8")

    chunks = chunk_markdown(markdown, cfg.chunk_size_chars, cfg.overlap_chars)
    agents = [ExtractorAgent(), ReviewerAgent(), AnalystAgent(), SynthesizerAgent()]

    report_lines = [f"# Analysis Report: {pdf_path.name}", ""]

    for i, chunk in enumerate(chunks, start=1):
        report_lines.append(f"## Chunk {i}")
        for agent in agents:
            result = agent.run(chunk)
            report_lines.append(f"### {result.agent_name}")
            report_lines.append(result.content)
            report_lines.append("")

    report = "\n".join(report_lines).strip() + "\n"
    report_path = cfg.output_dir / f"{pdf_path.stem}.analysis.md"
    report_path.write_text(report, encoding="utf-8")

    return {
        "markdown_path": md_path,
        "report_path": report_path,
        "chunk_count": len(chunks),
    }
