"""Exact expectations on hand-built panels, plus property-based invariants."""

from pathlib import Path

import polars as pl
from hypothesis import given
from hypothesis import settings as hsettings
from hypothesis import strategies as st

from sdg4_revisions import analysis as A
from sdg4_revisions.config import Eligibility, Settings

from .conftest import make_settings, panel_from_rows

R2, R3 = 2022, 2023


def tiny_settings(**kw: object) -> Settings:
    return make_settings(
        Path("/unused"),
        releases={"202209": R2, "202309": R3},
        reference_start=2018,
        reference_end=2023,
        lookback_years=2,
        **kw,
    )


# Release 2022 sees ABC for 2019-2020; release 2023 backfills DEF 2019 and ABC 2021
# (eligible in 2022 but late), retracts ABC 2019 and revises ABC 2020.
ROWS = [
    (R2, "4.1.4", "admin", "ROFST.1.CP", "ABC", 2019, 10.0),
    (R2, "4.1.4", "admin", "ROFST.1.CP", "ABC", 2020, 11.0),
    (R2, "4.1.4", "admin", "ROFST.1.CP", "ABC", 2022, 99.0),  # not eligible in 2022 (strict)
    (R3, "4.1.4", "admin", "ROFST.1.CP", "ABC", 2020, 12.5),
    (R3, "4.1.4", "admin", "ROFST.1.CP", "ABC", 2021, 13.0),
    (R3, "4.1.4", "hhs", "ROFST.H.1", "DEF", 2019, 20.0),
    (R3, "4.1.4", "admin", "ROFST.1.CP", "GHI", 2020, None),  # null value: not an observation
]


def test_observations_apply_eligibility_and_drop_nulls() -> None:
    obs = A.observations(panel_from_rows(ROWS), tiny_settings())
    assert obs.height == 5
    assert obs.filter(pl.col("ref_year") == 2022).is_empty()
    assert obs.filter(pl.col("country") == "GHI").is_empty()


def test_inclusive_eligibility_keeps_current_year() -> None:
    obs = A.observations(panel_from_rows(ROWS), tiny_settings(eligibility=Eligibility.INCLUSIVE))
    assert obs.filter(pl.col("ref_year") == 2022).height == 1


def test_vintage_curves_include_zero_cells() -> None:
    s = tiny_settings()
    curves = A.vintage_curves(A.observations(panel_from_rows(ROWS), s), s)
    got = {(r, y): n for r, _, y, n in curves.iter_rows()}
    assert got[(R2, 2018)] == 0 and got[(R2, 2019)] == 1 and got[(R2, 2021)] == 0
    assert got[(R3, 2019)] == 1 and got[(R3, 2020)] == 1 and got[(R3, 2021)] == 1
    assert (R2, 2022) not in got  # ineligible cells are absent, not zero


def test_expanding_coverage() -> None:
    s = tiny_settings()
    exp = A.expanding_coverage(A.observations(panel_from_rows(ROWS), s), s)
    assert dict(exp.select("release", "n_countries").iter_rows()) == {R2: 1, R3: 2}


def test_transition_flows_count_backfill_and_retraction_only() -> None:
    s = tiny_settings()
    flows = A.transition_flows(A.observations(panel_from_rows(ROWS), s), s)
    by_year = {row["ref_year"]: row for row in flows.to_dicts()}
    assert by_year[2019]["added"] == 1 and by_year[2019]["dropped"] == 1  # DEF in, ABC out
    assert by_year[2020]["retained"] == 1
    assert by_year[2021]["added"] == 1  # eligible in 2022 but late: lagged backfill
    assert 2022 not in by_year  # first eligible in 2023: a new arrival, not a revision
    summary = A.transition_summary(flows).row(0, named=True)
    assert (summary["added"], summary["dropped"], summary["net"]) == (2, 1, 1)


def test_value_revisions() -> None:
    s = tiny_settings()
    rev = A.value_revisions(panel_from_rows(ROWS), s).row(0, named=True)
    assert rev["n_pairs"] == 1  # only ABC-2020 is published in both releases
    assert rev["share_revised"] == 1.0
    assert rev["median_abs_revision"] == 1.5


def test_rolling_coverage_and_population_share() -> None:
    s = tiny_settings()
    obs = A.observations(panel_from_rows(ROWS), s)
    pop = pl.DataFrame(
        {
            "country": ["ABC", "DEF", "XYZ"],
            "year": [2020, 2020, 2020],
            "population": [10.0, 30.0, 60.0],
        }
    ).cast({"year": pl.Int16})
    roll = A.rolling_coverage(obs, s, pop)
    row = roll.filter((pl.col("release") == R3) & (pl.col("anchor_year") == 2020)).row(
        0, named=True
    )
    assert row["n_countries"] == 2  # ABC (2020) + DEF (2019) within a 2-year window
    assert row["population_share"] == 0.4
    assert roll.filter(pl.col("anchor_year") == 2021)["population_share"].is_null().all()


def test_source_layers_are_cumulative() -> None:
    s = tiny_settings()
    layers = A.source_layers(panel_from_rows(ROWS), s).filter(pl.col("release") == R3)
    assert dict(layers.select("layer", "n_countries").iter_rows()) == {
        "admin": 1,
        "+ hhs": 2,
        "+ model": 2,
    }


# --------------------------------------------------------------------------- properties

cells = st.lists(
    st.tuples(
        st.sampled_from([R2, R3]),
        st.sampled_from(["AAA", "BBB", "CCC", "DDD"]),
        st.integers(2018, 2023),
        st.sampled_from(["admin", "hhs"]),
    ),
    min_size=1,
    max_size=60,
)


def _panel(draw: list[tuple[int, str, int, str]]) -> pl.DataFrame:
    rows = {(r, "4.1.4", src, f"S.{src}", c, y, 1.0) for r, c, y, src in draw}
    return panel_from_rows(sorted(rows))


@hsettings(max_examples=60, deadline=None)
@given(cells)
def test_expanding_dominates_every_single_year(draw: list[tuple[int, str, int, str]]) -> None:
    s = tiny_settings()
    obs = A.observations(_panel(draw), s)
    exp = dict(A.expanding_coverage(obs, s).select("release", "n_countries").iter_rows())
    for release, _, _, n in A.vintage_curves(obs, s).iter_rows():
        assert n <= exp.get(release, 0)


@hsettings(max_examples=60, deadline=None)
@given(cells)
def test_rolling_dominates_point_in_time(draw: list[tuple[int, str, int, str]]) -> None:
    s = tiny_settings()
    obs = A.observations(_panel(draw), s)
    point = {(r, y): n for r, _, y, n in A.vintage_curves(obs, s).iter_rows()}
    for r, _, y, n in (
        A.rolling_coverage(obs, s)
        .select("release", "code", "anchor_year", "n_countries")
        .iter_rows()
    ):
        assert n >= point[(r, y)]


@hsettings(max_examples=60, deadline=None)
@given(cells)
def test_flows_conserve_cells(draw: list[tuple[int, str, int, str]]) -> None:
    """old + added - dropped == new, over reference years eligible in the old release."""
    s = tiny_settings()
    obs = A.observations(_panel(draw), s)
    flows = A.transition_flows(obs, s)
    common = obs.filter(pl.col("ref_year") <= s.eligibility.last_reference_year(R2))
    old = common.filter(pl.col("release") == R2).height
    new = common.filter(pl.col("release") == R3).height
    assert old + flows["added"].sum() - flows["dropped"].sum() == new
