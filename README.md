# pdf-multi-agent-analysis

Node-first document pipeline for:

1. PDF to markdown conversion with OCR fallback.
2. Multi-agent markdown refinement in GitHub Actions.

Important scope: there is no initial OpenAI-trained primary analysis stage. The refinement workflow starts at critique.

## Folder contracts

- Input PDFs: `rfp-pdfs/`
- Converted markdown: `rfp-markdown/`
- Final generated outputs: `rfp-markdown/generated/`
- Audit artifacts per run: `rfp-markdown/audit/`
- Optional analysis references: `assets/`

## Local setup

```bash
npm ci
```

## PDF conversion

Conversion script: `convert-pdf-to-markdown.js`

Runs recursively under `rfp-pdfs/` by default and mirrors relative paths into `rfp-markdown/`.

```bash
npm run convert:pdf
```

Convert one file or directory:

```bash
node convert-pdf-to-markdown.js rfp-pdfs/path/to/file.pdf
node convert-pdf-to-markdown.js rfp-pdfs/some-subfolder
```

Options:

- `--ocr-fallback`: enable OCR fallback using `pdftoppm` + `tesseract`
- `--min-text-chars <number>`: threshold for weak native extraction (default `400`)

Example:

```bash
node convert-pdf-to-markdown.js --ocr-fallback --min-text-chars 600
```

Each output markdown contains YAML frontmatter metadata:

- `title`
- `source_path`
- `page_count`
- `extraction_method`

Idempotency behavior: files are only rewritten if content changed.

## OCR prerequisites

Local OCR fallback requires:

- `pdftoppm` (from `poppler-utils`)
- `tesseract`

Install on Ubuntu:

```bash
sudo apt-get update
sudo apt-get install -y poppler-utils tesseract-ocr
```

## Workflow 1: PDF conversion automation

File: `.github/workflows/convert-rfp-pdf-to-markdown.yml`

Triggers:

- `push` on `rfp-pdfs/**/*.pdf`
- `workflow_dispatch` with optional `pdf_path`

Behavior:

- Detects added/modified/renamed PDFs and converts only affected files.
- Detects deleted PDFs and auto-removes mirrored markdown in `rfp-markdown/`.
- Commits only if `rfp-markdown/` changed.
- Uses actor/path guards to avoid commit-loop behavior.

## Workflow 2: Hybrid multimodel refinement

File: `.github/workflows/local-multistage-refinement.yml`

Triggers:

- `push` on `rfp-markdown/**/*.md` (excluding generated/audit outputs)
- `workflow_dispatch` with inputs:
	- `file_path`
	- `uploads_glob`

Stages:

1. Stage A: critique/revision agent
2. Stage B: executive refinement agent
3. Stage C: final markdown formatting agent

No initial primary analysis stage is included.

Execution behavior:

- No external model calls.
- Workflow always runs local deterministic stage transforms.
- Full routing and artifact logic runs on every execution.

Outputs:

- Final markdown: `rfp-markdown/generated/<stem>-final.md`
- Per-stage audit artifacts under `rfp-markdown/audit/<run-id>/`
	- request payload
	- raw response
	- stage markdown output
	- run summary

Commit behavior:

- Workflow commits generated outputs only when changed.
- If automated push is blocked by permissions/protection, workflow writes manual commit instructions artifact.

Reference assets behavior:

- If `assets/` exists, workflow appends it to run context.
- Assets are preprocessed into audit cache files under `rfp-markdown/audit/<run-id>/assets-cache/`.
- Text-like files (`.md`, `.txt`, `.json`, `.yaml`, `.yml`) are copied into cache text artifacts.
- PDF files are text-extracted into cache artifacts when `pdftotext` is available.
- DOCX files are extracted when `docx2txt` is available; otherwise a placeholder note is written.
- Binary/unsupported files are represented with placeholder notes so references remain traceable.

## Reliability and safety controls

- Strict shell mode (`set -euo pipefail`) in workflow shell steps.
- Explicit stage sequencing and artifact persistence.
- Path filtering and actor guards for safe CI behavior.
- Idempotent conversion writes.

## Acceptance checklist

- `npm run convert:pdf` converts all PDFs under `rfp-pdfs/` into mirrored markdown under `rfp-markdown/`.
- OCR fallback works when native extraction is weak and OCR tools are installed.
- Deleting a PDF removes corresponding markdown during conversion workflow runs.
- Multi-agent workflow starts at critique stage and excludes initial primary analysis.
- Refinement workflow executes local deterministic stage transforms and writes audit artifacts.
- Final outputs are written to `rfp-markdown/generated/*-final.md`.
- Workflows commit only when generated/converted files changed.
- Audit artifacts and run summary are uploaded for traceability.

## Legacy notes

The earlier Python scaffold remains in the repo as legacy reference, but Node + GitHub Actions is the primary implementation path.
