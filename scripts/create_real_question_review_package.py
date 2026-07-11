import csv
import html
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QUESTION_BANK = ROOT / "metadata" / "real_draft_question_bank.csv"
OUT_DIR = ROOT / "hitl_real_question_review"


FIELDS = [
    "reviewer_id",
    "question_id",
    "clip_id",
    "vhd_category",
    "task",
    "stimulus_type",
    "stimulus_path",
    "long_video_name",
    "long_video_start_sec_planned",
    "long_video_end_sec_planned",
    "question_text",
    "option_A",
    "option_B",
    "draft_correct_answer",
    "draft_A_language_prior",
    "draft_A_vision",
    "draft_uncertainty_label",
    "question_valid",
    "final_correct_answer",
    "final_A_language_prior",
    "final_A_vision",
    "final_uncertainty_label",
]


def read_questions():
    with QUESTION_BANK.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def make_row(row, reviewer_id):
    return {
        "reviewer_id": reviewer_id,
        "question_id": row["question_id"],
        "clip_id": row["clip_id"],
        "vhd_category": row["vhd_category"],
        "task": row["task"],
        "stimulus_type": row["stimulus_type"],
        "stimulus_path": row["stimulus_path"],
        "long_video_name": row["long_video_name"],
        "long_video_start_sec_planned": row["long_video_start_sec_planned"],
        "long_video_end_sec_planned": row["long_video_end_sec_planned"],
        "question_text": row["question_text"],
        "option_A": row["option_A"],
        "option_B": row["option_B"],
        "draft_correct_answer": row["correct_answer"],
        "draft_A_language_prior": row["A_language_prior"],
        "draft_A_vision": row["A_vision"],
        "draft_uncertainty_label": row["expected_uncertainty_label"],
        "question_valid": "",
        "final_correct_answer": "",
        "final_A_language_prior": "",
        "final_A_vision": "",
        "final_uncertainty_label": "",
    }


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def make_html(rows):
    cards = []
    for row in rows:
        stimulus = row["stimulus_path"].replace("\\", "/")
        cards.append(f"""
<article class="card">
<h2>{html.escape(row['question_id'])} <span>{html.escape(row['task'])}</span> <span>{html.escape(row['vhd_category'])}</span></h2>
<video controls preload="metadata" src="../{html.escape(stimulus)}"></video>
<p class="question">{html.escape(row['question_text'])}</p>
<ol>
<li><strong>A</strong>: {html.escape(row['option_A'])}</li>
<li><strong>B</strong>: {html.escape(row['option_B'])}</li>
</ol>
<dl>
<dt>Draft correct</dt><dd>{html.escape(row['draft_correct_answer'])}</dd>
<dt>Language-prior option</dt><dd>{html.escape(row['draft_A_language_prior'])}</dd>
<dt>Vision option</dt><dd>{html.escape(row['draft_A_vision'])}</dd>
<dt>Uncertainty label</dt><dd>{html.escape(row['draft_uncertainty_label'])}</dd>
<dt>Long video</dt><dd>{html.escape(row['long_video_name'])} [{html.escape(row['long_video_start_sec_planned'])}, {html.escape(row['long_video_end_sec_planned'])}]</dd>
</dl>
</article>
""")
    css = "body{font-family:Georgia,serif;background:#f7f2ea;margin:24px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(520px,1fr));gap:18px}.card{background:#fffaf2;border:1px solid #d9c7ad;padding:14px}video{width:100%;display:block;background:#000}.question{font-weight:bold}span{font-size:13px;background:#ead8bd;padding:2px 8px;border-radius:12px}dl{display:grid;grid-template-columns:130px 1fr;gap:4px 8px;font-size:13px}dd{margin:0}"
    doc = f"<!doctype html><meta charset='utf-8'><title>VHD Real Question Review</title><style>{css}</style><h1>VHD Real Question Review</h1><section class='grid'>{''.join(cards)}</section>"
    (OUT_DIR / "real_question_review_dashboard.html").write_text(doc, encoding="utf-8")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    questions = read_questions()
    r1 = [make_row(row, "reviewer_1") for row in questions]
    r2 = [dict(row, reviewer_id="reviewer_2") for row in r1]
    write_csv(OUT_DIR / "real_question_reviewer_1.csv", r1)
    write_csv(OUT_DIR / "real_question_reviewer_2.csv", r2)
    make_html(r1)
    print(f"question_review_rows={len(r1)}")
    print(f"output_dir={OUT_DIR}")


if __name__ == "__main__":
    main()
