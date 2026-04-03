from pathlib import Path

from .agents import AnalystAgent, ExtractorAgent, ReviewerAgent, SynthesizerAgent
from .assets_context import build_assets_context
from .chunking import chunk_markdown
from .config import PipelineConfig
from .converter import pdf_to_markdown


def _analyze_markdown(markdown: str, report_title: str, config: PipelineConfig, assets_context: str = "") -> dict:
    chunks = chunk_markdown(markdown, config.chunk_size_chars, config.overlap_chars)
    agents = [ExtractorAgent(), ReviewerAgent(), AnalystAgent(), SynthesizerAgent()]

    report_lines = [f"# Analysis Report: {report_title}", ""]
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

    report = "\n".join(report_lines).strip() + "\n"
    return {
        "report": report,
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
    report_path.write_text(analysis["report"], encoding="utf-8")

    return {
        "markdown_path": md_path,
        "report_path": report_path,
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
    if assets_dir is not None:
        assets_context = build_assets_context(assets_dir, max_chars_per_file=cfg.max_asset_chars_per_file)

    analysis = _analyze_markdown(markdown, markdown_path.name, cfg, assets_context=assets_context)
    report_path = cfg.output_dir / f"{markdown_path.stem}.analysis.md"
    report_path.write_text(analysis["report"], encoding="utf-8")

    return {
        "report_path": report_path,
        "chunk_count": analysis["chunk_count"],
        "assets_context_included": bool(assets_context.strip()),
    }
