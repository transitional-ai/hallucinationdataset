import csv
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_csv(name):
    with (ROOT / name).open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def main():
    videos = read_csv("video_manifest.csv")
    questions = read_csv("question_bank.csv")
    print("Dataset:", ROOT)
    print("Videos:", len(videos))
    print("Questions:", len(questions))
    print("By VHD task:", dict(Counter(v["vhd_task"] for v in videos)))
    print("By source type:", dict(Counter(v["source_type"] for v in videos)))
    print("By length bucket:", dict(Counter(v["length_bucket"] for v in videos)))
    print("By category:", dict(Counter(v["category"] for v in videos)))


if __name__ == "__main__":
    main()
