import argparse
import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REVIEW_DIR = ROOT / "hitl_real_question_review"
OUT_DIR = ROOT / "metadata"


FIELDS_TO_CHECK = ["question_valid", "final_correct_answer", "final_A_language_prior", "final_A_vision", "final_uncertainty_label"]


def read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reviewer-1", default=str(REVIEW_DIR / "real_question_reviewer_1.csv"))
    parser.add_argument("--reviewer-2", default=str(REVIEW_DIR / "real_question_reviewer_2.csv"))
    parser.add_argument("--allow-incomplete", action="store_true")
    args = parser.parse_args()

    r1 = {row["question_id"]: row for row in read_csv(Path(args.reviewer_1))}
    r2 = {row["question_id"]: row for row in read_csv(Path(args.reviewer_2))}
    ids = sorted(set(r1) | set(r2))
    missing = []
    disagreements = []
    out_rows = []
    for qid in ids:
        a = r1.get(qid)
        b = r2.get(qid)
        if not a or not b:
            missing.append({"question_id": qid, "issue": "missing row"})
            continue
        incomplete = []
        a_valid = a.get("question_valid", "").strip().lower()
        b_valid = b.get("question_valid", "").strip().lower()
        if a_valid not in {"yes", "no"} or b_valid not in {"yes", "no"}:
            incomplete.append("question_valid")
        labels_required = a_valid == "yes" and b_valid == "yes"
        for field in FIELDS_TO_CHECK:
            if field == "question_valid":
                continue
            if not labels_required:
                continue
            if field in {"final_A_language_prior", "final_A_vision"} and a["task"] != "vhd_i_pdi":
                continue
            if field == "final_uncertainty_label" and a["task"] != "vhd_ii_hce":
                continue
            if not a.get(field, "").strip() or not b.get(field, "").strip():
                incomplete.append(field)
        if incomplete:
            missing.append({"question_id": qid, "issue": "incomplete labels", "fields": incomplete})
            if not args.allow_incomplete:
                continue
        disagree = [field for field in FIELDS_TO_CHECK if a.get(field, "").strip() and b.get(field, "").strip() and a.get(field, "").strip() != b.get(field, "").strip()]
        if disagree:
            disagreements.append({"question_id": qid, "fields": disagree})
        final_valid = a.get("question_valid", "").strip().lower() if a.get("question_valid", "").strip().lower() == b.get("question_valid", "").strip().lower() else ("needs_adjudication" if args.allow_incomplete else "")
        out_rows.append({
            "question_id": qid,
            "clip_id": a.get("clip_id", ""),
            "vhd_category": a.get("vhd_category", ""),
            "task": a.get("task", ""),
            "stimulus_path": a.get("stimulus_path", ""),
            "question_text": a.get("question_text", ""),
            "option_A": a.get("option_A", ""),
            "option_B": a.get("option_B", ""),
            "final_question_valid": final_valid,
            "final_correct_answer": a.get("final_correct_answer", "").strip() if a.get("final_correct_answer", "").strip() == b.get("final_correct_answer", "").strip() else "",
            "final_A_language_prior": a.get("final_A_language_prior", "").strip() if a.get("final_A_language_prior", "").strip() == b.get("final_A_language_prior", "").strip() else "",
            "final_A_vision": a.get("final_A_vision", "").strip() if a.get("final_A_vision", "").strip() == b.get("final_A_vision", "").strip() else "",
            "final_uncertainty_label": a.get("final_uncertainty_label", "").strip() if a.get("final_uncertainty_label", "").strip() == b.get("final_uncertainty_label", "").strip() else "",
            "needs_adjudication": "yes" if disagree or final_valid == "needs_adjudication" else "no",
            "disagreement_fields": ";".join(disagree),
        })

    adjudication_path = OUT_DIR / "real_question_adjudication.csv"
    final_path = OUT_DIR / "real_final_question_bank.csv"
    fields = list(out_rows[0].keys()) if out_rows else ["question_id"]
    with adjudication_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(out_rows)
    final_rows = [row for row in out_rows if row["final_question_valid"] == "yes"]
    with final_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(final_rows)
    summary = {
        "reviewer_1_rows": len(r1),
        "reviewer_2_rows": len(r2),
        "question_ids_seen": len(ids),
        "missing_or_incomplete_count": len(missing),
        "disagreement_count": len(disagreements),
        "final_valid_question_count": len(final_rows),
        "complete_enough_for_final_question_claim": len(missing) == 0 and len(disagreements) == 0 and len(final_rows) > 0,
        "adjudication_csv": str(adjudication_path.relative_to(ROOT)),
        "final_question_bank_csv": str(final_path.relative_to(ROOT)),
    }
    (OUT_DIR / "real_question_adjudication_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
