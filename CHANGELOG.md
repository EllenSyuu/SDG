# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Redesigned interactive explorer: indicator switcher, vintage curves with a release-by-
  release hover readout, one-year drift chart, release scrubber on the country × year
  matrix, net-change heat strip, revision dot plot and an in-browser ground-truth check.
- Animated hero (GIF, light and dark) and explorer screenshots in the README.
- `scripts/build_site.py`, used by CI and the Pages workflow.

## [0.1.0] — 2026-10-26

### Added
- Typed run configuration (`pydantic`) with portable, repo-relative paths.
- Regex indicator taxonomy for 12 SDG 4 indicators with admin / survey / model tags.
- Lazy Polars ingestion into a validated Parquet panel, normalising schema drift.
- Metrics: vintage curves, expanding and rolling (population-weighted) coverage, source
  layers, transition flows, series-level transition ledger, value revisions.
- Deterministic synthetic generator with a ledger of planted events.
- Figures in light and dark themes, social preview image, static explorer.
- `sdg4v` CLI: `run`, `demo`, `explorer`.
- Unit, property-based, contract, ground-truth and end-to-end tests; CI on Python
  3.11–3.13; on-demand GitHub Pages deployment of the explorer.
