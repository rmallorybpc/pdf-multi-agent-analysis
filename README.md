# pdf-multi-agent-analysis

Reference scaffold for:

1. Converting PDF documents to markdown.
2. Running a multi-agent review and analysis pass on the converted markdown.

This repository is suitable as a baseline for building a proposal automation workflow similar to MarketEdge-style tooling.

## What this repo now includes

- Python package scaffold with CLI entrypoint.
- PDF-to-markdown converter (`pypdf` based).
- Chunking strategy for large documents.
- Multi-agent pipeline with four roles:
	- extractor
	- reviewer
	- analyst
	- synthesizer
- Prompt files for each role under `prompts/`.
- Basic tests for chunking and agent output contracts.

## Project structure

```text
.
├── prompts/
├── src/pdf_multi_agent_analysis/
│   ├── agents.py
│   ├── chunking.py
│   ├── cli.py
│   ├── config.py
│   ├── converter.py
│   └── pipeline.py
├── tests/
├── pyproject.toml
├── requirements.txt
└── requirements-dev.txt
```

## Quickstart

### 1. Create environment and install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pip install -e .
```

### 2. Convert a PDF to markdown

```bash
pdf-multi-agent-analysis convert path/to/input.pdf --out output/input.md
```

### 3. Run full pipeline

```bash
pdf-multi-agent-analysis run path/to/input.pdf --out-dir output --chunk-size 1800 --overlap 200
```

Outputs:

- `output/<name>.md`
- `output/<name>.analysis.md`

## Test

```bash
pytest
```

## Using this as a reference for a similar repo

Yes, this is now a practical reference scaffold. To adapt it to a proposal tool:

1. Replace rule-based agents in `agents.py` with LLM-backed agents.
2. Add proposal-specific schemas (sections, scoring rubric, compliance checks).
3. Add document templates and retrieval (RAG) for prior proposals.
4. Add API/UI layer (FastAPI + frontend) around the CLI pipeline.
5. Add eval suite for quality gates (coverage, factuality, style, risk).

## Suggested next milestones

1. Add `llm.py` abstraction with provider adapters (OpenAI/Azure/etc).
2. Introduce structured JSON outputs per agent.
3. Add orchestrator state persistence and trace logging.
4. Add regression tests with golden analysis snapshots.
