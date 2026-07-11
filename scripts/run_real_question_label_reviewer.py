import argparse
import csv
import os
import shutil
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

import cv2
from PIL import Image, ImageTk


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REVIEW_CSV = ROOT / "hitl_real_question_review" / "real_question_reviewer_1.csv"

REQUIRED_FIELDS = [
    "question_valid",
    "final_correct_answer",
    "final_A_language_prior",
    "final_A_vision",
    "final_uncertainty_label",
]


def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return reader.fieldnames or [], list(reader)


def write_csv(path: Path, fields, rows):
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)


def non_empty(value):
    return bool((value or "").strip())


def row_complete(row):
    if row.get("question_valid", "").strip().lower() == "no":
        return True
    if row.get("question_valid", "").strip().lower() != "yes":
        return False
    if not non_empty(row.get("final_correct_answer")):
        return False
    task = row.get("task", "")
    if task == "vhd_i_pdi":
        return non_empty(row.get("final_A_language_prior")) and non_empty(row.get("final_A_vision"))
    if task == "vhd_ii_hce":
        return non_empty(row.get("final_uncertainty_label"))
    return True


class ReviewerApp:
    def __init__(self, review_csv: Path):
        self.review_csv = review_csv
        self.fields, self.rows = read_csv(review_csv)
        for field in REQUIRED_FIELDS:
            if field not in self.fields:
                self.fields.append(field)
                for row in self.rows:
                    row[field] = ""

        if "reviewer_notes" in self.fields:
            self.fields = [field for field in self.fields if field != "reviewer_notes"]
            for row in self.rows:
                row.pop("reviewer_notes", None)
            self.save()

        backup = review_csv.with_suffix(".before_tk_review_backup.csv")
        if not backup.exists():
            shutil.copy2(review_csv, backup)

        self.index = self.first_unfinished_index()

        self.root = tk.Tk()
        self.root.title(f"VHD Question Label Reviewer - {review_csv.name}")
        self.root.geometry("1120x780")

        self.question_valid = tk.StringVar()
        self.correct_answer = tk.StringVar()
        self.language_prior = tk.StringVar()
        self.vision_answer = tk.StringVar()
        self.uncertainty_label = tk.StringVar()

        self.status_var = tk.StringVar()
        self.meta_var = tk.StringVar()
        self.path_var = tk.StringVar()
        self.question_var = tk.StringVar()
        self.option_a_var = tk.StringVar()
        self.option_b_var = tk.StringVar()
        self.draft_var = tk.StringVar()
        self.video_status_var = tk.StringVar()
        self.cap = None
        self.video_job = None
        self.video_photo = None
        self.video_paused = False

        self.build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.load_row()

    def first_unfinished_index(self):
        for i, row in enumerate(self.rows):
            if not row_complete(row):
                return i
        return 0

    def build_ui(self):
        pad = {"padx": 12, "pady": 6}

        top = tk.Frame(self.root)
        top.pack(fill="x", **pad)
        tk.Button(top, text="Previous", command=self.previous_row, width=12).pack(side="left")
        tk.Button(top, text="Next unfinished", command=self.next_unfinished, width=16).pack(side="left", padx=8)
        tk.Button(top, text="Next", command=self.next_row, width=12).pack(side="left")
        tk.Button(top, text="Save", command=self.save, width=12).pack(side="left", padx=8)
        tk.Label(top, textvariable=self.status_var, anchor="e").pack(side="right")

        tk.Label(self.root, textvariable=self.meta_var, font=("Segoe UI", 11, "bold"), anchor="w").pack(fill="x", **pad)
        tk.Label(self.root, textvariable=self.path_var, font=("Consolas", 9), anchor="w", wraplength=1060).pack(fill="x", **pad)

        video_frame = tk.LabelFrame(self.root, text="Video")
        video_frame.pack(fill="x", **pad)
        self.video_label = tk.Label(video_frame, bg="black", width=96, height=24)
        self.video_label.pack(fill="both", expand=True, padx=10, pady=8)
        video_bar = tk.Frame(video_frame)
        video_bar.pack(fill="x", padx=10, pady=(0, 8))
        tk.Button(video_bar, text="Pause / Play", command=self.toggle_video, width=14).pack(side="left")
        tk.Button(video_bar, text="Restart", command=self.restart_video, width=12).pack(side="left", padx=8)
        tk.Button(video_bar, text="Open External Player", command=self.open_video, width=20).pack(side="left")
        tk.Button(video_bar, text="Open Video Folder", command=self.open_video_folder, width=18).pack(side="left", padx=8)
        tk.Label(video_bar, textvariable=self.video_status_var, anchor="w", fg="#7a4b2d").pack(side="left", padx=12)

        question_frame = tk.LabelFrame(self.root, text="Question")
        question_frame.pack(fill="x", **pad)
        tk.Label(question_frame, textvariable=self.question_var, wraplength=1040, justify="left", font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=10, pady=8)
        tk.Label(question_frame, textvariable=self.option_a_var, wraplength=1040, justify="left", font=("Segoe UI", 12)).pack(anchor="w", padx=10, pady=4)
        tk.Label(question_frame, textvariable=self.option_b_var, wraplength=1040, justify="left", font=("Segoe UI", 12)).pack(anchor="w", padx=10, pady=4)
        tk.Label(question_frame, textvariable=self.draft_var, wraplength=1040, justify="left", font=("Segoe UI", 9), fg="#555").pack(anchor="w", padx=10, pady=8)

        valid_frame = tk.LabelFrame(self.root, text="1. Is this question valid?")
        valid_frame.pack(fill="x", **pad)
        tk.Radiobutton(valid_frame, text="Yes", value="yes", variable=self.question_valid, command=self.on_valid_change).pack(side="left", padx=12)
        tk.Radiobutton(valid_frame, text="No", value="no", variable=self.question_valid, command=self.on_valid_change).pack(side="left", padx=12)

        correct_frame = tk.LabelFrame(self.root, text="2. Correct answer")
        correct_frame.pack(fill="x", **pad)
        tk.Radiobutton(correct_frame, text="Option A", value="A", variable=self.correct_answer).pack(side="left", padx=12)
        tk.Radiobutton(correct_frame, text="Option B", value="B", variable=self.correct_answer).pack(side="left", padx=12)

        pdi_frame = tk.LabelFrame(self.root, text="3. PDI labels, only for vhd_i_pdi")
        pdi_frame.pack(fill="x", **pad)
        tk.Label(pdi_frame, text="Language-prior option:").pack(side="left", padx=(12, 4))
        tk.Radiobutton(pdi_frame, text="A", value="A", variable=self.language_prior).pack(side="left")
        tk.Radiobutton(pdi_frame, text="B", value="B", variable=self.language_prior).pack(side="left", padx=(0, 18))
        tk.Label(pdi_frame, text="Vision-consistent option:").pack(side="left", padx=(12, 4))
        tk.Radiobutton(pdi_frame, text="A", value="A", variable=self.vision_answer).pack(side="left")
        tk.Radiobutton(pdi_frame, text="B", value="B", variable=self.vision_answer).pack(side="left")

        hce_frame = tk.LabelFrame(self.root, text="4. HCE uncertainty label, only for vhd_ii_hce")
        hce_frame.pack(fill="x", **pad)
        tk.Radiobutton(hce_frame, text="uncertain", value="uncertain", variable=self.uncertainty_label).pack(side="left", padx=12)
        tk.Radiobutton(hce_frame, text="not_uncertain", value="not_uncertain", variable=self.uncertainty_label).pack(side="left", padx=12)

        action = tk.Frame(self.root)
        action.pack(fill="x", **pad)
        tk.Button(action, text="Use draft labels", command=self.use_draft, width=18).pack(side="left")
        tk.Button(action, text="Save and Next", command=self.save_and_next, width=18).pack(side="left", padx=8)
        tk.Button(action, text="Mark invalid and Next", command=self.mark_invalid_and_next, width=20).pack(side="left")

        help_text = (
            "No blank choice is shown. Fields that do not apply to the current task are automatically left empty in the CSV. "
            "Use question_valid=no only when the question cannot be answered or its labels cannot be defined."
        )
        tk.Label(self.root, text=help_text, wraplength=1040, justify="left", fg="#444").pack(fill="x", **pad)

    def current_row(self):
        return self.rows[self.index]

    def load_row(self):
        if not self.rows:
            messagebox.showerror("No rows", f"No rows found in {self.review_csv}")
            self.root.destroy()
            return
        row = self.current_row()
        total = len(self.rows)
        completed = sum(1 for item in self.rows if row_complete(item))
        self.status_var.set(f"Row {self.index + 1}/{total} | completed {completed}/{total}")
        self.meta_var.set(
            f"{row.get('question_id')} | clip={row.get('clip_id')} | {row.get('vhd_category')} | task={row.get('task')} | stimulus={row.get('stimulus_type')}"
        )
        self.path_var.set(str(ROOT / row.get("stimulus_path", "")))
        self.question_var.set(row.get("question_text", ""))
        self.option_a_var.set(f"A. {row.get('option_A', '')}")
        self.option_b_var.set(f"B. {row.get('option_B', '')}")
        self.draft_var.set(
            "Draft labels: "
            f"correct={row.get('draft_correct_answer', '') or 'n/a'}, "
            f"language_prior={row.get('draft_A_language_prior', '') or 'n/a'}, "
            f"vision={row.get('draft_A_vision', '') or 'n/a'}, "
            f"uncertainty={row.get('draft_uncertainty_label', '') or 'n/a'}"
        )

        self.question_valid.set(row.get("question_valid", ""))
        self.correct_answer.set(row.get("final_correct_answer", ""))
        self.language_prior.set(row.get("final_A_language_prior", ""))
        self.vision_answer.set(row.get("final_A_vision", ""))
        self.uncertainty_label.set(row.get("final_uncertainty_label", ""))
        self.clear_irrelevant_fields()
        self.load_video()

    def clear_irrelevant_fields(self):
        task = self.current_row().get("task", "")
        if task != "vhd_i_pdi":
            self.language_prior.set("")
            self.vision_answer.set("")
        if task != "vhd_ii_hce":
            self.uncertainty_label.set("")

    def on_valid_change(self):
        if self.question_valid.get() == "no":
            self.correct_answer.set("")
            self.language_prior.set("")
            self.vision_answer.set("")
            self.uncertainty_label.set("")

    def apply_vars_to_row(self):
        row = self.current_row()
        row["question_valid"] = self.question_valid.get()
        if row["question_valid"] == "no":
            row["final_correct_answer"] = ""
            row["final_A_language_prior"] = ""
            row["final_A_vision"] = ""
            row["final_uncertainty_label"] = ""
            return
        row["final_correct_answer"] = self.correct_answer.get()
        row["final_A_language_prior"] = self.language_prior.get() if row.get("task") == "vhd_i_pdi" else ""
        row["final_A_vision"] = self.vision_answer.get() if row.get("task") == "vhd_i_pdi" else ""
        row["final_uncertainty_label"] = self.uncertainty_label.get() if row.get("task") == "vhd_ii_hce" else ""

    def save(self):
        self.apply_vars_to_row()
        write_csv(self.review_csv, self.fields, self.rows)
        self.load_row()

    def validate_current_selection(self):
        self.apply_vars_to_row()
        row = self.current_row()
        if row.get("question_valid") == "no":
            return True
        if row.get("question_valid") != "yes":
            messagebox.showwarning("Missing label", "Choose whether the question is valid.")
            return False
        if not row.get("final_correct_answer"):
            messagebox.showwarning("Missing label", "Choose the correct answer.")
            return False
        if row.get("task") == "vhd_i_pdi" and (not row.get("final_A_language_prior") or not row.get("final_A_vision")):
            messagebox.showwarning("Missing label", "Choose both language-prior and vision-consistent options for PDI.")
            return False
        if row.get("task") == "vhd_ii_hce" and not row.get("final_uncertainty_label"):
            messagebox.showwarning("Missing label", "Choose an uncertainty label for HCE.")
            return False
        return True

    def save_and_next(self):
        if not self.validate_current_selection():
            return
        write_csv(self.review_csv, self.fields, self.rows)
        self.next_row()

    def mark_invalid_and_next(self):
        self.question_valid.set("no")
        self.apply_vars_to_row()
        write_csv(self.review_csv, self.fields, self.rows)
        self.next_row()

    def use_draft(self):
        row = self.current_row()
        self.question_valid.set("yes")
        self.correct_answer.set(row.get("draft_correct_answer", ""))
        if row.get("task") == "vhd_i_pdi":
            self.language_prior.set(row.get("draft_A_language_prior", ""))
            self.vision_answer.set(row.get("draft_A_vision", ""))
        else:
            self.language_prior.set("")
            self.vision_answer.set("")
        if row.get("task") == "vhd_ii_hce":
            self.uncertainty_label.set(row.get("draft_uncertainty_label", "") or "uncertain")
        else:
            self.uncertainty_label.set("")

    def open_video(self):
        path = ROOT / self.current_row().get("stimulus_path", "")
        if not path.exists():
            messagebox.showerror("Missing video", str(path))
            return
        os.startfile(path)

    def open_video_folder(self):
        path = ROOT / self.current_row().get("stimulus_path", "")
        folder = path.parent
        if not folder.exists():
            messagebox.showerror("Missing folder", str(folder))
            return
        os.startfile(folder)

    def stop_video(self):
        if self.video_job is not None:
            try:
                self.root.after_cancel(self.video_job)
            except Exception:
                pass
            self.video_job = None
        if self.cap is not None:
            self.cap.release()
            self.cap = None

    def load_video(self):
        self.stop_video()
        self.video_photo = None
        self.video_label.configure(image="", text="")
        path = ROOT / self.current_row().get("stimulus_path", "")
        if not path.exists():
            self.video_status_var.set(f"Missing video: {path}")
            self.video_label.configure(text="Missing video", fg="white", bg="black")
            return
        self.cap = cv2.VideoCapture(str(path))
        if not self.cap.isOpened():
            self.video_status_var.set("OpenCV could not open this video. Use external player.")
            self.video_label.configure(text="Video open failed. Use external player.", fg="white", bg="black")
            self.cap = None
            return
        self.video_paused = False
        self.video_status_var.set("Playing")
        self.update_video_frame()

    def update_video_frame(self):
        if self.cap is None or self.video_paused:
            return
        ok, frame = self.cap.read()
        if not ok:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = self.cap.read()
        if not ok:
            self.video_status_var.set("Frame decode failed. Use external player.")
            return

        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(frame)
        image.thumbnail((900, 360), Image.Resampling.LANCZOS)
        self.video_photo = ImageTk.PhotoImage(image)
        self.video_label.configure(image=self.video_photo, text="")

        fps = self.cap.get(cv2.CAP_PROP_FPS) or 24
        delay = max(15, int(1000 / fps))
        self.video_job = self.root.after(delay, self.update_video_frame)

    def toggle_video(self):
        if self.cap is None:
            self.load_video()
            return
        self.video_paused = not self.video_paused
        if self.video_paused:
            self.video_status_var.set("Paused")
            if self.video_job is not None:
                self.root.after_cancel(self.video_job)
                self.video_job = None
        else:
            self.video_status_var.set("Playing")
            self.update_video_frame()

    def restart_video(self):
        if self.cap is None:
            self.load_video()
            return
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        self.video_paused = False
        self.video_status_var.set("Playing")
        self.update_video_frame()

    def on_close(self):
        self.stop_video()
        self.apply_vars_to_row()
        write_csv(self.review_csv, self.fields, self.rows)
        self.root.destroy()

    def previous_row(self):
        self.save()
        self.index = max(0, self.index - 1)
        self.load_row()

    def next_row(self):
        self.index = min(len(self.rows) - 1, self.index + 1)
        self.load_row()

    def next_unfinished(self):
        self.save()
        for offset in range(1, len(self.rows) + 1):
            candidate = (self.index + offset) % len(self.rows)
            if not row_complete(self.rows[candidate]):
                self.index = candidate
                self.load_row()
                return
        messagebox.showinfo("Complete", "No unfinished rows found.")

    def run(self):
        self.root.mainloop()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--review-csv", default=str(DEFAULT_REVIEW_CSV))
    args = parser.parse_args()
    review_csv = Path(args.review_csv)
    if not review_csv.exists():
        print(f"Missing review CSV: {review_csv}", file=sys.stderr)
        raise SystemExit(1)
    ReviewerApp(review_csv).run()


if __name__ == "__main__":
    main()
