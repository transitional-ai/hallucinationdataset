# VHD v1.1.2 publication-release staging files

This directory prepares the non-blind reproducibility deposit that will
accompany the TRACE paper.  It is separate from `../public/`, which remains
the frozen blind-evaluation input.  Do not give the files in this directory to
a model before its responses have been sealed.

Generated files:

- `THIRD_PARTY_NOTICES.csv`: one attribution and transformation notice for
  each of the 801 randomized release videos;
- `GOLD_LABELS.csv`: final adjudicated labels keyed only by randomized
  question ID;
- `GROUPS_AND_FOLDS.csv`: anonymous source-group IDs and the five official
  outer folds;
- `score_vhd_release.py`: standalone standard-library scorer;
- `ATTRIBUTION_AUDIT.json`: counts, authoritative terms links, caveats, and
  SHA-256 hashes.

The notices cover all 341 source clips.  Eight NASA source items recovered
after an interrupted download are matched by normalized NASA asset ID and
duration to the independently recorded verified-download manifest, which
supplies their collection and original-media URLs.

The remaining attribution caveat is explicit rather than silently filled:
the official Internet Archive metadata for `SmallWaterfall` and
`Yewenyi-atTheCampfire367` does not supply a creator.  Their 16 source clips
(42 derivative files) therefore identify the recorded uploader account as an
uploader, not as the creator.  Before redistributing those derivatives, the
authors should either obtain/record rights-holder confirmation or replace the
two source items and regenerate a scientifically versioned successor dataset.

This staging directory is not an archival deposit and has no DOI.  The final
deposit must include the frozen public manifests and videos, this directory,
the dataset card, checksums, and an immutable version identifier.
