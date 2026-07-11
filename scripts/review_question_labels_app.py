import argparse
import csv
import shutil
import sys
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

import cv2
from PIL import Image, ImageTk


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV = ROOT / "hitl_real_question_review" / "real_question_reviewer_1.csv"
AI_REVIEW_DIR = ROOT / "hitl_question_review"

REQUIRED_FIELDS = [
    "question_valid",
    "final_correct_answer",
    "final_A_language_prior",
    "final_A_vision",
    "final_uncertainty_label",
]

CATEGORY_LABELS = {
    "fire_smoke_or_burning": "fire, smoke, or burning",
    "liquid_pouring_or_flow": "liquid pouring or flow",
    "falling_or_gravity": "falling or gravity-driven motion",
    "collision_or_impact": "collision or impact",
    "glass_breaking_or_fragments": "glass breaking or fragment motion",
    "deformation_or_melting": "deformation, melting, or shape change",
}

TASK_LABELS = {
    "accuracy": "Accuracy question",
    "vhd_i_pdi": "VHD-I reversed-video language-prior question",
    "vhd_ii_hce": "VHD-II masked-evidence uncertainty question",
}

STIMULUS_LABELS = {
    "original": "Original video",
    "reversed": "Reversed video",
    "masked": "Masked video",
}


def read_rows(csv_path: Path):
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    for field in REQUIRED_FIELDS:
        if field not in fieldnames:
            fieldnames.append(field)
        for row in rows:
            row.setdefault(field, "")
    return fieldnames, rows


def write_rows(csv_path: Path, fieldnames, rows):
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def video_path_for(row):
    return ROOT / row["stimulus_path"]


def is_complete(row):
    if row.get("question_valid", "").strip().lower() == "no":
        return True
    if row.get("question_valid", "").strip().lower() != "yes":
        return False
    if row.get("final_correct_answer", "").strip() not in {"A", "B"}:
        return False
    task = row.get("task", "")
    if task == "vhd_i_pdi":
        return (
            row.get("final_A_language_prior", "").strip() in {"A", "B"}
            and row.get("final_A_vision", "").strip() in {"A", "B"}
        )
    if task == "vhd_ii_hce":
        return bool(row.get("final_uncertainty_label", "").strip())
    return True


def label_or_raw(mapping, value):
    return mapping.get(value, value.replace("_", " ") if value else "")


def category_label(row):
    return label_or_raw(CATEGORY_LABELS, row.get("vhd_category", ""))


def display_text_for_row(row):
    return {
        "question": row.get("question_text", ""),
        "option_A": row.get("option_A", ""),
        "option_B": row.get("option_B", ""),
    }


def companion_ai_csv(csv_path: Path):
    if csv_path.parent.name != "hitl_real_question_review":
        return None
    name = csv_path.name.replace("real_question_", "question_", 1)
    candidate = AI_REVIEW_DIR / name
    return candidate if candidate.exists() else None


def preferred_start_index(rows):
    for idx, row in enumerate(rows):
        if row.get("clip_id", "").startswith("ai_") and not is_complete(row):
            return idx
    for idx, row in enumerate(rows):
        if not is_complete(row):
            return idx
    return 0


