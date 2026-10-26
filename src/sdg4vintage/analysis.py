"""Vintage analytics on the tidy panel.

Vocabulary (borrowed from real-time macroeconomic data analysis):

* **release / vintage** -- one published snapshot of the database (e.g. Sept 2025).
* **reference year**    -- the school/fiscal year a value describes.
* **eligible**          -- a reference year a release could be expected to contain
                           (see :class:`~sdg4vintage.config.Eligibility`).
* **observation**       -- a (release, indicator, country, reference year) cell for
                           which at least one constituent series has a value.

All functions are pure: panel in, tidy ``polars.DataFrame`` out.
"""

from __future__ import annotations

from collections.abc import Iterable
from itertools import pairwise

import polars as pl

from sdg4vintage.config import Settings

OBS_KEYS = ["release", "code", "country", "ref_year"]


# --------------------------------------------------------------------------- building blocks


def last_eligible_year(settings: Settings) -> pl.Expr:
    """Expression: last eligible reference year for the row's release."""
    offset = 1 if settings.eligibility.value == "strict" else 0
    return pl.min_horizontal(pl.col("release") - offset, pl.lit(settings.reference_end))


def observations(
    panel: pl.DataFrame, settings: Settings, sources: Iterable[str] | None = None
) -> pl.DataFrame:
    """Distinct eligible observations, optionally restricted to some sources."""
    frame = panel.filter(pl.col("value").is_not_null())
    if sources is not None:
        frame = frame.filter(pl.col("source").is_in(list(sources)))
    return (
        frame.filter(
            pl.col("ref_year").is_between(settings.reference_start, last_eligible_year(settings))
        )
        .select(OBS_KEYS)
        .unique()
        .sort(OBS_KEYS)
    )


def _grid(obs: pl.DataFrame, settings: Settings) -> pl.DataFrame:
    """All (release, code, ref_year) cells that are eligible, so zero counts survive."""
    codes = obs.select("code").unique()
    releases = pl.DataFrame({"release": settings.release_years}, schema={"release": pl.Int16})
    years = pl.DataFrame({"ref_year": settings.reference_years}, schema={"ref_year": pl.Int16})
    return (
        releases.join(codes, how="cross")
        .join(years, how="cross")
        .filter(pl.col("ref_year") <= last_eligible_year(settings))
    )


# --------------------------------------------------------------------------- coverage


def vintage_curves(obs: pl.DataFrame, settings: Settings) -> pl.DataFrame:
    """Countries reporting each reference year, as seen by each release.

    Plotting one line per release gives the classic 'vintage curve': the right-hand
    end of each curve sags (reporting lag), and later releases lift earlier years
    (backfilling).
    """
    counts = obs.group_by(["release", "code", "ref_year"]).agg(
        pl.col("country").n_unique().alias("n_countries")
    )
    return (
        _grid(obs, settings)
        .join(counts, on=["release", "code", "ref_year"], how="left")
        .with_columns(pl.col("n_countries").fill_null(0).cast(pl.Int32))
        .sort(["code", "release", "ref_year"])
    )


def expanding_coverage(obs: pl.DataFrame, settings: Settings) -> pl.DataFrame:
    """Countries with at least one observation anywhere in the eligible window."""
    counts = obs.group_by(["release", "code"]).agg(
        pl.col("country").n_unique().alias("n_countries")
    )
    grid = _grid(obs, settings).select("release", "code").unique()
    return (
        grid.join(counts, on=["release", "code"], how="left")
        .with_columns(
            pl.col("n_countries").fill_null(0).cast(pl.Int32),
            pl.lit(settings.reference_start).alias("window_start"),
            last_eligible_year(settings).alias("window_end"),
        )
        .sort(["code", "release"])
    )


def rolling_country_sets(obs: pl.DataFrame, settings: Settings) -> pl.DataFrame:
    """(release, code, anchor_year, country): country reported in [anchor-L+1, anchor]."""
    window = settings.lookback_years
    offsets = pl.DataFrame({"k": list(range(window))}, schema={"k": pl.Int16})
    return (
        obs.join(offsets, how="cross")
        .with_columns((pl.col("ref_year") + pl.col("k")).alias("anchor_year"))
        .filter(pl.col("anchor_year") <= last_eligible_year(settings))
        .select("release", "code", "anchor_year", "country")
        .unique()
    )


