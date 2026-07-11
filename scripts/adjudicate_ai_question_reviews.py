import argparse
import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REVIEW_DIR = ROOT / "hitl_question_review"
OUT_DIR = ROOT / "metadata"


LABEL_FIELDS = [
    "question_valid",
    "final_correct_answer",
    "final_A_language_prior",
    "final_A_vision",
    "final_uncertainty_label",
]


def read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def cohen_kappa(labels_a, labels_b):
    pairs = [(a, b) for a, b in zip(labels_a, labels_b) if a and b]
    if not pairs:
        return None
    total = len(pairs)
    observed = sum(1 for a, b in pairs if a == b) / total
    labels = sorted(set([a for a, _ in pairs] + [b for _, b in pairs]))
    expected = 0.0
    for label in labels:
        pa = sum(1 for a, _ in pairs if a == label) / total
        pb = sum(1 for _, b in pairs if b == label) / total
        expected += pa * pb
    if expected == 1:
        return 1.0
    return round((observed - expected) / (1 - expected), 4)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reviewer-1", default=str(REVIEW_DIR / "question_reviewer_1.csv"))
    parser.add_argument("--reviewer-2", default=str(REVIEW_DIR / "question_reviewer_2.csv"))
    parser.add_argument("--allow-incomplete", action="store_true")
    args = parser.parse_args()

    r1 = {row["question_id"]: row for row in read_csv(Path(args.reviewer_1))}
    r2 = {row["question_id"]: row for row in read_csv(Path(args.reviewer_2))}
    question_ids = sorted(set(r1) | set(r2))

    missing = []
    disagreements = []
    adjudicated = []
    for qid in question_ids:
        row1 = r1.get(qid)
        row2 = r2.get(qid)
        if row1 is None or row2 is None:
            missing.append({"question_id": qid, "issue": "missing row in one reviewer file"})
            continue

        incomplete_fields = []
        for field in LABEL_FIELDS:
            value1 = row1.get(field, "").strip()
            value2 = row2.get(field, "").strip()
            if field in {"final_A_language_prior", "final_A_vision"} and row1["task"] != "vhd_i_pdi":
                continue
            if field == "final_uncertainty_label" and row1["task"] != "vhd_ii_hce":
                continue
            if not value1 or not value2:
                incomplete_fields.append(field)
        if incomplete_fields:
            missing.append({"question_id": qid, "issue": "incomplete labels", "fields": incomplete_fields})
            if not args.allow_incomplete:
                continue

        field_disagreements = []
        for field in LABEL_FIELDS:
            value1 = row1.get(field, "").strip()
            value2 = row2.get(field, "").strip()
            if value1 and value2 and value1 != value2:
                field_disagreements.append(field)
        if field_disagreements:
            disagreements.append({"question_id": qid, "fields": field_disagreements})

        valid1 = row1.get("question_valid", "").strip().lower()
        valid2 = row2.get("question_valid", "").strip().lower()
        final_valid = ""
        if valid1 and valid1 == valid2:
            final_valid = valid1
        elif args.allow_incomplete:
            final_valid = "needs_adjudication"

        out = {
            "question_id": qid,
            "clip_id": row1.get("clip_id", ""),
            "vhd_category": row1.get("vhd_category", ""),
            "task": row1.get("task", ""),
            "stimulus_type": row1.get("stimulus_type", ""),
            "stimulus_path": row1.get("stimulus_path", ""),
            "long_video_name": row1.get("long_video_name", ""),
            "long_video_start_sec_planned": row1.get("long_video_start_sec_planned", ""),
            "long_video_end_sec_planned": row1.get("long_video_end_sec_planned", ""),
            "question_text": row1.get("question_text", ""),
            "option_A": row1.get("option_A", ""),
            "option_B": row1.get("option_B", ""),
            "option_C": row1.get("option_C", ""),
            "option_D": row1.get("option_D", ""),
            "reviewer_1_valid": valid1,
            "reviewer_2_valid": valid2,
            "final_question_valid": final_valid,
            "final_correct_answer": row1.get("final_correct_answer", "").strip()
            if row1.get("final_correct_answer", "").strip() == row2.get("final_correct_answer", "").strip()
            else "",
            "final_A_language_prior": row1.get("final_A_language_prior", "").strip()
            if row1.get("final_A_language_prior", "").strip() == row2.get("final_A_language_prior", "").strip()
            else "",
            "final_A_vision": row1.get("final_A_vision", "").strip()
            if row1.get("final_A_vision", "").strip() == row2.get("final_A_vision", "").strip()
            else "",
            "final_uncertainty_label": row1.get("final_uncertainty_label", "").strip()
            if row1.get("final_uncertainty_label", "").strip() == row2.get("final_uncertainty_label", "").strip()
            else "",
            "needs_adjudication": "yes" if field_disagreements or final_valid == "needs_adjudication" else "no",
            "disagreement_fields": ";".join(field_disagreements),
        }
        adjudicated.append(out)

    kappas = {}
    for field in LABEL_FIELDS:
        labels_a = []
        labels_b = []
        for qid in question_ids:
            if qid not in r1 or qid not in r2:
                continue
            if field in {"final_A_language_prior", "final_A_vision"} and r1[qid]["task"] != "vhd_i_pdi":
                continue
            if field == "final_uncertainty_label" and r1[qid]["task"] != "vhd_ii_hce":
                continue
            labels_a.append(r1[qid].get(field, "").strip().lower())
            labels_b.append(r2[qid].get(field, "").strip().lower())
        kappas[field] = cohen_kappa(labels_a, labels_b)

    fields = list(adjudicated[0].keys()) if adjudicated else []
    adjudicated_path = OUT_DIR / "ai_generated_question_adjudication.csv"
    with adjudicated_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(adjudicated)

    final_rows = [row for row in adjudicated if row["final_question_valid"] == "yes"]
    final_path = OUT_DIR / "ai_generated_final_question_bank.csv"
    with final_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(final_rows)

    summary = {
        "reviewer_1_rows": len(r1),
        "reviewer_2_rows": len(r2),
        "question_ids_seen": len(question_ids),
        "missing_or_incomplete_count": len(missing),
        "disagreement_count": len(disagreements),
        "final_valid_question_count": len(final_rows),
        "kappa": kappas,
        "adjudication_csv": str(adjudicated_path.relative_to(ROOT)),
        "final_question_bank_csv": str(final_path.relative_to(ROOT)),
        "complete_enough_for_final_question_claim": len(missing) == 0 and len(disagreements) == 0 and len(final_rows) > 0,
    }
    summary_path = OUT_DIR / "ai_generated_question_adjudication_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
