# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed
- Project renamed to **SDG 4 Data Revision Tracker** (distribution `sdg4-revision-tracker`,
  import package `sdg4_revisions`, CLI `sdg4-revisions`).
- Licence changed from MIT to Apache-2.0; added `NOTICE`.
- CI actions updated to current major versions; Dependabot removed to keep a single branch.

### Added
- Every README figure is now an animated GIF (light and dark): releases draw in one
  after another, bars grow per transition, revision dots appear per transition, and the
  ground-truth check drops recovered counts onto the planted bars. Static PNGs are kept
  alongside. Shared `plots.animate` renders any figure at a given progress and writes an
  optimised, palette-quantised GIF that holds on the finished chart.
- Figures redesigned for README reading width: 10-inch layouts, 11–19 pt type, stacked
  panels, constrained layout; new per-indicator "what each release changed" chart with
  clipped outliers; every README image shown full width.
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
- `sdg4-revisions` CLI: `run`, `demo`, `explorer`.
- Unit, property-based, contract, ground-truth and end-to-end tests; CI on Python
  3.11–3.13; on-demand GitHub Pages deployment of the explorer.