class QuestionReviewApp:
    def __init__(self, csv_path: Path):
        self.csv_path = csv_path
        self.sources = []
        self.rows = []
        self.add_source(csv_path)
        ai_csv = companion_ai_csv(csv_path)
        if ai_csv is not None:
            self.add_source(ai_csv)
        if not self.rows:
            raise RuntimeError(f"No rows found in {csv_path}")
        self.make_backup()

        self.index = self.first_ai_incomplete_index()
        self.cap = None
        self.playing = True
        self.frame_delay_ms = 40
        self.last_save = None
        self.current_image = None
        self.displayed_group = None
        self.group_notice_job = None

        self.root = tk.Tk()
        self.root.title("VHD Question Label Review")
        self.root.geometry("1280x900")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.build_ui()
        self.load_row(self.index)
        self.root.after(self.frame_delay_ms, self.update_video)

    def add_source(self, path: Path):
        fieldnames, rows = read_rows(path)
        start = len(self.rows)
        self.rows.extend(rows)
        self.sources.append(
            {
                "path": path,
                "fieldnames": fieldnames,
                "start": start,
                "end": len(self.rows),
            }
        )

    def make_backup(self):
        stamp = time.strftime("%Y%m%d_%H%M%S")
        for source in self.sources:
            path = source["path"]
            backup = path.with_suffix(path.suffix + f".bak_{stamp}")
            if not backup.exists():
                shutil.copy2(path, backup)

    def first_ai_incomplete_index(self):
        return preferred_start_index(self.rows)

    def build_ui(self):
        self.root.grid_columnconfigure(0, weight=3)
        self.root.grid_columnconfigure(1, weight=2)
        self.root.grid_rowconfigure(0, weight=1)

        left = tk.Frame(self.root, bg="#111111")
        left.grid(row=0, column=0, sticky="nsew")
        left.grid_rowconfigure(0, weight=1)
        left.grid_columnconfigure(0, weight=1)

        self.video_label = tk.Label(left, bg="#111111", fg="white", text="Loading video...")
        self.video_label.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)

        video_controls = tk.Frame(left, bg="#111111")
        video_controls.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))
        self.play_button = tk.Button(video_controls, text="Pause", command=self.toggle_play)
        self.play_button.pack(side="left")
        self.replay_button = tk.Button(video_controls, text="Replay", command=self.replay_video)
        self.replay_button.pack(side="left", padx=6)
        self.video_status = tk.Label(video_controls, bg="#111111", fg="white", text="")
        self.video_status.pack(side="left", padx=10)

        right = tk.Frame(self.root, padx=14, pady=12)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)

        self.group_notice = tk.Label(
            right,
            anchor="w",
            justify="left",
            wraplength=470,
            font=("Segoe UI", 12, "bold"),
            bg="#f0c36d",
            fg="#3b2a0a",
            padx=10,
            pady=8,
        )
        self.group_notice.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        self.progress_label = tk.Label(right, anchor="w", font=("Segoe UI", 12, "bold"))
        self.progress_label.grid(row=1, column=0, sticky="ew")

        self.meta_label = tk.Label(right, anchor="w", justify="left", wraplength=470, fg="#555555")
        self.meta_label.grid(row=2, column=0, sticky="ew", pady=(4, 10))

        self.question_label = tk.Label(
            right,
            anchor="w",
            justify="left",
            wraplength=470,
            font=("Segoe UI", 12),
        )
        self.question_label.grid(row=3, column=0, sticky="ew", pady=(4, 10))

        self.option_a_label = tk.Label(
            right,
            anchor="w",
            justify="left",
            wraplength=470,
            bg="#f3efe7",
            padx=8,
            pady=8,
        )
        self.option_a_label.grid(row=4, column=0, sticky="ew", pady=4)
        self.option_b_label = tk.Label(
            right,
            anchor="w",
            justify="left",
            wraplength=470,
            bg="#f3efe7",
            padx=8,
            pady=8,
        )
        self.option_b_label.grid(row=5, column=0, sticky="ew", pady=4)

        self.groups_frame = tk.Frame(right)
        self.groups_frame.grid(row=6, column=0, sticky="ew", pady=(14, 8))
        self.groups_frame.grid_columnconfigure(0, weight=1)

        self.group_widgets = {}
        self.make_button_group("question_valid", "1. Is this question valid?", [("yes", "Valid"), ("no", "Invalid")], 0)
        self.make_button_group("final_correct_answer", "2. Correct answer", [("A", "A"), ("B", "B")], 1)
        self.make_button_group(
            "final_A_language_prior",
            "3. Language-prior-consistent option",
            [("A", "A"), ("B", "B")],
            2,
        )
        self.make_button_group(
            "final_A_vision",
            "4. Vision-grounded option",
            [("A", "A"), ("B", "B")],
            3,
        )
        self.make_button_group(
            "final_uncertainty_label",
            "5. Should the answer express uncertainty?",
            [("uncertain", "Should be uncertain"), ("not_uncertain", "Need not be uncertain")],
            4,
        )

        nav = tk.Frame(right)
        nav.grid(row=7, column=0, sticky="ew", pady=(18, 6))
        tk.Button(nav, text="< Previous", command=self.prev_row, width=14).pack(side="left")
        tk.Button(nav, text="Next >", command=self.next_row, width=14).pack(side="left", padx=8)
        tk.Button(nav, text="Next incomplete", command=self.next_incomplete, width=16).pack(side="left")

        save_row = tk.Frame(right)
        save_row.grid(row=8, column=0, sticky="ew", pady=6)
        tk.Button(save_row, text="Save now", command=self.save, width=14).pack(side="left")
        self.save_label = tk.Label(save_row, text="", fg="#555555")
        self.save_label.pack(side="left", padx=10)

        hint = (
            "Only fields needed for the current task are shown. No blank option is used. "
            "Fields unrelated to the current task are automatically left empty in the CSV."
        )
        self.hint_label = tk.Label(right, anchor="w", justify="left", wraplength=470, fg="#666666", text=hint)
        self.hint_label.grid(row=9, column=0, sticky="ew", pady=(12, 0))

    def make_button_group(self, field, title, options, row_index):
        frame = tk.LabelFrame(self.groups_frame, text=title, padx=8, pady=8)
        frame.grid(row=row_index, column=0, sticky="ew", pady=5)
        buttons = []
        for value, label in options:
            button = tk.Button(frame, text=label, width=20, command=lambda f=field, v=value: self.set_value(f, v))
            button.pack(side="left", padx=4)
            buttons.append((value, button))
        self.group_widgets[field] = {"frame": frame, "buttons": buttons}

    def current_row(self):
        return self.rows[self.index]

    def load_row(self, index):
        self.save()
        self.index = max(0, min(index, len(self.rows) - 1))
        row = self.current_row()
        display = display_text_for_row(row)
        self.update_group_notice(row)

        self.progress_label.config(text=f"Question {self.index + 1} / {len(self.rows)}")
        complete = "complete" if is_complete(row) else "incomplete"
        self.meta_label.config(
            text=(
                f"{row.get('question_id', '')}\n"
                f"Video: {row.get('clip_id', '')} | Category: {category_label(row)}\n"
                f"Task: {label_or_raw(TASK_LABELS, row.get('task', ''))} | "
                f"Stimulus: {label_or_raw(STIMULUS_LABELS, row.get('stimulus_type', ''))} | Status: {complete}"
            )
        )
        self.question_label.config(text=f"Question:\n{display['question']}")
        self.option_a_label.config(text=f"A. {display['option_A']}")
        self.option_b_label.config(text=f"B. {display['option_B']}")

        self.configure_visible_groups()
        self.refresh_button_styles()
        self.open_video(video_path_for(row))

    def update_group_notice(self, row):
        group_id = row.get("clip_id", "") or "unknown"
        source = "AI-generated" if group_id.startswith("ai_") else "Real"
        group_changed = self.displayed_group != group_id
        self.displayed_group = group_id
        self.group_notice.config(
            text=f"{'NEW VIDEO GROUP - ' if group_changed else ''}{source}: {group_id}\n"
            "Original / Reversed / Masked",
            bg="#f0c36d" if group_changed else "#eee6d8",
        )
        if self.group_notice_job is not None:
            self.root.after_cancel(self.group_notice_job)
        if group_changed:
            self.group_notice_job = self.root.after(2500, self.end_group_highlight)

    def end_group_highlight(self):
        self.group_notice.config(bg="#eee6d8")
        self.group_notice_job = None

    def configure_visible_groups(self):
        row = self.current_row()
        task = row.get("task", "")
        visible = {
            "question_valid": True,
            "final_correct_answer": True,
            "final_A_language_prior": task == "vhd_i_pdi",
            "final_A_vision": task == "vhd_i_pdi",
            "final_uncertainty_label": task == "vhd_ii_hce",
        }
        for field, widgets in self.group_widgets.items():
            if visible[field]:
                widgets["frame"].grid()
            else:
                widgets["frame"].grid_remove()
                row[field] = ""

    def refresh_button_styles(self):
        row = self.current_row()
        for field, widgets in self.group_widgets.items():
            current = row.get(field, "").strip()
            for value, button in widgets["buttons"]:
                if current == value:
                    button.config(relief="sunken", bg="#a8d5ba")
                else:
                    button.config(relief="raised", bg="SystemButtonFace")

    def set_value(self, field, value):
        row = self.current_row()
        row[field] = value
        if field == "question_valid" and value == "no":
            row["final_correct_answer"] = ""
            row["final_A_language_prior"] = ""
            row["final_A_vision"] = ""
            row["final_uncertainty_label"] = ""
        self.refresh_button_styles()
        self.save()

    def open_video(self, path: Path):
        if self.cap is not None:
            self.cap.release()
        self.cap = None
        self.video_status.config(text=str(path.relative_to(ROOT)) if path.exists() else f"Missing video: {path}")
        if not path.exists():
            self.video_label.config(image="", text="Video file not found")
            return
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            self.video_label.config(image="", text="Could not open video")
            return
        self.cap = cap
        self.playing = True
        self.play_button.config(text="Pause")
        self.show_next_frame()

    def show_next_frame(self):
        if self.cap is None:
            return
        ok, frame = self.cap.read()
        if not ok:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = self.cap.read()
            if not ok:
                self.video_label.config(image="", text="No readable video frame")
                return
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(frame)
        image.thumbnail((860, 650), Image.Resampling.LANCZOS)
        self.current_image = ImageTk.PhotoImage(image)
        self.video_label.config(image=self.current_image, text="")

    def update_video(self):
        if self.playing:
            self.show_next_frame()
        self.root.after(self.frame_delay_ms, self.update_video)

    def toggle_play(self):
        self.playing = not self.playing
        self.play_button.config(text="Pause" if self.playing else "Play")

    def replay_video(self):
        if self.cap is not None:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            self.playing = True
            self.play_button.config(text="Pause")

    def save(self):
        if hasattr(self, "rows"):
            for source in self.sources:
                write_rows(
                    source["path"],
                    source["fieldnames"],
                    self.rows[source["start"] : source["end"]],
                )
            self.last_save = time.strftime("%H:%M:%S")
            if hasattr(self, "save_label"):
                self.save_label.config(text=f"Saved {self.last_save}")

    def prev_row(self):
        self.load_row(self.index - 1)

    def next_row(self):
        self.load_row(self.index + 1)

    def next_incomplete(self):
        for offset in range(1, len(self.rows) + 1):
            idx = (self.index + offset) % len(self.rows)
            if not is_complete(self.rows[idx]):
                self.load_row(idx)
                return
        messagebox.showinfo("Complete", "No incomplete questions remain.")

    def on_close(self):
        self.save()
        if self.cap is not None:
            self.cap.release()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def self_test(csv_path: Path, max_videos: int):
    fieldnames, rows = read_rows(csv_path)
    errors = []
    real_count = len(rows)
    ai_csv = companion_ai_csv(csv_path)
    if ai_csv is not None:
        _, ai_rows = read_rows(ai_csv)
        rows.extend(ai_rows)
    if not rows:
        errors.append("CSV has no rows")
    for field in REQUIRED_FIELDS:
        if field not in fieldnames:
            errors.append(f"missing required field: {field}")
    test_rows = rows[:max_videos]
    if len(rows) > real_count:
        test_rows += rows[real_count : real_count + max_videos]
    for idx, row in enumerate(test_rows, start=1):
        path = video_path_for(row)
        if not path.exists():
            errors.append(f"missing video row {idx}: {path}")
            continue
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            errors.append(f"cannot open video row {idx}: {path}")
            continue
        ok, frame = cap.read()
        cap.release()
        if not ok or frame is None:
            errors.append(f"cannot read first frame row {idx}: {path}")
            continue
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        Image.fromarray(frame).thumbnail((860, 650), Image.Resampling.LANCZOS)
        display = display_text_for_row(row)
        if not display["question"] or not display["option_A"] or not display["option_B"]:
            errors.append(f"empty display text row {idx}: {row.get('question_id', '')}")

    group_counts = {}
    for row in rows:
        group_id = row.get("clip_id", "")
        group_counts[group_id] = group_counts.get(group_id, 0) + 1
    malformed_groups = {group: count for group, count in group_counts.items() if not group or count != 3}
    if malformed_groups:
        errors.append(f"video groups must contain three questions: {malformed_groups}")

    start_index = preferred_start_index(rows)
    if len(rows) > real_count and start_index < real_count:
        errors.append(f"startup did not select AI questions: row {start_index + 1}")

    tmp = csv_path.with_suffix(csv_path.suffix + ".selftest_tmp")
    shutil.copy2(csv_path, tmp)
    tmp_fields, tmp_rows = read_rows(tmp)
    if tmp_rows:
        tmp_rows[0]["question_valid"] = tmp_rows[0].get("question_valid", "") or "yes"
    write_rows(tmp, tmp_fields, tmp_rows)
    tmp.unlink(missing_ok=True)

    if errors:
        print("SELF_TEST_FAILED")
        for error in errors:
            print(error)
        return 1
    print("SELF_TEST_PASSED")
    print(f"csv={csv_path}")
    print(f"rows={len(rows)}")
    print(f"startup_question={start_index + 1}")
    print(f"startup_clip={rows[start_index].get('clip_id', '')}")
    print(f"video_groups={len(group_counts)}")
    print(f"videos_tested={len(test_rows)}")
    print("csv_save_test=passed")
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default=str(DEFAULT_CSV))
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--max-test-videos", type=int, default=30)
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.is_absolute():
        csv_path = (Path.cwd() / csv_path).resolve()
    if not csv_path.exists():
        raise FileNotFoundError(csv_path)

    if args.self_test:
        raise SystemExit(self_test(csv_path, args.max_test_videos))

    app = QuestionReviewApp(csv_path)
    app.run()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
