from __future__ import annotations

import argparse
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import quote


EXPECTED_SUFFIXES = {
    "final": "-final.md",
    "analysis": "-final.analysis.md",
    "issues": "-final.issues.md",
    "scorecard": "-final.scorecard.md",
    "executive": "-final.executive-summary.md",
}

RISK_ORDER = {
    "HIGH": 4,
    "MEDIUM": 3,
    "LOW": 2,
    "NOT FOUND": 1,
    "UNKNOWN": 0,
}


@dataclass
class ContractRecord:
    stem: str
    slug: str
    files: dict[str, Path]
    latest_risk: str
    last_run: str
    run_count: int
    completeness: str


@dataclass
class RunRecord:
    created_utc: str
    workflow_run_id: str
    workflow_attempt: str
    copied_files: str
    targets: list[str]
    manifest_path: Path


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value)
    return value.strip("-") or "contract"


def extract_frontmatter_value(path: Path, key: str) -> str:
    text = path.read_text(encoding="utf-8", errors="ignore")
    if not text.startswith("---\n"):
        return ""

    end = text.find("\n---", 4)
    if end == -1:
        return ""

    frontmatter = text[4:end]
    pattern = re.compile(rf"^{re.escape(key)}:\s*\"?([^\"\n]+)\"?\s*$", re.MULTILINE)
    match = pattern.search(frontmatter)
    return match.group(1).strip() if match else ""


def extract_overall_risk(scorecard_path: Path) -> str:
    text = scorecard_path.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r"Overall contract risk rating:\s*([A-Z ]+)", text)
    if match:
        return match.group(1).strip()

    match = re.search(r"Overall contract risk is\s*([A-Z ]+)", text)
    if match:
        return match.group(1).strip()

    return "UNKNOWN"


def extract_summary_snippet(executive_path: Path, max_lines: int = 12) -> str:
    lines = executive_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    output: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        output.append(stripped)
        if len(output) >= max_lines:
            break

    return "\n".join(output)


def parse_manifest(path: Path) -> RunRecord:
    content = path.read_text(encoding="utf-8", errors="ignore")

    def extract_field(name: str) -> str:
        match = re.search(rf"^-\s*{re.escape(name)}:\s*(.+)\s*$", content, re.MULTILINE)
        return match.group(1).strip() if match else ""

    targets: list[str] = []
    target_block = re.search(r"^##\s+Targets\s*$([\s\S]*)", content, re.MULTILINE)
    if target_block:
        for raw_line in target_block.group(1).splitlines():
            line = raw_line.strip()
            if line.startswith("- "):
                targets.append(line[2:].strip())

    return RunRecord(
        created_utc=extract_field("created_utc"),
        workflow_run_id=extract_field("workflow_run_id"),
        workflow_attempt=extract_field("workflow_attempt"),
        copied_files=extract_field("copied_files"),
        targets=targets,
        manifest_path=path,
    )


def parse_created_utc_sort_key(raw: str) -> datetime:
    try:
        return datetime.strptime(raw, "%Y%m%dT%H%M%SZ")
    except ValueError:
        return datetime.min


def parse_iso_datetime(raw: str) -> datetime | None:
    if not raw:
        return None
    normalized = raw.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def to_date_only(raw: str) -> str:
    parsed = parse_iso_datetime(raw)
    if parsed:
        return parsed.date().isoformat()
    if len(raw) >= 10 and raw[4] == "-" and raw[7] == "-":
        return raw[:10]
    return ""


def build_blob_url(repo_url: str, relative_path: Path) -> str:
    if not repo_url:
        return ""

    clean_base = repo_url.rstrip("/")
    encoded_parts = [quote(part) for part in relative_path.as_posix().split("/")]
    return f"{clean_base}/blob/main/{'/'.join(encoded_parts)}"


def discover_runs(archive_root: Path) -> list[RunRecord]:
    manifests = sorted(archive_root.glob("*/_snapshot-manifest.md"))
    records = [parse_manifest(path) for path in manifests]
    records.sort(key=lambda r: parse_created_utc_sort_key(r.created_utc), reverse=True)
    return records


