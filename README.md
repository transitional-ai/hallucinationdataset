# Video Hallucination Diagnosis Dataset Tools

This repository contains the code used to prepare, label, and export the Video
Hallucination Diagnosis (VHD) dataset metadata. The video files are not stored
in this GitHub repository.

## Dataset Videos

Download the video files from Kaggle:

https://www.kaggle.com/datasets/mlopssss/video-hallucination-diagnosis

After downloading, place the extracted dataset so that paths such as the
following are available:

```text
VHD_pilot_dataset/videos/real/original/...
VHD_pilot_dataset/videos/real/reversed/...
VHD_pilot_dataset/videos/real/masked/...
VHD_pilot_dataset/videos/ai_generated/original/...
VHD_pilot_dataset/videos/ai_generated/reversed/...
VHD_pilot_dataset/videos/ai_generated/masked/...
```

## Repository Contents

```text
scripts/
  Human-in-the-loop question labelling tools.
  Review package builders.
  Adjudication scripts.
  Dataset manifest assembly and release scripts.

metadata_examples/
  Example CSV and JSON files showing the expected output format.

assets/gifs/
  Small visual examples showing original, reversed, and masked fire clips.
```

## Labelling Workflow

The dataset uses a human-in-the-loop workflow:

1. Prepare candidate video clips and metadata.
2. Generate question-review CSV files.
3. Review each question with the video shown beside the answer options.
4. Save the reviewer choices directly to CSV.
5. Resolve disagreements or invalid items during adjudication.
6. Assemble the final benchmark manifest.

The main GUI scripts are:

```text
scripts/review_question_labels_app.py
scripts/run_question_labeling_app.py
scripts/run_real_question_label_app.py
```

The adjudication scripts are:

```text
scripts/adjudicate_real_question_reviews.py
scripts/adjudicate_ai_question_reviews.py
```

The final manifest assembly scripts are:

```text
scripts/assemble_final_real_benchmark_manifest.py
scripts/assemble_final_ai_benchmark_manifest.py
scripts/build_dataset_release_package.py
```

## Visual Examples

The examples below show the same real fire clip under the three VHD conditions.

### Original

![Original fire clip](assets/gifs/fireoriginal.gif)

### Temporally Reversed

![Reversed fire clip](assets/gifs/firereversed.gif)

### Masked

![Masked fire clip](assets/gifs/firemasked.gif)

The original clip supports ordinary accuracy questions. The reversed clip is
used to test whether a model follows visible temporal evidence rather than an
ordinary forward event pattern. The masked clip is used to test whether a model
expresses uncertainty when key visual evidence is hidden.

## Notes

- This repository is intended for dataset construction and annotation tooling.
- Large video files should be downloaded from Kaggle rather than committed to
  GitHub.
- The CSV files in `metadata_examples/` are examples of the expected structure.
  They can be replaced by the latest exported metadata after running the full
  dataset preparation pipeline.
