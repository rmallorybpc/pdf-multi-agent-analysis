import argparse
from pathlib import Path

from .config import PipelineConfig
from .converter import pdf_to_markdown
from .pipeline import run_markdown_analysis, run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pdf-multi-agent-analysis",
        description="Convert PDF to markdown and run multi-agent analysis.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    convert = sub.add_parser("convert", help="Convert a PDF file to markdown")
    convert.add_argument("pdf", type=Path)
    convert.add_argument("--out", type=Path, default=Path("output/converted.md"))

    run = sub.add_parser("run", help="Run full conversion + multi-agent analysis")
    run.add_argument("pdf", type=Path)
    run.add_argument("--out-dir", type=Path, default=Path("output"))
    run.add_argument("--chunk-size", type=int, default=1800)
    run.add_argument("--overlap", type=int, default=200)

    analyze_md = sub.add_parser(
        "analyze-markdown",
        help="Run multi-agent analysis for an existing markdown file",
    )
    analyze_md.add_argument("markdown", type=Path)
    analyze_md.add_argument("--assets-dir", type=Path, default=Path("assets"))
    analyze_md.add_argument("--out-dir", type=Path, default=Path("output"))
    analyze_md.add_argument("--chunk-size", type=int, default=1800)
    analyze_md.add_argument("--overlap", type=int, default=200)
    analyze_md.add_argument(
        "--asset-ocr-fallback",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable OCR fallback for PDF files in assets (requires pdftoppm and tesseract)",
    )
    analyze_md.add_argument(
        "--asset-ocr-max-pages",
        type=int,
        default=6,
        help="Maximum number of pages to OCR per PDF asset",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "convert":
        markdown = pdf_to_markdown(args.pdf)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(markdown, encoding="utf-8")
        print(f"Wrote markdown: {args.out}")
        return 0

    if args.command == "analyze-markdown":
        cfg = PipelineConfig(
            output_dir=args.out_dir,
            chunk_size_chars=args.chunk_size,
            overlap_chars=args.overlap,
            asset_pdf_ocr_fallback=args.asset_ocr_fallback,
            asset_pdf_ocr_max_pages=args.asset_ocr_max_pages,
        )
        result = run_markdown_analysis(args.markdown, config=cfg, assets_dir=args.assets_dir)
        print(f"Wrote report: {result['report_path']}")
        print(f"Wrote issues summary: {result['issues_path']}")
        print(f"Wrote risk scorecard: {result['scorecard_path']}")
        print(f"Wrote executive summary: {result['executive_summary_path']}")
        print(f"Chunks analyzed: {result['chunk_count']}")
        print(f"Assets context included: {result['assets_context_included']}")
        for warning in result.get("asset_warnings", []):
            print(f"WARNING: {warning}")
        return 0

    cfg = PipelineConfig(
        output_dir=args.out_dir,
        chunk_size_chars=args.chunk_size,
        overlap_chars=args.overlap,
    )
    result = run_pipeline(args.pdf, cfg)
    print(f"Wrote markdown: {result['markdown_path']}")
    print(f"Wrote report: {result['report_path']}")
    print(f"Wrote issues summary: {result['issues_path']}")
    print(f"Wrote risk scorecard: {result['scorecard_path']}")
    print(f"Wrote executive summary: {result['executive_summary_path']}")
    print(f"Chunks analyzed: {result['chunk_count']}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