def discover_contracts(generated_root: Path, runs: list[RunRecord]) -> list[ContractRecord]:
    stems: set[str] = set()
    for final_file in generated_root.glob("*-final.md"):
        stem = final_file.name[: -len(EXPECTED_SUFFIXES["final"])]
        stems.add(stem)

    run_counts: dict[str, int] = {}
    for run in runs:
        target_stems = {Path(t).stem for t in run.targets}
        for stem in target_stems:
            run_counts[stem] = run_counts.get(stem, 0) + 1

    contracts: list[ContractRecord] = []
    for stem in sorted(stems, key=lambda s: s.lower()):
        files: dict[str, Path] = {}
        missing = 0
        for key, suffix in EXPECTED_SUFFIXES.items():
            path = generated_root / f"{stem}{suffix}"
            if path.exists():
                files[key] = path
            else:
                missing += 1

        last_run = ""
        if "final" in files:
            last_run = extract_frontmatter_value(files["final"], "last_run")

        latest_risk = "UNKNOWN"
        if "scorecard" in files:
            latest_risk = extract_overall_risk(files["scorecard"])

        contracts.append(
            ContractRecord(
                stem=stem,
                slug=slugify(stem),
                files=files,
                latest_risk=latest_risk,
                last_run=last_run,
                run_count=run_counts.get(stem, 0),
                completeness="complete" if missing == 0 else f"missing-{missing}",
            )
        )

    contracts.sort(
        key=lambda c: (
            parse_iso_datetime(c.last_run) or datetime.min,
            RISK_ORDER.get(c.latest_risk, 0),
            c.stem.lower(),
        ),
        reverse=True,
    )
    return contracts


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


def copy_contract_artifacts(contract: ContractRecord, contract_dir: Path) -> None:
    for key, src in contract.files.items():
        target_name = {
            "final": "final.md",
            "analysis": "analysis.md",
            "issues": "issues.md",
            "scorecard": "scorecard.md",
            "executive": "executive-summary.md",
        }[key]
        shutil.copy2(src, contract_dir / target_name)


def build_home_page(contracts: list[ContractRecord], runs: list[RunRecord]) -> str:
    latest_contract = contracts[0] if contracts else None
    latest_run = runs[0] if runs else None
    complete_count = sum(1 for c in contracts if c.completeness == "complete")
    risk_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "NOT FOUND": 0, "UNKNOWN": 0}
    for contract in contracts:
        risk_counts[contract.latest_risk] = risk_counts.get(contract.latest_risk, 0) + 1

    avg_runs = round(sum(c.run_count for c in contracts) / len(contracts), 2) if contracts else 0.0
    high_risk_pct = round((risk_counts.get("HIGH", 0) / len(contracts)) * 100, 1) if contracts else 0.0
    completeness_pct = round((complete_count / len(contracts)) * 100, 1) if contracts else 0.0
    latest_targets = len(latest_run.targets) if latest_run else 0

    lines = [
        "# Contract Analysis Transparency Portal",
        "",
        "This site publishes generated analysis outputs and immutable run history from the repository.",
        "",
        "## KPI Snapshot",
        "",
        f"- Contracts indexed: {len(contracts)}",
        f"- High risk contracts: {risk_counts.get('HIGH', 0)} ({high_risk_pct}%)",
        f"- Medium risk contracts: {risk_counts.get('MEDIUM', 0)}",
        f"- Low risk contracts: {risk_counts.get('LOW', 0)}",
        f"- Not found risk contracts: {risk_counts.get('NOT FOUND', 0)}",
        f"- Complete artifact sets: {complete_count}",
        f"- Artifact completeness rate: {completeness_pct}%",
        f"- Total archived runs: {len(runs)}",
        f"- Average runs per contract: {avg_runs}",
    ]

    if latest_run:
        lines.extend(
            [
                "",
                "## Latest Run",
                "",
                f"- Created UTC: {latest_run.created_utc or 'unknown'}",
                f"- Workflow run: {latest_run.workflow_run_id or 'unknown'}",
                f"- Workflow attempt: {latest_run.workflow_attempt or 'unknown'}",
                f"- Copied files: {latest_run.copied_files or 'unknown'}",
                f"- Targets in latest run: {latest_targets}",
            ]
        )

    if latest_contract:
        lines.extend(
            [
                "",
                "## Latest Contract Snapshot",
                "",
                f"- Contract: {latest_contract.stem}",
                f"- Latest risk: {latest_contract.latest_risk}",
                f"- Last run: {latest_contract.last_run or 'unknown'}",
                f"- Details: [Open contract page](contracts/{latest_contract.slug}/index.md)",
                f"- Trends: [Open trends view](trends.md)",
            ]
        )

    return "\n".join(lines)


