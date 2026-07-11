import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FINAL_QUESTIONS = ROOT / "metadata" / "real_final_question_bank.csv"
OUT = ROOT / "metadata" / "real_final_benchmark_manifest.csv"
SUMMARY = ROOT / "metadata" / "real_final_benchmark_summary.json"


def read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def main():
    if not FINAL_QUESTIONS.exists():
        summary = {"ready": False, "error": f"missing {FINAL_QUESTIONS}"}
        SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps(summary, indent=2))
        return
    rows = [row for row in read_csv(FINAL_QUESTIONS) if row.get("final_question_valid") == "yes"]
    task_counts = {}
    category_counts = {}
    for row in rows:
        task_counts[row["task"]] = task_counts.get(row["task"], 0) + 1
        category_counts[row["vhd_category"]] = category_counts.get(row["vhd_category"], 0) + 1
    fields = list(rows[0].keys()) if rows else ["question_id"]
    with OUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "ready": bool(rows),
        "final_question_count": len(rows),
        "task_counts": task_counts,
        "category_counts": category_counts,
        "output_manifest": str(OUT.relative_to(ROOT)),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
