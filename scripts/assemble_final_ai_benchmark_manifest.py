import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FINAL_VISUAL = ROOT / "metadata" / "ai_generated_final_visual_subset.csv"
FINAL_QUESTIONS = ROOT / "metadata" / "ai_generated_final_question_bank.csv"
OUT = ROOT / "metadata" / "ai_generated_final_benchmark_manifest.csv"
SUMMARY = ROOT / "metadata" / "ai_generated_final_benchmark_summary.json"


def read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def main():
    errors = []
    if not FINAL_VISUAL.exists():
        errors.append(f"missing {FINAL_VISUAL}")
    if not FINAL_QUESTIONS.exists():
        errors.append(f"missing {FINAL_QUESTIONS}")
    if errors:
        summary = {
            "ready": False,
            "errors": errors,
            "message": "Run visual and question HITL adjudication before assembling the final AI benchmark manifest.",
        }
        SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps(summary, indent=2))
        return

    visual_rows = read_csv(FINAL_VISUAL)
    question_rows = read_csv(FINAL_QUESTIONS)
    kept_clips = {row["clip_id"] for row in visual_rows if row.get("final_keep_for_ai_subset", "").lower() == "yes"}
    final_questions = [row for row in question_rows if row["clip_id"] in kept_clips and row.get("final_question_valid") == "yes"]

    missing_clip_questions = sorted(kept_clips - {row["clip_id"] for row in final_questions})
    by_clip_task = {}
    for row in final_questions:
        by_clip_task.setdefault(row["clip_id"], set()).add(row["task"])
    incomplete_task_clips = {
        clip_id: sorted(tasks)
        for clip_id, tasks in by_clip_task.items()
        if tasks != {"accuracy", "vhd_i_pdi", "vhd_ii_hce"}
    }

    fields = list(final_questions[0].keys()) if final_questions else ["question_id"]
    with OUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(final_questions)

    task_counts = {}
    category_counts = {}
    for row in final_questions:
        task_counts[row["task"]] = task_counts.get(row["task"], 0) + 1
        key = f"{row['task']}::{row['vhd_category']}"
        category_counts[key] = category_counts.get(key, 0) + 1

    summary = {
        "ready": not missing_clip_questions and not incomplete_task_clips and bool(final_questions),
        "kept_visual_clip_count": len(kept_clips),
        "final_question_count": len(final_questions),
        "task_counts": task_counts,
        "task_category_counts": category_counts,
        "missing_clip_questions": missing_clip_questions,
        "incomplete_task_clips": incomplete_task_clips,
        "output_manifest": str(OUT.relative_to(ROOT)),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