def rolling_coverage(
    obs: pl.DataFrame, settings: Settings, population: pl.DataFrame | None = None
) -> pl.DataFrame:
    """Countries (and optionally share of world population) covered by a rolling
    ``lookback_years`` window ending at each anchor year."""
    sets = rolling_country_sets(obs, settings)
    grid = _grid(obs, settings).rename({"ref_year": "anchor_year"})
    counts = sets.group_by(["release", "code", "anchor_year"]).agg(
        pl.col("country").n_unique().alias("n_countries")
    )
    out = grid.join(counts, on=["release", "code", "anchor_year"], how="left").with_columns(
        pl.col("n_countries").fill_null(0).cast(pl.Int32)
    )
    if population is not None:
        out = out.join(
            population_share(sets, population), on=["release", "code", "anchor_year"], how="left"
        )
    return out.sort(["code", "release", "anchor_year"])


def population_share(sets: pl.DataFrame, population: pl.DataFrame) -> pl.DataFrame:
    """Covered population / population of all countries in the WPP file, same year.

    Anchor years outside the population file's range get a null share rather than a
    silently wrong one.
    """
    pop = population.rename({"year": "anchor_year"})
    totals = pop.group_by("anchor_year").agg(pl.col("population").sum().alias("world"))
    covered = (
        sets.join(pop, on=["country", "anchor_year"], how="inner")
        .group_by(["release", "code", "anchor_year"])
        .agg(pl.col("population").sum().alias("covered"))
    )
    keys = sets.select("release", "code", "anchor_year").unique()
    return (
        keys.join(covered, on=["release", "code", "anchor_year"], how="left")
        .join(totals, on="anchor_year", how="left")
        .with_columns(
            pl.when(pl.col("world").is_not_null())
            .then(pl.col("covered").fill_null(0) / pl.col("world"))
            .otherwise(None)
            .alias("population_share")
        )
        .select("release", "code", "anchor_year", "population_share")
    )


def source_layers(panel: pl.DataFrame, settings: Settings) -> pl.DataFrame:
    """Expanding coverage as sources are stacked: admin -> +hhs -> +model."""
    layers = {"admin": ["admin"], "+ hhs": ["admin", "hhs"], "+ model": ["admin", "hhs", "model"]}
    frames = []
    for order, (layer, sources) in enumerate(layers.items()):
        obs = observations(panel, settings, sources)
        if obs.is_empty():
            continue
        frames.append(
            expanding_coverage(obs, settings).with_columns(
                pl.lit(layer).alias("layer"), pl.lit(order).alias("layer_order")
            )
        )
    return pl.concat(frames).sort(["code", "layer_order", "release"]).drop("layer_order")


# --------------------------------------------------------------------------- revisions


def _transitions(settings: Settings) -> list[tuple[int, int]]:
    years = settings.release_years
    return list(pairwise(years))


def _count(condition: pl.Expr) -> pl.Expr:
    return condition.fill_null(False).sum().cast(pl.Int64)


def transition_flows(obs: pl.DataFrame, settings: Settings) -> pl.DataFrame:
    """Country-year cells added, dropped or retained between consecutive releases.

    Only reference years eligible in *both* releases are compared, so the natural
    arrival of a new reference year is never counted as an 'addition'.
    """
    frames = []
    for before, after in _transitions(settings):
        old = obs.filter(pl.col("release") == before).drop("release")
        new = obs.filter(pl.col("release") == after).drop("release")
        keys = ["code", "country", "ref_year"]
        joined = old.with_columns(pl.lit(True).alias("in_old")).join(
            new.with_columns(pl.lit(True).alias("in_new")), on=keys, how="full", coalesce=True
        )
        frames.append(
            joined.filter(pl.col("ref_year") <= settings.eligibility.last_reference_year(before))
            .group_by(["code", "ref_year"])
            .agg(
                _count(pl.col("in_new") & pl.col("in_old").is_null()).alias("added"),
                _count(pl.col("in_old") & pl.col("in_new").is_null()).alias("dropped"),
                _count(pl.col("in_old") & pl.col("in_new")).alias("retained"),
            )
            .with_columns(
                pl.lit(before, dtype=pl.Int16).alias("from_release"),
                pl.lit(after, dtype=pl.Int16).alias("to_release"),
            )
        )
    flows = pl.concat(frames).with_columns(
        (pl.col("added") - pl.col("dropped")).alias("net"),
    )
    return flows.select(
        "code", "from_release", "to_release", "ref_year", "added", "dropped", "retained", "net"
    ).sort(["code", "from_release", "ref_year"])


