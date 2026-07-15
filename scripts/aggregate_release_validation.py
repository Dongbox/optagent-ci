from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any, Sequence


def aggregate(*, artifacts_root: Path, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for path in sorted(artifacts_root.glob("**/results.jsonl")):
        rows.extend(
            _read_jsonl(
                path, source=_artifact_source(path, artifacts_root), category="api"
            )
        )
    for path in sorted(artifacts_root.glob("**/benchmark-results.jsonl")):
        rows.extend(
            _read_jsonl(
                path,
                source=_artifact_source(path, artifacts_root),
                category="benchmark",
            )
        )
    if not rows:
        raise RuntimeError("no release-validation result rows were found")
    statuses = Counter(str(row["status"]) for row in rows)
    conclusion = (
        "FAIL"
        if statuses["FAIL"]
        else "PASS_WITH_GAPS"
        if any(
            statuses[name]
            for name in ("NOT_COVERED", "ENVIRONMENT_BLOCKED", "QUALITY_WARNING")
        )
        else "PASS"
    )
    summary = {
        "schema_version": 1,
        "conclusion": conclusion,
        "status_counts": dict(sorted(statuses.items())),
        "result_count": len(rows),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    gaps = [
        row
        for row in rows
        if row["status"]
        not in {"PASS", "EXPECTED_ERROR_PASS", "DOCUMENTED_UNSUPPORTED"}
    ]
    (output_dir / "coverage-gaps.md").write_text(_gaps_markdown(gaps), encoding="utf-8")
    (output_dir / "summary.md").write_text(
        _summary_markdown(summary, rows), encoding="utf-8"
    )
    return summary


def _artifact_source(path: Path, artifacts_root: Path) -> str:
    relative = path.relative_to(artifacts_root)
    return relative.parts[0] if len(relative.parts) > 1 else path.parent.name


def _read_jsonl(path: Path, *, source: str, category: str) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        row["source"] = source
        row["category"] = category
        rows.append(row)
    return rows


def _summary_markdown(summary: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    lines = [
        "# OptAgent Release Validation",
        "",
        f"Conclusion: **{summary['conclusion']}**",
        "",
        "## Status Counts",
        "",
        "| Status | Count |",
        "| --- | ---: |",
    ]
    lines.extend(
        f"| {status} | {count} |" for status, count in summary["status_counts"].items()
    )
    lines.extend(["", "## Platform Sources", ""])
    for source in sorted({row["source"] for row in rows}):
        source_rows = [row for row in rows if row["source"] == source]
        failures = sum(row["status"] == "FAIL" for row in source_rows)
        lines.append(f"- `{source}`: {len(source_rows)} results, {failures} failures")
    lines.extend(
        [
            "",
            "## Evidence Boundary",
            "",
            "Full licensed solves use validation wheels built with ephemeral validation keys. Release wheels use the repository production public key and cover packaging, loading, and rejection paths; a production-signed positive solve remains NOT_COVERED.",
            "",
        ]
    )
    return "\n".join(lines)


def _gaps_markdown(gaps: list[dict[str, Any]]) -> str:
    lines = ["# Coverage Gaps", ""]
    if not gaps:
        return "\n".join([*lines, "None.", ""])
    for row in gaps:
        label = (
            row.get("label")
            or row.get("scenario")
            or row.get("benchmark_id")
            or "unknown"
        )
        reason = row.get("reason") or row.get("message") or ""
        lines.append(f"- `{row['status']}` `{label}` {reason}".rstrip())
    lines.append("")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    summary = aggregate(artifacts_root=args.artifacts_root, output_dir=args.output_dir)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 1 if summary["conclusion"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