def build_contracts_index(contracts: list[ContractRecord]) -> str:
    rows: list[str] = []
    for contract in contracts:
        last_run_date = to_date_only(contract.last_run)
        risk_key = contract.latest_risk.strip().lower().replace(" ", "-")
        rows.append(
            "<tr "
            f"data-risk=\"{risk_key}\" "
            f"data-last-run=\"{last_run_date}\" "
            f"data-contract=\"{contract.stem.lower()}\">"
            f"<td>{contract.stem}</td>"
            f"<td>{contract.latest_risk}</td>"
            f"<td>{contract.last_run or 'unknown'}</td>"
            f"<td>{contract.run_count}</td>"
            f"<td>{contract.completeness}</td>"
            f"<td><a href=\"./{contract.slug}/index.md\">View</a></td>"
            "</tr>"
        )

    if not rows:
        rows.append(
            "<tr><td colspan=\"6\"><em>No contracts found</em></td></tr>"
        )

    lines = [
        "# Contracts",
        "",
        "Use filters below to narrow by latest risk and contract run date.",
        "",
        "<div style=\"display:flex;gap:12px;flex-wrap:wrap;margin:12px 0;\">",
        "  <label>Risk",
        "    <select id=\"riskFilter\">",
        "      <option value=\"all\">All</option>",
        "      <option value=\"high\">HIGH</option>",
        "      <option value=\"medium\">MEDIUM</option>",
        "      <option value=\"low\">LOW</option>",
        "      <option value=\"not-found\">NOT FOUND</option>",
        "      <option value=\"unknown\">UNKNOWN</option>",
        "    </select>",
        "  </label>",
        "  <label>From date",
        "    <input id=\"fromDate\" type=\"date\" />",
        "  </label>",
        "  <label>To date",
        "    <input id=\"toDate\" type=\"date\" />",
        "  </label>",
        "  <button id=\"resetFilters\" type=\"button\">Reset</button>",
        "</div>",
        "",
        "<table>",
        "  <thead>",
        "    <tr>",
        "      <th>Contract</th>",
        "      <th>Latest Risk</th>",
        "      <th>Last Run</th>",
        "      <th>Archived Runs</th>",
        "      <th>Status</th>",
        "      <th>Details</th>",
        "    </tr>",
        "  </thead>",
        "  <tbody id=\"contractsTableBody\">",
        *rows,
        "  </tbody>",
        "</table>",
        "",
        "<p id=\"contractsResultCount\" style=\"margin-top:8px;\"></p>",
        "",
        "<script>",
        "(function () {",
        "  const riskFilter = document.getElementById('riskFilter');",
        "  const fromDate = document.getElementById('fromDate');",
        "  const toDate = document.getElementById('toDate');",
        "  const reset = document.getElementById('resetFilters');",
        "  const body = document.getElementById('contractsTableBody');",
        "  const count = document.getElementById('contractsResultCount');",
        "  if (!riskFilter || !fromDate || !toDate || !reset || !body || !count) return;",
        "",
        "  const rows = Array.from(body.querySelectorAll('tr'));",
        "  function applyFilters() {",
        "    const risk = riskFilter.value;",
        "    const from = fromDate.value;",
        "    const to = toDate.value;",
        "    let shown = 0;",
        "    rows.forEach((row) => {",
        "      const rowRisk = (row.getAttribute('data-risk') || 'unknown');",
        "      const rowDate = row.getAttribute('data-last-run') || '';",
        "      const riskOk = risk === 'all' || rowRisk === risk;",
        "      const fromOk = !from || (rowDate && rowDate >= from);",
        "      const toOk = !to || (rowDate && rowDate <= to);",
        "      const visible = riskOk && fromOk && toOk;",
        "      row.style.display = visible ? '' : 'none';",
        "      if (visible) shown += 1;",
        "    });",
        "    count.textContent = `Showing ${shown} contract(s)`;",
        "  }",
        "",
        "  riskFilter.addEventListener('change', applyFilters);",
        "  fromDate.addEventListener('change', applyFilters);",
        "  toDate.addEventListener('change', applyFilters);",
        "  reset.addEventListener('click', () => {",
        "    riskFilter.value = 'all';",
        "    fromDate.value = '';",
        "    toDate.value = '';",
        "    applyFilters();",
        "  });",
        "",
        "  applyFilters();",
        "})();",
        "</script>",
    ]

    return "\n".join(lines)


