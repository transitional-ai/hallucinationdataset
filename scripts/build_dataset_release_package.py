import csv
import json
import os
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
RELEASE = WORKSPACE / "VHD_pilot_dataset"
README = ROOT / "release_README.md"
REAL_QUESTIONS = ROOT / "hitl_real_question_review" / "real_question_reviewer_1.csv"
AI_QUESTIONS = ROOT / "hitl_question_review" / "question_reviewer_1.csv"

METADATA_FILES = [
    "real_provenance_manifest.csv",
    "ai_generated_provenance_manifest.csv",
    "real_verified_clean_manifest.csv",
    "ai_generated_verified_clean_manifest.csv",
    "real_subset_statistics.csv",
    "ai_generated_subset_statistics.csv",
    "real_audio_restoration_report.json",
]


def load_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def hardlink_or_copy(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        destination.unlink()
    try:
        os.link(source, destination)
    except OSError:
        shutil.copy2(source, destination)


def write_csv(path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    if RELEASE.exists():
        resolved = RELEASE.resolve()
        if resolved.parent != WORKSPACE.resolve() or resolved.name != "VHD_pilot_dataset":
            raise RuntimeError(f"Refusing to replace unexpected path: {resolved}")
        shutil.rmtree(resolved)

    (RELEASE / "questions").mkdir(parents=True)
    (RELEASE / "metadata").mkdir()
    shutil.copy2(README, RELEASE / "README.md")
    shutil.copy2(REAL_QUESTIONS, RELEASE / "questions" / "real_question_reviewer_1.csv")
    shutil.copy2(AI_QUESTIONS, RELEASE / "questions" / "ai_question_reviewer_1.csv")

    real_rows, real_fields = load_csv(REAL_QUESTIONS)
    ai_rows, ai_fields = load_csv(AI_QUESTIONS)
    combined_fields = ["video_split", "release_video_path"]
    for field in real_fields + ai_fields:
        if field not in combined_fields:
            combined_fields.append(field)

    combined_rows = []
    file_manifest = []
    seen_destinations = set()
    for split, rows in (("real", real_rows), ("ai_generated", ai_rows)):
        for row in rows:
            source = ROOT / row["stimulus_path"]
            if not source.is_file():
                raise FileNotFoundError(source)
            stimulus_type = row["stimulus_type"]
            category = row["vhd_category"]
            relative = Path("videos") / split / stimulus_type / category / source.name
            if relative in seen_destinations:
                raise RuntimeError(f"Duplicate release path: {relative}")
            seen_destinations.add(relative)
            destination = RELEASE / relative
            hardlink_or_copy(source, destination)

            output_row = {field: row.get(field, "") for field in combined_fields}
            output_row["video_split"] = split
            output_row["release_video_path"] = relative.as_posix()
            combined_rows.append(output_row)
            file_manifest.append(
                {
                    "clip_id": row["clip_id"],
                    "video_split": split,
                    "stimulus_type": stimulus_type,
                    "vhd_category": category,
                    "release_video_path": relative.as_posix(),
                    "size_bytes": source.stat().st_size,
                }
            )

    write_csv(RELEASE / "questions" / "vhd_questions.csv", combined_fields, combined_rows)
    write_csv(
        RELEASE / "metadata" / "video_file_manifest.csv",
        list(file_manifest[0]),
        file_manifest,
    )

    for name in METADATA_FILES:
        source = ROOT / "metadata" / name
        if source.exists():
            shutil.copy2(source, RELEASE / "metadata" / name)

    summary = {
        "source_clips": len({row["clip_id"] for row in combined_rows}),
        "questions": len(combined_rows),
        "video_files": len(file_manifest),
        "real_questions": len(real_rows),
        "ai_generated_questions": len(ai_rows),
        "video_bytes": sum(row["size_bytes"] for row in file_manifest),
    }
    (RELEASE / "metadata" / "package_summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
