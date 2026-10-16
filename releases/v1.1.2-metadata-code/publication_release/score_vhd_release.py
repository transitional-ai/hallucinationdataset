#!/usr/bin/env python3
"""Score VHD v1.1.2 response CSVs using the publication-release files."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


TASKS = ("accuracy", "vhd_i_pdi", "vhd_ii_hce")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def normalized_choice(value: str) -> str:
    choice = value.strip().upper()
    return choice if choice in {"A", "B"} else ""


def grouped_mean(rows: list[dict[str, object]], value_key: str) -> float | None:
    by_group: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        value = row[value_key]
        if value is not None:
            by_group[str(row["source_group_id"])].append(float(value))
    if not by_group:
        return None
    group_values = [sum(values) / len(values) for values in by_group.values()]
    return sum(group_values) / len(group_values)


def score(responses_path: Path, release_dir: Path) -> dict[str, object]:
    responses = read_csv(responses_path)
    gold_rows = read_csv(release_dir / "GOLD_LABELS.csv")
    group_rows = read_csv(release_dir / "GROUPS_AND_FOLDS.csv")
    gold = {row["question_id"]: row for row in gold_rows}
    groups = {row["question_id"]: row for row in group_rows}
    if set(gold) != set(groups) or len(gold) != 801:
        raise ValueError("Publication gold/group files are incomplete or disagree")
    if not responses:
        raise ValueError("Response file is empty")

    by_model: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in responses:
        model = row.get("model_id", "model").strip() or "model"
        by_model[model].append(row)

    summaries: list[dict[str, object]] = []
    for model, model_rows in sorted(by_model.items()):
        ids = [row.get("question_id", "") for row in model_rows]
        if len(ids) != len(set(ids)):
            raise ValueError(f"Duplicate question ID for model {model}")
        unknown = set(ids) - set(gold)
        if unknown:
            raise ValueError(f"Unknown question IDs for model {model}: {len(unknown)}")
        scored: list[dict[str, object]] = []
        parse_failures = 0
        for row in model_rows:
            question_id = row["question_id"]
            selected = normalized_choice(row.get("selected_choice", ""))
            parse_ok = row.get("parse_status", "ok").strip().lower() == "ok" and bool(selected)
            if not parse_ok:
                parse_failures += 1
            target = normalized_choice(gold[question_id]["correct_answer"])
            prior = normalized_choice(gold[question_id]["language_prior_answer"])
            scored.append(
                {
                    "task": gold[question_id]["task"],
                    "source_group_id": groups[question_id]["source_group_id"],
                    "is_correct": float(selected == target) if parse_ok else 0.0,
                    "is_prior_choice": (float(selected == prior) if parse_ok and prior else None),
                }
            )
        summary: dict[str, object] = {
            "model_id": model,
            "responses_expected": 801,
            "responses_present": len(model_rows),
            "parse_failure_rate": parse_failures / len(model_rows),
            "overall_grouped_accuracy": grouped_mean(scored, "is_correct"),
        }
        for task in TASKS:
            subset = [row for row in scored if row["task"] == task]
            summary[f"{task}_questions"] = len(subset)
            summary[f"{task}_grouped_accuracy"] = grouped_mean(subset, "is_correct")
        pdi = [row for row in scored if row["task"] == "vhd_i_pdi"]
        summary["vhd_i_pdi_grouped_language_prior_choice_rate"] = grouped_mean(
            pdi, "is_prior_choice"
        )
        summaries.append(summary)

    return {
        "schema_version": "vhd-publication-score-1.0",
        "response_file": str(responses_path),
        "models": summaries,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("responses", type=Path)
    parser.add_argument(
        "--release-dir",
        type=Path,
        default=Path(__file__).resolve().parents[2]
        / "releases"
        / "vhd_eval_v1_1_2"
        / "publication_release",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = score(args.responses.resolve(), args.release_dir.resolve())
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
