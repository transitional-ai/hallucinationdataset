import csv
import html
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QUESTION_BANK = ROOT / "metadata" / "ai_generated_draft_question_bank.csv"
OUT_DIR = ROOT / "hitl_question_review"


REVIEW_FIELDS = [
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
    "caption_for_reference",
    "question_text",
    "option_A",
    "option_B",
    "option_C",
    "option_D",
    "draft_correct_answer",
    "draft_A_language_prior",
    "draft_A_vision",
    "draft_uncertainty_label",
    "question_valid",
    "final_correct_answer",
    "final_A_language_prior",
    "final_A_vision",
    "final_uncertainty_label",
    "reviewer_notes",
]


def read_questions():
    with QUESTION_BANK.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def review_row(row, reviewer_id):
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
        "caption_for_reference": row["caption_for_reference"],
        "question_text": row["question_text"],
        "option_A": row["option_A"],
        "option_B": row["option_B"],
        "option_C": row["option_C"],
        "option_D": row["option_D"],
        "draft_correct_answer": row["correct_answer"],
        "draft_A_language_prior": row["A_language_prior"],
        "draft_A_vision": row["A_vision"],
        "draft_uncertainty_label": row["expected_uncertainty_label"],
        "question_valid": "",
        "final_correct_answer": "",
        "final_A_language_prior": "",
        "final_A_vision": "",
        "final_uncertainty_label": "",
        "reviewer_notes": "",
    }


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def make_html(rows):
    cards = []
    for row in rows:
        video = row["stimulus_path"].replace("\\", "/")
        options = []
        for key in ["option_A", "option_B", "option_C", "option_D"]:
            value = row.get(key, "")
            if value:
                options.append(f"<li><strong>{key[-1]}</strong>: {html.escape(value)}</li>")
        cards.append(
            f"""
<article class="card" id="{html.escape(row['question_id'])}">
  <header>
    <h2>{html.escape(row['question_id'])}</h2>
    <span>{html.escape(row['task'])}</span>
    <span>{html.escape(row['vhd_category'])}</span>
  </header>
  <p class="caption">{html.escape(row['caption_for_reference'])}</p>
  <video controls preload="metadata" src="../{html.escape(video)}"></video>
  <p class="question">{html.escape(row['question_text'])}</p>
  <ol>{''.join(options)}</ol>
  <dl>
    <dt>Draft correct</dt><dd>{html.escape(row['draft_correct_answer'])}</dd>
    <dt>Language-prior option</dt><dd>{html.escape(row['draft_A_language_prior'])}</dd>
    <dt>Vision option</dt><dd>{html.escape(row['draft_A_vision'])}</dd>
    <dt>Uncertainty label</dt><dd>{html.escape(row['draft_uncertainty_label'])}</dd>
    <dt>Long video</dt><dd>{html.escape(row['long_video_name'])} [{html.escape(row['long_video_start_sec_planned'])}, {html.escape(row['long_video_end_sec_planned'])}]</dd>
  </dl>
</article>
"""
        )

    css = """
body { font-family: Georgia, 'Times New Roman', serif; margin: 24px; background: #f7f2ea; color: #231f1a; }
h1 { margin-bottom: 4px; }
.meta { color: #6e6258; margin-bottom: 24px; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(520px, 1fr)); gap: 18px; }
.card { background: #fffaf2; border: 1px solid #d9c7ad; padding: 14px; box-shadow: 0 1px 2px rgba(0,0,0,.08); }
header { display: flex; gap: 10px; align-items: baseline; flex-wrap: wrap; }
h2 { font-size: 16px; margin: 0 8px 0 0; }
header span { background: #ead8bd; padding: 2px 8px; border-radius: 12px; font-size: 13px; }
.caption { font-size: 13px; color: #5f554d; min-height: 34px; }
.question { font-size: 15px; font-weight: bold; line-height: 1.35; }
video { width: 100%; background: #000; display: block; }
ol { padding-left: 22px; font-size: 14px; }
dl { display: grid; grid-template-columns: 130px 1fr; gap: 4px 8px; font-size: 13px; }
dt { font-weight: bold; }
dd { margin: 0; }
"""
    doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>VHD AI-generated Question Review Dashboard</title>
  <style>{css}</style>
</head>
<body>
  <h1>VHD AI-generated Question Review Dashboard</h1>
  <p class="meta">Use this page with question_reviewer_1.csv and question_reviewer_2.csv. Review question validity and final labels.</p>
  <section class="grid">{''.join(cards)}</section>
</body>
</html>
"""
    (OUT_DIR / "question_review_dashboard.html").write_text(doc, encoding="utf-8")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    questions = read_questions()
    reviewer_1 = [review_row(row, "reviewer_1") for row in questions]
    reviewer_2 = [dict(row, reviewer_id="reviewer_2") for row in reviewer_1]
    write_csv(OUT_DIR / "question_reviewer_1.csv", reviewer_1)
    write_csv(OUT_DIR / "question_reviewer_2.csv", reviewer_2)
    make_html(reviewer_1)
    print(f"question_review_rows={len(reviewer_1)}")
    print(f"output_dir={OUT_DIR}")


if __name__ == "__main__":
    main()
