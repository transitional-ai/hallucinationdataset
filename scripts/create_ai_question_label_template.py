import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HITL_MANIFEST = ROOT / "metadata" / "ai_generated_hitl_ready_manifest.csv"
OUT = ROOT / "metadata" / "ai_generated_question_label_template.csv"


def default_prompt(category, task):
    if task == "accuracy":
        return "Ask a factual question whose answer is directly visible in the original clip."
    if task == "vhd_i":
        if category in {"glass_breaking_or_fragments", "falling_or_gravity", "liquid_pouring_or_flow", "collision_or_impact"}:
            return "Ask a forced-choice question on the reversed clip where one option follows ordinary language prior and the other follows the reversed visual evidence."
        return "Optional: use only if reversal creates a clear temporal conflict."
    if task == "vhd_ii":
        return "Ask a question on the masked clip where the correct response should reflect whether the hidden evidence is knowable."
    return ""


def main():
    with HITL_MANIFEST.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    out_rows = []
    for row in rows:
        for task in ["accuracy", "vhd_i", "vhd_ii"]:
            out_rows.append(
                {
                    "question_id": f"{row['clip_id']}_{task}",
                    "clip_id": row["clip_id"],
                    "task": task,
                    "vhd_category": row["vhd_category"],
                    "source_video": row["clean_local_path"],
                    "caption_for_reference": row["caption"],
                    "question_writing_instruction": default_prompt(row["vhd_category"], task),
                    "question_text": "",
                    "answer_format": "mcqa" if task in {"accuracy", "vhd_i"} else "open_or_mcqa",
                    "option_A": "",
                    "option_B": "",
                    "option_C": "",
                    "option_D": "",
                    "correct_answer": "",
                    "A_language_prior": "",
                    "A_vision": "",
                    "expected_uncertainty_label": "",
                    "mask_region_xywh": "",
                    "reviewer_1_label": "",
                    "reviewer_2_label": "",
                    "adjudicated_label": "",
                    "include_in_final": "",
                    "notes": "",
                }
            )

    fields = list(out_rows[0].keys())
    with OUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(out_rows)
    print(f"question_rows={len(out_rows)}")
    print(f"output={OUT}")


if __name__ == "__main__":
    main()
