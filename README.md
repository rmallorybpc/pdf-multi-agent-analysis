# PDF Multi-Agent Analysis

AI-powered contract analysis pipeline that converts PDFs into structured intelligence for contract administrators and business leaders.

Upload a contract PDF. The pipeline converts it to markdown, runs a multi-agent analysis, and produces five ready-to-use output documents — from detailed clause findings to a one-page executive brief.

---

## What you get

For every contract processed, the pipeline produces five output files:

| Output File | Purpose | Audience |
|---|---|---|
| `*-final.md` | Refined, clean markdown version of the contract | Reference |
| `*-final.analysis.md` | Clause-by-clause findings organized by contract section, with legal risk flags, strategic takeaways, and recommended actions | Contract admin |
| `*-final.issues.md` | Consolidated list of contractual obligations and risk clauses | Legal review |
| `*-final.scorecard.md` | Risk rating table (LOW / MEDIUM / HIGH / NOT FOUND) across six clause categories with confidence indicators | Leadership |
| `*-final.executive-summary.md` | One-page brief with plain-language risk assessment and recommended actions before signing | Business leader |

Each refinement run also snapshots those generated files into `linkedin-series-archive/` using a timestamped run folder so prior LinkedIn episode artifacts remain immutable.

**See a sample output:** [SS&C Services Agreement — Executive Summary](rfp-markdown/generated/SS%26C%20Services%20Agreement%20from%202024-final.executive-summary.md)

## Transparency Portal (GitHub Pages)

This repository includes a static transparency portal built with MkDocs and Material theme.
It publishes a decision-first view of generated outputs (executive summary and scorecard), plus immutable run history for transparency.

- Site source: `docs/`
- Site generator: `scripts/build_site_from_manifests.py`
- Build config: `mkdocs.yml`
- Deploy workflow: `.github/workflows/build-and-publish-site.yml`

### Local preview

```bash
python -m pip install -r requirements-dev.txt
python scripts/build_site_from_manifests.py
mkdocs serve
```

### Automated deployment

The Pages workflow runs on successful completion of `local-multistage-refinement`, on manual dispatch, and daily on schedule.

---

## About this project

This repo supports the **PDF → Publish: Multi-Agent Document Intelligence** LinkedIn series, a six-episode series demonstrating AI-powered document analysis across real-world contract and document types:

- Episode 1 — NDA (Legal): Clause risk, ambiguity, standstill, confidentiality
- Episode 2 — Privacy Policy (Compliance): Completeness, vague language, regulatory alignment
- Episode 3 — Employee Handbook (HR): Conflicting policies, outdated language, structural drift
- Episode 4 — Marketing One-Pager (Marketing): Tone alignment, clarity, CTA strength
- Episode 5 — Vendor Security Questionnaire (Security): Structured responses, control mapping, gaps
- Episode 6 — Technical Specification (Engineering): Cross-section consistency, requirement drift, clarity

---

## How it works

The pipeline runs two automated GitHub Actions workflows in sequence:

**Workflow 1 — PDF conversion**

Detects new or changed PDFs in `rfp-pdfs/`, converts them to markdown using native extraction with OCR fallback for scanned documents, and writes output to
`rfp-markdown/`.

**Workflow 2 — Multi-agent refinement and analysis**
Runs the converted markdown through a four-stage agent pipeline:

- Stage A: Critique and revision
- Stage B: Executive refinement
- Stage C: Final markdown formatting
- Stage D: Claude Sonnet cleanup pass via GitHub Models (falls back to Stage C if
  model access is unavailable)

After refinement, a Python analysis pipeline runs the contract through five specialized agents (extractor, reviewer, analyst, legal-risk, synthesizer) and produces all five output files. All outputs are committed back to the repo automatically.

Reference documents in the `assets/` folder (such as SOC 2 reports or NDA templates) are preprocessed and injected as context, enabling the analysis to flag deviations from your internal standards.

---

## Project layout

```
rfp-pdfs/                   Input PDFs — drop contracts here
rfp-markdown/               Converted markdown files
rfp-markdown/generated/     Final analysis output files
rfp-markdown/audit/         Per-run audit artifacts and diagnostics
linkedin-series-archive/    Immutable timestamped snapshots of generated outputs per workflow run
assets/                     Optional reference documents for comparative analysis
src/                        Python analysis pipeline source
.github/workflows/          Automation workflows
prompts/                    Agent prompt files — edit these to change analysis behavior
```

---

## Quickstart

### 1. Automated pipeline (recommended)

Add a PDF to `rfp-pdfs/` and push. Both workflows run automatically and commit all five output files to `rfp-markdown/generated/`.

```bash
# Copy your contract into the input folder
cp your-contract.pdf rfp-pdfs/

# Push to trigger the pipeline
git add rfp-pdfs/your-contract.pdf
git commit -m "add contract for analysis"
git push
```

### 2. Local PDF conversion

```bash
npm ci
npm run convert:pdf
```

Convert a specific file or folder:

```bash
node convert-pdf-to-markdown.js rfp-pdfs/path/to/file.pdf
node convert-pdf-to-markdown.js rfp-pdfs/some-subfolder
```

