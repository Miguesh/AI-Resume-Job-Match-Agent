"""Command-line interface for the synthetic offline benchmark."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from evaluations.benchmark import DEFAULT_DATASET_PATH, evaluate_dataset


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the deterministic synthetic resume-matcher benchmark."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET_PATH,
        help="Path to a versioned benchmark JSON file.",
    )
    parser.add_argument("--json-output", type=Path, help="Optional JSON report path.")
    parser.add_argument("--markdown-output", type=Path, help="Optional Markdown report path.")
    return parser


async def _run(args: argparse.Namespace) -> int:
    report = await evaluate_dataset(args.dataset)
    if args.json_output:
        _write(args.json_output, report.to_json())
    if args.markdown_output:
        _write(args.markdown_output, report.to_markdown())
    if not args.json_output and not args.markdown_output:
        print(report.to_markdown())
    all_gates_pass = (
        report.structured_validity.rate == 1
        and report.identity_exact_match.rate == 1
        and report.score_agreement.agreement_rate == 1
        and report.fact_guard.accuracy == 1
        and all(metric.f1 == 1 for metric in report.skills.values())
        and report.required_preferred_split.accuracy == 1
    )
    return 0 if all_gates_pass else 1


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def main() -> int:
    return asyncio.run(_run(build_parser().parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
