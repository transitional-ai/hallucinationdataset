# VHD v1.1.2 metadata and evaluation-code archive

## Release scope

This archive is the non-media, non-blind companion to VHD v1.1.2. It enables
inspection of the frozen question manifests, adjudicated labels, official
group/fold structure, third-party provenance notices, checksums, and scoring
code without redistributing any video file.

The archive contains:

- 801 frozen binary VideoQA questions across accuracy, prior-dependence
  intervention (PDI), and hallucination-under-concealed-evidence (HCE) tasks;
- 801 adjudicated gold-label rows;
- 801 anonymous source-group/fold rows covering 341 indivisible source clips;
- 801 third-party attribution and transformation notices;
- the frozen frame-sampling and PDI control manifests;
- a standalone standard-library scoring program;
- dataset card, release metadata, and SHA-256 inventories.

It intentionally excludes:

- all MP4 files and original source media;
- randomized-to-source private mappings;
- private scoring keys other than the publication gold-label table;
- credentials, uploader email addresses, or local filesystem paths.

## Important availability boundary

This archive does **not** make the complete media benchmark publicly
downloadable. The official Internet Archive metadata for `SmallWaterfall` and
`Yewenyi-atTheCampfire367` supplies a CC BY license and uploader account but no
creator field. These two items contribute 16 source clips and 42 VHD
derivatives. The derivatives are therefore withheld from public
redistribution until the authors obtain and record rights-holder confirmation
or replace the two items in a scientifically versioned successor release.

The remaining provenance notices are included for transparency, but users
must follow each source's original license or media-use terms. Inclusion of a
notice does not relicense a third-party work.

## Scoring

Prepare a response CSV with at least:

```text
question_id,model_id,selected_choice,parse_status
```

Then run from the archive root:

```bash
python publication_release/score_vhd_release.py responses.csv \
  --release-dir publication_release \
  --output score_report.json
```

The scorer verifies the 801-item gold/group key and reports grouped overall
accuracy, task-specific accuracy, parse-failure rate, and the PDI
language-prior choice rate.

## Versioning and citation

- Dataset version: 1.1.2.
- Frozen before the first final evaluation rerun: 2026-07-17.
- Media files changed by this archive: no.
- Questions, labels, or folds changed by this archive: no.

Before public deposit, the authors must complete the creator list, affiliation,
ORCID fields, repository license selection, and immutable DOI in
`DEPOSIT_METADATA_TEMPLATE.json`. Until a DOI exists, cite the version and
state that the metadata/code archive is prepared for deposit; do not claim
that the complete VHD media are already public.