def run_risk_for_contract(run: RunRecord, stem: str) -> str:
    snapshot_dir = run.manifest_path.parent
    scorecard = snapshot_dir / f"{stem}-final.scorecard.md"
    if not scorecard.exists():
        return "UNKNOWN"
    return extract_overall_risk(scorecard)


def build_trends_page(contracts: list[ContractRecord], runs: list[RunRecord]) -> str:
    lines = [
        "# Trends",
        "",
        "This view tracks contract risk across archived runs using scorecards saved in immutable snapshots.",
    ]

    if not contracts:
        lines.extend(["", "_No contracts available for trend analysis._"])
        return "\n".join(lines)

    for contract in contracts:
        contract_runs = runs_for_contract(runs, contract.stem)
        high_count = 0
        medium_count = 0
        low_count = 0
        not_found_count = 0
        unknown_count = 0
        trend_rows: list[str] = []

        for run in contract_runs:
            risk = run_risk_for_contract(run, contract.stem)
            if risk == "HIGH":
                high_count += 1
            elif risk == "MEDIUM":
                medium_count += 1
            elif risk == "LOW":
                low_count += 1
            elif risk == "NOT FOUND":
                not_found_count += 1
            else:
                unknown_count += 1

            trend_rows.append(
                f"| {run.created_utc or 'unknown'} | {run.workflow_run_id or 'unknown'} | "
                f"{run.workflow_attempt or 'unknown'} | {risk} |"
            )

        lines.extend(
            [
                "",
                f"## {contract.stem}",
                "",
                f"- Latest risk: {contract.latest_risk}",
                f"- Archived runs: {len(contract_runs)}",
                f"- Distribution: HIGH={high_count}, MEDIUM={medium_count}, LOW={low_count}, NOT FOUND={not_found_count}, UNKNOWN={unknown_count}",
                "",
                "| Created UTC | Workflow Run | Attempt | Risk |",
                "| --- | --- | --- | --- |",
            ]
        )

        if trend_rows:
            lines.extend(trend_rows)
        else:
            lines.append("| _No runs found_ | - | - | - |")

    return "\n".join(lines)


def build_history_page(runs: list[RunRecord], repo_url: str) -> str:
    lines = [
        "# History",
        "",
        "| Created UTC | Workflow Run | Attempt | Copied Files | Targets | Manifest |",
        "| --- | --- | --- | --- | --- | --- |",
    ]

    for run in runs:
        targets = ", ".join(Path(t).stem for t in run.targets) or "none"
        manifest_rel = Path(run.manifest_path.as_posix())
        manifest_url = build_blob_url(repo_url, manifest_rel)
        manifest_cell = f"[Manifest]({manifest_url})" if manifest_url else manifest_rel.as_posix()
        lines.append(
            "| "
            f"{run.created_utc or 'unknown'} | {run.workflow_run_id or 'unknown'} | "
            f"{run.workflow_attempt or 'unknown'} | {run.copied_files or 'unknown'} | "
            f"{targets} | {manifest_cell} |"
        )

    if len(lines) == 4:
        lines.append("| _No runs found_ | - | - | - | - | - |")

    return "\n".join(lines)


def runs_for_contract(runs: list[RunRecord], stem: str) -> list[RunRecord]:
    selected: list[RunRecord] = []
    for run in runs:
        target_stems = {Path(t).stem for t in run.targets}
        if stem in target_stems:
            selected.append(run)
    return selected