def transition_summary(flows: pl.DataFrame) -> pl.DataFrame:
    """Per indicator and release transition: totals and churn rate."""
    return (
        flows.group_by(["code", "from_release", "to_release"])
        .agg(pl.col("added", "dropped", "retained", "net").sum())
        .with_columns(
            (
                (pl.col("added") + pl.col("dropped"))
                / (pl.col("retained") + pl.col("dropped")).clip(lower_bound=1)
            ).alias("churn_rate")
        )
        .sort(["code", "from_release"])
    )


def value_revisions(panel: pl.DataFrame, settings: Settings) -> pl.DataFrame:
    """How often, and by how much, a published value changes in the next release.

    Compared at series level (the finest published grain) for values present in both
    releases, then summarised per indicator and transition.
    """
    keys = ["series_id", "country", "ref_year"]
    frames = []
    for before, after in _transitions(settings):
        old = panel.filter((pl.col("release") == before) & pl.col("value").is_not_null())
        new = panel.filter((pl.col("release") == after) & pl.col("value").is_not_null())
        pairs = old.select([*keys, "code", pl.col("value").alias("v0")]).join(
            new.select([*keys, pl.col("value").alias("v1")]), on=keys, how="inner"
        )
        frames.append(
            pairs.with_columns(
                (pl.col("v1") - pl.col("v0")).abs().alias("abs_rev"),
                pl.lit(before, dtype=pl.Int16).alias("from_release"),
                pl.lit(after, dtype=pl.Int16).alias("to_release"),
            )
        )
    tol = settings.revision_tolerance
    revisions = pl.concat(frames)
    revised = pl.col("abs_rev").filter(pl.col("abs_rev") > tol)
    return (
        revisions.group_by(["code", "from_release", "to_release"])
        .agg(
            pl.len().alias("n_pairs"),
            (pl.col("abs_rev") > tol).mean().alias("share_revised"),
            revised.median().alias("median_abs_revision"),
            revised.quantile(0.9).alias("p90_abs_revision"),
        )
        .sort(["code", "from_release"])
    )


def series_transitions(panel: pl.DataFrame, settings: Settings) -> pl.DataFrame:
    """Series-level ledger for each consecutive transition.

    Cells are (series, country, reference year) with a published value, restricted to
    reference years eligible in the earlier release. Each cell is exactly one of
    *retained*, *backfilled* (new in the later release) or *retracted* (gone from it);
    retained cells whose value moved by more than ``revision_tolerance`` are *revised*.
    This is the grain at which the synthetic generator plants events, so the two can be
    compared exactly (see ``tests/test_ground_truth.py``).
    """
    keys = ["series_id", "country", "ref_year"]
    tol = settings.revision_tolerance
    rows = []
    for before, after in _transitions(settings):
        last = settings.eligibility.last_reference_year(before)

        def cells(release: int, name: str, last: int = last) -> pl.DataFrame:
            return panel.filter(
                (pl.col("release") == release)
                & pl.col("value").is_not_null()
                & pl.col("ref_year").is_between(settings.reference_start, last)
            ).select([*keys, pl.col("value").alias(name)])

        joined = cells(before, "v0").join(cells(after, "v1"), on=keys, how="full", coalesce=True)
        both = pl.col("v0").is_not_null() & pl.col("v1").is_not_null()
        counts = joined.select(
            _count(both).alias("retained"),
            _count(pl.col("v0").is_null()).alias("backfilled"),
            _count(pl.col("v1").is_null()).alias("retracted"),
            _count(both & ((pl.col("v1") - pl.col("v0")).abs() > tol)).alias("revised"),
        ).row(0, named=True)
        rows.append({"from_release": before, "to_release": after, **counts})
    return pl.DataFrame(rows).cast({"from_release": pl.Int16, "to_release": pl.Int16})


# --------------------------------------------------------------------------- matrices


def reporting_matrix(obs: pl.DataFrame, code: str, release: int) -> pl.DataFrame:
    """Country x reference-year 0/1 matrix for one indicator and release."""
    cells = obs.filter((pl.col("code") == code) & (pl.col("release") == release))
    if cells.is_empty():
        return pl.DataFrame({"country": []}, schema={"country": pl.String})
    return (
        cells.with_columns(pl.lit(1, dtype=pl.Int8).alias("reported"))
        .pivot(on="ref_year", index="country", values="reported", sort_columns=True)
        .fill_null(0)
        .sort("country")
    )
