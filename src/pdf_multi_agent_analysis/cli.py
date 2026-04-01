import argparse
from pathlib import Path

from .config import PipelineConfig
from .converter import pdf_to_markdown
from .pipeline import run_pipeline


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

    cfg = PipelineConfig(
        output_dir=args.out_dir,
        chunk_size_chars=args.chunk_size,
        overlap_chars=args.overlap,
    )
    result = run_pipeline(args.pdf, cfg)
    print(f"Wrote markdown: {result['markdown_path']}")
    print(f"Wrote report: {result['report_path']}")
    print(f"Chunks analyzed: {result['chunk_count']}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
