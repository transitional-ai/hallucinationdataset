# Video Hallucination Diagnosis (VHD)

This repository contains the dataset documentation, annotation tools, and
evaluation utilities for VHD, the diagnostic dataset used in **Hallucination
Risk Evaluation Framework for Question-Answering in Video-Language Models**.

Related resources:

- [Main paper code and held-out results](https://github.com/sydney-machine-learning/video-hallucination-diagnosis)
- [Public Kaggle pilot package](https://www.kaggle.com/datasets/mlopssss/video-hallucination-diagnosis)
- [VHD v1.1.2 metadata and evaluation-code archive](releases/v1.1.2-metadata-code)

## Release status

Two VHD versions must be distinguished:

| Resource | Source clips | Questions | Purpose |
|---|---:|---:|---|
| Kaggle pilot package | 385 | 1,155 | Preliminary question development and annotation |
| VHD v1.1.2 | 341 | 801 | Human-adjudicated diagnostic set reported in the current paper |

The Kaggle files currently contain the earlier pilot package, with original,
temporally reversed, and masked stimuli for each source clip. They are useful
for inspecting the task design but are not the exact 801-question v1.1.2 set
reported in the paper.

The frozen v1.1.2 metadata and evaluation-code archive is included under
[`releases/v1.1.2-metadata-code`](releases/v1.1.2-metadata-code). It contains:

- 801 frozen binary VideoQA questions;
- 333 visible-evidence, 178 prior-conflict, and 290 concealed-evidence items;
- adjudicated gold labels and five grouped evaluation folds;
- frame-sampling and PDI control manifests;
- per-file provenance notices and SHA-256 inventories; and
- a standalone scoring program.

The archive does not include MP4 files. Forty-two derivatives from two Internet
Archive items remain withheld because the archived source metadata identifies
an uploader but not the creator. See the included dataset card and attribution
audit before redistributing any media.

## Pilot annotation files

The files in `metadata_examples/` belong to the earlier pilot workflow:

- `vhd_questions.csv` contains 1,155 candidate questions, including review
  decisions;
- `evaluation_manifest.csv` contains the 807 questions accepted in that pilot
  workflow.

These files preserve readable source-oriented identifiers for annotation and
tool demonstrations. They must not be substituted for the randomized
801-question v1.1.2 release manifest.

## Install the annotation tools

```bash
python -m pip install -r requirements.txt
```

For model inference, install the additional multimodal dependencies:

```bash
python -m pip install -r requirements_omni.txt
```

## Review question labels

The review application shows each video with its question and options and
writes the reviewed labels back to a CSV file. Copy the source CSV before
editing it:

```bash
cp metadata_examples/vhd_questions.csv reviewer_1.csv

python scripts/review_question_labels_app.py \
  --dataset-root /path/to/VHD_pilot_dataset \
  --csv reviewer_1.csv
```

On Windows PowerShell:

```powershell
Copy-Item metadata_examples\vhd_questions.csv reviewer_1.csv
python scripts\review_question_labels_app.py --dataset-root C:\path\to\VHD_pilot_dataset --csv reviewer_1.csv
```

The main review fields are `question_valid`, `final_correct_answer`,
`final_A_language_prior`, `final_A_vision`, and `final_uncertainty_label`.

## Run a video-language model on the pilot package

```bash
python scripts/run_model_responses.py \
  --model-key qwen \
  --dataset-root /path/to/VHD_pilot_dataset \
  --manifest metadata_examples/evaluation_manifest.csv \
  --output-dir outputs \
  --save-every 5
```

Supported model keys are:

```text
qwen      Qwen/Qwen2.5-Omni-3B
qwen7     Qwen/Qwen2.5-Omni-7B
minicpm   openbmb/MiniCPM-o-2_6
```

The runner requests only an answer choice for ordinary and prior-conflict
questions. Concealed-evidence questions additionally request an answer
confidence because confidence behavior is part of that diagnostic task. The
runner stores CSV checkpoints, a JSONL recovery ledger, model revision details,
parser status, and final scoring fields.

## Score VHD v1.1.2 responses

Prepare a CSV with at least these columns:

```text
question_id,model_id,selected_choice,parse_status
```

Then run:

```bash
python releases/v1.1.2-metadata-code/publication_release/score_vhd_release.py responses.csv \
  --release-dir releases/v1.1.2-metadata-code/publication_release \
  --output score_report.json
```

The scorer verifies the 801-item gold and group keys before reporting grouped
overall accuracy, task-specific accuracy, parse-failure rate, and the PDI
language-prior choice rate.

## Task design

VHD contains three related question types:

- **Visible-event control:** asks about evidence visible in the original clip.
- **Prior-conflict reversal:** tests whether the model follows reversed visual
  evidence instead of its usual event-order expectations.
- **Concealed evidence:** tests whether the model remains confident after key
  evidence has been hidden.

The example GIFs in `assets/gifs/` illustrate the three stimulus conditions.

## License and citation

The original software in this repository is released under the
[MIT License](LICENSE). That license does not apply to third-party videos,
benchmark media, or source datasets. Each media item remains governed by its
original license or media-use terms; the v1.1.2 archive records these terms in
`THIRD_PARTY_NOTICES.csv`.

Citation metadata for this repository is provided in [`CITATION.cff`](CITATION.cff).
The final article citation will be added after publication.
