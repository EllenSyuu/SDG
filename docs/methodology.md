# Methodology

## The question

International education statistics are published as **releases**: periodically a new
snapshot of an SDG 4 database replaces the previous one. Each snapshot does three things at
once:

1. it adds the newest reference years;
2. it **backfills** older reference years with values that arrived late;
3. it **revises or withdraws** values that were published before.

Most users only ever see the latest snapshot, so these three effects are invisible.
That matters for anyone who reads a trend, a coverage statistic or a progress
assessment off a single release: part of what looks like change in the world is change
in the data. This project measures that second kind of change directly, the same way
macroeconomists study real-time GDP vintages.

## Units

| Term | Definition |
|---|---|
| Release *R* | One published snapshot (folder `YYYYMM`, release year *R*). |
| Reference year *y* | The year a value describes. |
| Series | One series identifier, e.g. `ROFST.1.F.CP` (out-of-school rate, primary, female, admin). |
| Indicator | An SDG code (e.g. 4.1.4): the union of its series, see `config/indicators.yaml`. |
| Observation | (release, indicator, country, *y*) such that **at least one** series of the indicator has a non-null value. |
| Eligible | *y* ≤ last eligible year of *R*: *R* − 1 under the default `strict` rule (a September release cannot hold the school year that has just started), *R* under `inclusive`. |

All metrics are computed on eligible cells only, inside the window
`reference_start`–`reference_end` (2008–2025 by default).

## Metrics

**Vintage curve.** For each release and indicator, the number of countries with an
observation in each reference year. Overlaying releases shows the *reporting-lag sag* at
the right edge of each curve and how later releases lift it.

**Expanding coverage.** Countries with at least one observation anywhere in
[`reference_start`, last eligible year of *R*]: "has this country *ever* produced a value
for this indicator, as of this release?"

**Rolling coverage.** Countries with an observation in the *L* years ending at an anchor
year (`lookback_years`, default 5), plus the same set weighted by population: covered
population ÷ population of all countries in the UN WPP file, same year. Anchor years
outside the population file get a null share, never a silently wrong one.

**Source layers.** Expanding coverage recomputed with sources stacked —
administrative only, + household surveys, + modelled estimates — to show which
countries are reached only through surveys or models.

**Transition flows.** For consecutive releases *R₀ → R₁* and each indicator, every
country-year that is eligible *in R₀* is classified:

| Class | In *R₀* | In *R₁* | Reading |
|---|---|---|---|
| retained | ✓ | ✓ | stable |
| added | – | ✓ | backfill: arrived late |
| dropped | ✓ | – | withdrawn |

Reference years that first become eligible in *R₁* are excluded, so the normal
arrival of a new year is never counted as a revision. Conservation is tested as a
property: `|R₀| + added − dropped = |R₁|` over the common window
(`tests/test_analysis.py::test_flows_conserve_cells`).
*Churn* = (added + dropped) / (retained + dropped).

**Value revisions.** At series level (the finest published grain), every
(series, country, *y*) with a value in both *R₀* and *R₁* is compared. A change of
more than `revision_tolerance` (0.001, i.e. above the noise of publication rounding)
counts as a revision; the share revised and the median / 90th-percentile absolute
revision of revised values are reported.

## Design choices and their alternatives

* **Presence, not value, defines coverage.** A country "covers" an indicator in a year
  if *any* constituent series (any education level, sex or source) has a value. This
  matches how availability is usually communicated; a stricter "headline series only"
  definition is a one-line change to the taxonomy.
* **Null values are not observations.** Rows the release carries without a number do
  not count towards coverage.
* **Rule-based taxonomy instead of a lookup table.** Series are mapped by regular
  expressions over their identifiers, so the mapping is reviewable in one screen,
  versionable, and testable (known series, near misses and ambiguity are all covered
  in `tests/test_taxonomy.py`).
* **Release comparison is pairwise and consecutive.** Comparing every release with the
  latest one ("final vintage") is the other standard design; it is a small extension
  of `transition_flows` and is listed in the roadmap.

## Limitations

* The code is release-agnostic: adding a release is a line in the config. Metrics on
  consecutive transitions need at least two releases.
* A revision can be a correction, a methodological change, a new population
  denominator, or a re-based model run; the metrics measure *that* values changed,
  not *why*. Metadata files shipped with each release could be joined in for that.
* Population shares use one WPP vintage for every release, so they isolate changes in
  coverage from changes in population estimates.
