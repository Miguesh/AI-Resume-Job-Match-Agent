from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

import pytest
from evaluations.benchmark import DEFAULT_DATASET_PATH, evaluate_dataset, load_dataset
from evaluations.runner import _run

BASELINE_PATH = Path("evaluations/baselines/local-v1.md")


def test_synthetic_dataset_declares_provenance_license_and_limitations() -> None:
    dataset = load_dataset()

    assert dataset.metadata.version == "1.0.0"
    assert dataset.metadata.license == "CC0-1.0"
    assert "synthetic" in dataset.metadata.provenance.casefold() or "authored" in (
        dataset.metadata.provenance.casefold()
    )
    assert "real-world" in dataset.metadata.limitations
    assert len(dataset.matching_cases) >= 5
    assert any("prompt-injection" in case.tags for case in dataset.matching_cases)
    assert all(
        "@" not in case.resume_text or "@example." in case.resume_text
        for case in dataset.matching_cases
    )


@pytest.mark.asyncio
async def test_local_benchmark_meets_all_golden_regression_gates() -> None:
    report = await evaluate_dataset()

    assert report.structured_validity.rate == 1
    assert report.identity_exact_match.rate == 1
    assert all(metric.precision == 1 for metric in report.skills.values())
    assert all(metric.recall == 1 for metric in report.skills.values())
    assert all(metric.f1 == 1 for metric in report.skills.values())
    assert report.required_preferred_split.accuracy == 1
    assert report.required_preferred_split.mislabeled == 0
    assert report.score_agreement.agreement_rate == 1
    assert report.score_agreement.mean_absolute_error == 0
    assert report.fact_guard.accuracy == 1
    assert {case.actual_accepted for case in report.fact_guard_cases} == {True, False}


@pytest.mark.asyncio
async def test_benchmark_report_is_deterministic_and_explains_scope() -> None:
    first = await evaluate_dataset()
    second = await evaluate_dataset()

    assert first.to_json() == second.to_json()
    markdown = first.to_markdown()
    assert "software-regression artifact" in markdown
    assert "not evidence of hiring validity" in markdown
    assert "prompt-injection-as-data" in markdown
    accepted_baseline = await asyncio.to_thread(BASELINE_PATH.read_text, encoding="utf-8")
    assert markdown == accepted_baseline


@pytest.mark.asyncio
async def test_runner_writes_machine_and_human_readable_reports(tmp_path: Path) -> None:
    json_path = tmp_path / "report.json"
    markdown_path = tmp_path / "report.md"
    args = argparse.Namespace(
        dataset=DEFAULT_DATASET_PATH,
        json_output=json_path,
        markdown_output=markdown_path,
    )

    exit_code = await _run(args)

    assert exit_code == 0
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["dataset_version"] == "1.0.0"
    assert payload["structured_validity"]["rate"] == 1
    assert markdown_path.read_text(encoding="utf-8").startswith(
        "# Synthetic resume-matcher regression benchmark"
    )