def build_contract_detail(contract: ContractRecord, contract_runs: list[RunRecord], summary_snippet: str) -> str:
    lines = [
        f"# {contract.stem}",
        "",
        "## Latest Snapshot",
        "",
        f"- Latest risk: {contract.latest_risk}",
        f"- Last run: {contract.last_run or 'unknown'}",
        f"- Archived runs: {contract.run_count}",
        f"- Artifact completeness: {contract.completeness}",
        "",
        "## Executive Summary Preview",
        "",
    ]

    if summary_snippet:
        for line in summary_snippet.splitlines():
            lines.append(f"> {line}")
    else:
        lines.append("_No executive summary available._")

    lines.extend(
        [
            "",
            "## Artifact Links",
            "",
            "- [Executive Summary](./executive-summary.md)",
            "- [Scorecard](./scorecard.md)",
            "- [Issues](./issues.md)",
            "- [Analysis](./analysis.md)",
            "- [Final Markdown](./final.md)",
            "- [Audit Runs](./audit.md)",
            "",
            "## Recent Runs",
            "",
            "| Created UTC | Workflow Run | Attempt | Copied Files |",
            "| --- | --- | --- | --- |",
        ]
    )

    for run in contract_runs[:10]:
        lines.append(
            f"| {run.created_utc or 'unknown'} | {run.workflow_run_id or 'unknown'} | "
            f"{run.workflow_attempt or 'unknown'} | {run.copied_files or 'unknown'} |"
        )

    if not contract_runs:
        lines.append("| _No runs found_ | - | - | - |")

    return "\n".join(lines)


def build_contract_audit(contract: ContractRecord, contract_runs: list[RunRecord], repo_url: str) -> str:
    lines = [
        f"# Audit Trail: {contract.stem}",
        "",
        "| Created UTC | Workflow Run | Attempt | Manifest |",
        "| --- | --- | --- | --- |",
    ]

    for run in contract_runs:
        manifest_rel = Path(run.manifest_path.as_posix())
        manifest_url = build_blob_url(repo_url, manifest_rel)
        manifest_cell = f"[Manifest]({manifest_url})" if manifest_url else manifest_rel.as_posix()
        lines.append(
            f"| {run.created_utc or 'unknown'} | {run.workflow_run_id or 'unknown'} | "
            f"{run.workflow_attempt or 'unknown'} | {manifest_cell} |"
        )

    if not contract_runs:
        lines.append("| _No runs found_ | - | - | - |")

    return "\n".join(lines)


def build_docs(
    docs_root: Path,
    generated_root: Path,
    archive_root: Path,
    contracts: list[ContractRecord],
    runs: list[RunRecord],
    repo_url: str,
) -> None:
    contracts_root = docs_root / "contracts"
    contracts_root.mkdir(parents=True, exist_ok=True)

    for child in contracts_root.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        elif child.name == "index.md":
            child.unlink()

    write_text(docs_root / "index.md", build_home_page(contracts, runs))
    write_text(contracts_root / "index.md", build_contracts_index(contracts))
    write_text(docs_root / "history.md", build_history_page(runs, repo_url))
    write_text(docs_root / "trends.md", build_trends_page(contracts, runs))

    for contract in contracts:
        contract_dir = contracts_root / contract.slug
        contract_dir.mkdir(parents=True, exist_ok=True)
        copy_contract_artifacts(contract, contract_dir)

        snippet = ""
        executive_path = contract.files.get("executive")
        if executive_path:
            snippet = extract_summary_snippet(executive_path)

        contract_runs = runs_for_contract(runs, contract.stem)
        write_text(contract_dir / "index.md", build_contract_detail(contract, contract_runs, snippet))
        write_text(contract_dir / "audit.md", build_contract_audit(contract, contract_runs, repo_url))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build MkDocs content from generated artifacts and snapshot manifests")
    parser.add_argument("--archive-root", type=Path, default=Path("linkedin-series-archive"))
    parser.add_argument("--generated-root", type=Path, default=Path("rfp-markdown/generated"))
    parser.add_argument("--docs-root", type=Path, default=Path("docs"))
    parser.add_argument(
        "--repo-url",
        default="",
        help="Repository HTTPS URL used to build links to source manifests",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_url = args.repo_url.strip()
    if not repo_url:
        gh_repo = os.getenv("GITHUB_REPOSITORY", "").strip()
        gh_server = os.getenv("GITHUB_SERVER_URL", "https://github.com").strip().rstrip("/")
        if gh_repo:
            repo_url = f"{gh_server}/{gh_repo}"
        else:
            repo_url = "https://github.com/rmallorybpc/pdf-multi-agent-analysis"

    runs = discover_runs(args.archive_root)
    contracts = discover_contracts(args.generated_root, runs)
    build_docs(args.docs_root, args.generated_root, args.archive_root, contracts, runs, repo_url)

    print(f"Runs indexed: {len(runs)}")
    print(f"Contracts indexed: {len(contracts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
