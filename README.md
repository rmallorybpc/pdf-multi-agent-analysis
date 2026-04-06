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
- `workflow_run` when `convert-rfp-pdf-to-markdown` completes successfully
- `workflow_dispatch` with inputs:
	- `file_path`
	- `uploads_glob`

Target selection:

- `push`: processes all source markdown files under `rfp-markdown/` (excluding `generated/` and `audit/`).
- `workflow_dispatch`: processes `file_path`, or `uploads_glob`, or all source markdown files if neither input is set.

Stages:

1. Stage A: critique/revision agent
2. Stage B: executive refinement agent
3. Stage C: final markdown formatting agent
4. Stage D: GitHub Models cleanup pass (Claude Sonnet 4.5), with safe fallback to Stage C output

No initial primary analysis stage is included.

Execution behavior:

- Stages A/B/C always run as local deterministic transforms.
- Stage D uses GitHub Models with `anthropic/claude-sonnet-4.5` by default.
- If model access is unavailable (permissions/token/endpoint), Stage D falls back to Stage C output and records fallback status in audit artifacts.
- If Claude marks content as incomprehensible, the workflow restarts from Stage A with capped retries and then fails clearly if retries are exhausted.
- Full routing and artifact logic runs on every execution.

Outputs:

- Final markdown: `rfp-markdown/generated/<stem>-final.md`
- Per-stage audit artifacts under `rfp-markdown/audit/<run-id>/`
	- request payload
	- raw response
	- stage markdown output
	- stage status (including Claude fallback/success status)
	- run summary

GitHub Models requirements:

- Workflow permissions include `models: read`.
- Uses `github.token` (no Anthropic API key required).
- Optional environment toggles in workflow job:
	- `ENABLE_GITHUB_MODELS_CLAUDE` (default `"true"`)
	- `GITHUB_MODELS_CLAUDE_MODEL` (default `anthropic/claude-sonnet-4.5`)
	- `GITHUB_MODELS_ENDPOINT` (default `https://models.github.ai/inference/chat/completions`)
	- `MAX_REFINEMENT_RETRIES` (default `"1"`; total attempts = retries + 1)

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

## Local Python analysis of existing markdown + assets

If you already have a converted markdown file, run the Python CLI directly against it and include reference files from `assets/`:

```bash
python -m pdf_multi_agent_analysis.cli analyze-markdown \
	"rfp-markdown/generated/MUTUAL NON-DISCLOSURE AGREEMENT-final.md" \
	--assets-dir assets \
	--out-dir rfp-markdown/generated
```

This writes:

- analysis report: `rfp-markdown/generated/MUTUAL NON-DISCLOSURE AGREEMENT-final.analysis.md`
- issues summary: `rfp-markdown/generated/MUTUAL NON-DISCLOSURE AGREEMENT-final.issues.md`

Behavior:

- The markdown is chunked and processed by extractor/reviewer/analyst/synthesizer agents.
- The pipeline includes a legal-risk stage and writes a contract-focused issues summary.
- Asset references from `assets/` are preprocessed into text context and injected into agent runs.
- Supported asset extraction: text files (`.md`, `.txt`, `.json`, `.yaml`, `.yml`), `.pdf` (via `pypdf` with OCR fallback enabled by default), and `.docx` (basic XML extraction).

### Agent Steps (Python markdown analysis)

Agent metadata for this analysis flow:

- Agent runtime: local Python pipeline agents (`extractor`, `reviewer`, `analyst`, `legal-risk`, `synthesizer`)
- Copilot assistant name: GitHub Copilot
- Copilot model label: GPT-5.3-Codex

For each markdown chunk, the pipeline runs agents in this exact order:

1. `extractor`
	- Step 1 role: takes the chunk and extracts the first key lines as a focused content snapshot.
	- If `assets/` context is present, it also reports overlap terms between the chunk and reference assets.
2. `reviewer`
	- Step 2 role: performs structural checks such as TODO markers and short/incomplete chunk warnings.
	- If `assets/` context is present, it reports how many alignment terms were found.
3. `analyst`
	- Step 3 role: computes chunk-level metrics (word count and unique terms).
	- If `assets/` context is present, it also reports shared term counts against assets.
4. `legal-risk`
	- Step 4 role: identifies contractual obligation/risk language (for example: shall, must, termination, liability, indemnity, jurisdiction).
	- This is the stage that feeds the contract issues output file: `*-final.issues.md` (or `<name>.issues.md`).
5. `synthesizer`
	- Step 5 role: generates a concise summary preview of the chunk.
	- If `assets/` context is present, it appends detected reference anchors.

Final outputs after all chunks are processed:

- Full analysis report: `<name>.analysis.md`
- Contract issues summary (from `legal-risk` results): `<name>.issues.md`

Enable OCR fallback for scanned/image PDFs in assets (requires `pdftoppm` and `tesseract`):

```bash
python -m pdf_multi_agent_analysis.cli analyze-markdown \
	"rfp-markdown/generated/MUTUAL NON-DISCLOSURE AGREEMENT-final.md" \
	--assets-dir assets \
	--out-dir rfp-markdown/generated \
	--asset-ocr-fallback \
	--asset-ocr-max-pages 8
```

Disable OCR fallback when needed:

```bash
python -m pdf_multi_agent_analysis.cli analyze-markdown \
	"rfp-markdown/generated/MUTUAL NON-DISCLOSURE AGREEMENT-final.md" \
	--assets-dir assets \
	--out-dir rfp-markdown/generated \
	--no-asset-ocr-fallback
```