OCR fallback options (requires `pdftoppm` and `tesseract`):

```bash
node convert-pdf-to-markdown.js --ocr-fallback --min-text-chars 600
```

### 3. Local Python analysis

Run the full analysis pipeline against an already-converted markdown file:

```bash
python -m pdf_multi_agent_analysis.cli analyze-markdown \
  "rfp-markdown/generated/your-contract-final.md" \
  --assets-dir assets \
  --out-dir rfp-markdown/generated
```

With OCR fallback enabled for scanned asset PDFs:

```bash
python -m pdf_multi_agent_analysis.cli analyze-markdown \
  "rfp-markdown/generated/your-contract-final.md" \
  --assets-dir assets \
  --out-dir rfp-markdown/generated \
  --asset-ocr-fallback \
  --asset-ocr-max-pages 8
```

---

## OCR prerequisites

Local OCR fallback requires:

- `pdftoppm` (from `poppler-utils`)
- `tesseract`

Install on Ubuntu:

```bash
sudo apt-get update
sudo apt-get install -y poppler-utils tesseract-ocr
```

---

## Workflow configuration

### Workflow 1: PDF conversion

File: `.github/workflows/convert-rfp-pdf-to-markdown.yml`

Triggers on `push` to `rfp-pdfs/**/*.pdf` or `workflow_dispatch` with optional `pdf_path` input. Detects added, modified, renamed, and deleted PDFs. Commits only when `rfp-markdown/` content changes.

### Workflow 2: Multi-agent refinement

File: `.github/workflows/local-multistage-refinement.yml`

Triggers on `push` to `rfp-markdown/**/*.md` (excluding generated and audit paths), on successful completion of Workflow 1, or via `workflow_dispatch`.

Target selection:

- **push**: processes only the markdown files added or modified in the triggering
  commit — not all source files in the folder
- **workflow_dispatch**: processes `file_path`, or `uploads_glob`, or all source
  markdown files if neither input is set
- **workflow_run**: processes only the files converted in the triggering conversion
  workflow run

Optional environment toggles:

| Variable | Default |
|---|---|
| `ENABLE_GITHUB_MODELS_CLAUDE` | `"true"` |
| `GITHUB_MODELS_CLAUDE_MODEL` | `anthropic/claude-sonnet-4.5` |
| `GITHUB_MODELS_ENDPOINT` | `https://models.github.ai/inference/chat/completions` |
| `MAX_REFINEMENT_RETRIES` | `"1"` |

GitHub Models requirements: workflow permissions include `models: read`. Uses `github.token` — no Anthropic API key required.

---

## Reference assets

Place supporting documents in the `assets/` folder to enable comparative analysis. The pipeline will extract their content and use it to flag deviations, missing clauses, and alignment gaps in the contract being analyzed.

Supported formats: `.md`, `.txt`, `.json`, `.yaml`, `.yml`, `.pdf`, `.docx`

Assets that cannot be parsed are flagged in the Reference Document Status section of the analysis file with a plain-language note rather than a silent failure.

---

## Contributing or extending

Agent prompts are in `prompts/`. To change how the pipeline analyzes contracts — for example to add a new clause category, adjust risk scoring criteria, or tune the executive summary format — edit the relevant prompt file and push. The workflow picks up prompt changes automatically on the next run.

To extend the pipeline with a new document type or output file, the Python source is in `src/pdf_multi_agent_analysis/`. The `pipeline.py` file controls agent sequencing and output file generation. The `agents.py` file defines individual agent behavior.

---

## Known limitations

- **Scanned PDFs with heavy OCR artifacts**: Reference asset PDFs that were scanned rather than born-digital may produce degraded extracted text even after the OCR cleanup pass. The pipeline will flag these in the Reference Document Status section rather than silently injecting low-quality context, but the analysis will not reflect their contents. Replace scanned assets with text-based PDFs where possible.

- **Large contracts**: Contracts over approximately 40 pages will produce a large analysis file due to chunk volume. The section grouping and deduplication logic reduces this significantly, but very long contracts with many subsections may still produce lengthy output. The executive summary and scorecard files remain concise regardless of contract length and are the recommended starting point for long documents.

---

## Implementation notes

The pipeline has two execution paths that complement each other:

**Node + GitHub Actions** is the primary automation path. Push a PDF and all five output files are produced and committed automatically with no local setup required beyond a GitHub repository.

**Python CLI** provides local analysis capability for teams that want to run the pipeline on existing markdown files, integrate with other tooling, or iterate on prompts without pushing to GitHub.

Both paths produce the same five output files and use the same underlying agent logic.

---

## Reliability and safety controls

- Strict shell mode (`set -euo pipefail`) in all workflow steps
- Explicit stage sequencing with artifact persistence between stages
- Path filtering and actor guards to prevent commit loops
- Idempotent writes — files are only updated when content changes
- Stage D fallback to Stage C output if GitHub Models is unavailable
- Asset extraction quality thresholds — degraded OCR output is flagged rather than silently injected into analysis context
