from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from sdg4_revisions.config import Paths, Settings
from sdg4_revisions.io import PANEL_SCHEMA
from sdg4_revisions.synthetic import generate
from sdg4_revisions.taxonomy import Taxonomy, load_taxonomy

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def taxonomy() -> Taxonomy:
    return load_taxonomy(ROOT / "config" / "indicators.yaml")


def make_settings(tmp: Path, **overrides: object) -> Settings:
    paths = Paths(
        raw_dir=tmp / "raw",
        processed_dir=tmp / "processed",
        population_file=tmp / "raw" / "wpp" / "total_population_by_sex.csv",
        indicators_file=ROOT / "config" / "indicators.yaml",
        figures_dir=tmp / "figures",
        tables_dir=tmp / "tables",
    )
    base: dict[str, object] = {
        "paths": paths,
        "releases": {"202209": 2022, "202309": 2023, "202409": 2024, "202509": 2025},
    }
    base.update(overrides)
    return Settings.model_validate(base)


@pytest.fixture(scope="session")
def synthetic_settings(tmp_path_factory: pytest.TempPathFactory) -> Settings:
    tmp = tmp_path_factory.mktemp("synthetic")
    generate(tmp / "raw")
    return make_settings(tmp)


def panel_from_rows(rows: list[tuple[int, str, str, str, str, int, float | None]]) -> pl.DataFrame:
    """rows: (release, code, source, series_id, country, ref_year, value)."""
    return pl.DataFrame(rows, schema=list(PANEL_SCHEMA), orient="row").cast(
        PANEL_SCHEMA  # type: ignore[arg-type]
    )
