# Video Hallucination Diagnosis (VHD)

## Version notice

The downloadable files on this Kaggle page are the **VHD pilot package**. The
pilot contains 385 source clips and 1,155 candidate questions built from
original, temporally reversed, and masked video stimuli.

The current paper, **Hallucination Risk Evaluation Framework for
Question-Answering in Video-Language Models**, reports **VHD v1.1.2**. That
version contains 801 human-adjudicated binary questions from 341 source clips:

- 333 visible-evidence questions;
- 178 prior-conflict questions; and
- 290 concealed-evidence questions.

The frozen v1.1.2 metadata, gold labels, grouped folds, attribution notices,
checksums, and standalone scorer are available from the
[VHD GitHub repository](https://github.com/transitional-ai/hallucinationdataset/tree/master/releases/v1.1.2-metadata-code).
The paper code and held-out evaluation results are available from the
[main project repository](https://github.com/sydney-machine-learning/video-hallucination-diagnosis).

The v1.1.2 archive does not include MP4 files. Forty-two derivatives from two
Internet Archive items are withheld because the archived source metadata names
an uploader but does not identify the original creator. They will not be
redistributed until the attribution is confirmed or the affected sources are
replaced.

## What the pilot package contains

The pilot package supports inspection of the dataset design and the annotation
workflow. Each source clip is paired with three stimulus conditions:

1. an original clip for visible-evidence questions;
2. a temporally reversed clip for prior-conflict questions; and
3. a masked clip for concealed-evidence questions.

The 1,155 pilot questions are candidate items. They must not be treated as the
801-question adjudicated v1.1.2 benchmark reported in the current paper.

## License and media terms

The project authors' original software and documentation are available under
the MIT License. This does not relicense third-party videos or source datasets.
Each media item remains subject to its original license and terms. Users should
review the source and attribution records before redistributing media.

## Citation

The final article citation will be added after publication. Until then, please
cite the dataset repository and identify the version used (pilot or v1.1.2).
