# VHD v1.1.2 dataset card

## Release status

VHD v1.1.2 is a frozen, human-adjudicated diagnostic benchmark for confidence
and hallucination analysis in multiple-choice VideoQA.  This directory is the
blind evaluation package prepared for controlled review.  It is **not yet an
attribution-complete public deposit**: third-party media attribution must be
completed and the gold package must be deposited at an immutable location
before the dataset is described as publicly available.

The current release supersedes v1.1.1.  Its manifests were frozen on
2026-07-17 before the first final evaluation rerun.  Randomized question IDs,
media filenames, and manifest order reduce accidental leakage from the source
organization.

## Intended task and motivation

VHD targets reliability failures around visually grounded physical events.  It
contains three complementary question types:

- **Accuracy:** factual questions on visible video evidence;
- **Prior-dependence intervention (PDI):** questions for which a temporally
  reversed view tests whether a language prior overrides changed evidence;
- **Hallucination under concealed evidence (HCE):** questions in which a masked
  view hides diagnostic evidence and probes unsupported confidence.

The benchmark is intended for model evaluation, failure prediction, selective
prediction, confidence calibration, and mechanism analysis.  It is not a
general video-understanding training corpus, a safety certification, or a
measure of human intelligence.

## Composition

- 801 human-adjudicated binary questions;
- 341 indivisible source clips;
- 245 licensed real-world clips and 96 VideoPhy-2 AI-generated clips;
- 333 accuracy, 178 PDI, and 290 HCE questions;
- six physical-event categories;
- silent evaluation with a fixed 16-frame sampling policy.

Category coverage by source clip is:

| Category | Clips |
|---|---:|
| Collision or impact | 56 |
| Deformation or melting | 57 |
| Falling or gravity | 41 |
| Fire, smoke, or burning | 36 |
| Glass breaking or fragments | 43 |
| Liquid pouring or flow | 108 |
| **Total** | **341** |

The release contains five deterministic outer folds with 67, 67, 67, 67, and
73 source clips.  All questions and derived views associated with a source
clip remain in the same fold.  Evaluation and resampling must group on the
source clip rather than treating related questions or transformations as
independent observations.

## Sources and licensing

The 341 source clips comprise 120 Internet Archive clips, 59 NASA Image and
Video Library clips, 66 Wikimedia Commons clips, and 96 VideoPhy-2 clips.  The
source-level license families are 117 CC BY, 35 CC BY-SA, 34 CC0 or
public-domain declarations, 59 NASA media-use declarations, and 96 VideoPhy-2
clips under its recorded MIT source license.

Third-party media retain their original licenses and terms.  Inclusion in VHD
does not relicense those works.  A final deposit must include a per-file
`THIRD_PARTY_NOTICES.csv` giving the original title, verified creator, source
page, license and license URL, and derivative transformation.  Sixteen
Internet Archive CC BY records still require creator verification, so the
current media directory must not be redistributed as an attribution-complete
public dataset.

## Annotation and quality control

Questions and labels were reviewed and disagreements were adjudicated before
v1.1.2 was frozen.  Before adjudication, agreement statistics were:

| Field | Paired items | Raw agreement | Cohen's kappa |
|---|---:|---:|---:|
| Question validity | 1,155 | 0.977 | 0.945 |
| Correct answer | 807 | 0.895 | 0.789 |
| PDI language-prior answer | 183 | 0.896 | 0.792 |
| PDI vision-grounded answer | 183 | 0.896 | 0.792 |
| HCE uncertainty label | 290 | 0.900 | 0.794 |

Counts in this table describe the pre-adjudication comparison pool and may
exceed final-release counts.  Final evaluation uses only the 801 adjudicated
questions in the frozen release manifest.

## Files and evaluation protocol

The blind package contains:

- `blind_evaluation_manifest.csv`;
- `frame_sampling_manifest.csv`;
- `pdi_control_manifest.csv`;
- `pdi_control_frame_plan.csv`;
- 801 randomized MP4 evaluation files under `videos/`.

Gold labels, randomized-to-source mappings, and scoring keys are private in the
blind package.  They must be released separately with scoring code for final
paper reproducibility, or governed by an explicit embargo and archival-deposit
policy.  Private files must never be copied under the blind `public/`
directory.

## Known limitations

- VHD is small relative to broad public VideoQA benchmarks and concentrates on
  six physical-event families.
- Source and license availability shaped clip selection, especially for real
  videos, and liquid-flow events are overrepresented.
- AI-generated clips originate from one source dataset and do not span the
  full generator population.
- Binary answer structure and fixed silent 16-frame evaluation do not cover
  open-ended generation, audio reasoning, dense temporal localization, or
  arbitrary frame budgets.
- PDI and HCE are author-designed diagnostics.  Strong performance on them is
  not evidence of guaranteed calibration or safety under every deployment
  shift.
- Multiple questions or views can share a source clip; analyses that ignore
  clip grouping will understate uncertainty.

## Ethical and responsible use considerations

VHD is designed to study model behavior, not to infer attributes of people.
Users should retain original source attribution, avoid identity or sensitive
attribute inference, inspect the original media terms before redistribution,
and report aggregate results without exposing blind keys.  The benchmark does
not authorize uses prohibited by the original media licenses or NASA media-use
guidelines.

## Versioning and integrity

Release metadata and SHA-256 values are recorded in
`../release_metadata.json` and the release checksum inventories.  Results
should cite the exact VHD version and immutable archival identifier.  Until a
DOI or equivalent deposit exists, manuscripts should state that the
attribution-complete artifact, labels, folds, and evaluation code will be
deposited with the accepted paper, rather than claiming current public
availability.
