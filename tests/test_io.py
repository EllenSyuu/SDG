from pathlib import Path

import polars as pl
import pytest

from sdg4_revisions import io
from sdg4_revisions.config import Settings
from sdg4_revisions.synthetic import DISTRACTOR_SERIES
from sdg4_revisions.taxonomy import Taxonomy


@pytest.fixture(scope="module")
def panel(synthetic_settings: Settings, taxonomy: Taxonomy) -> pl.DataFrame:
    return io.build_panel(synthetic_settings, taxonomy)


def test_panel_contract(panel: pl.DataFrame) -> None:
    io.validate_panel(panel)  # schema, unique keys, no null keys, ISO3 shape
    assert set(panel["release"].unique()) == {2022, 2023, 2024, 2025}
    assert set(panel["source"].unique()) == {"admin", "hhs", "model"}


def test_mixed_header_case_is_normalised(synthetic_settings: Settings) -> None:
    headers = {
        (synthetic_settings.paths.raw_dir / f / io.DATA_FILE).read_text().splitlines()[0]
        for f in synthetic_settings.releases
    }
    assert len(headers) == 2  # the generator alternates upper/lower case headers


def test_unmapped_series_never_enter_the_panel(panel: pl.DataFrame) -> None:
    assert not set(DISTRACTOR_SERIES) & set(panel["series_id"].unique())


def test_missing_column_raises(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text("indicator_id,country_id,year\nX,ABC,2020\n")
    with pytest.raises(io.SchemaError):
        io.scan_release(path, 2025).collect()


def test_duplicate_keys_are_rejected(panel: pl.DataFrame) -> None:
    with pytest.raises(io.SchemaError):
        io.validate_panel(pl.concat([panel.head(3), panel.head(1)]))


def test_missing_release_has_actionable_error(tmp_path: Path, taxonomy: Taxonomy) -> None:
    settings = Settings.model_validate(
        {"releases": {"209909": 2099}, "paths": {"raw_dir": tmp_path}}
    )
    with pytest.raises(FileNotFoundError, match=r"docs/data\.md"):
        io.build_panel(settings, taxonomy)


def test_parquet_round_trip(panel: pl.DataFrame, synthetic_settings: Settings) -> None:
    io.write_panel(panel, synthetic_settings)
    assert io.read_panel(synthetic_settings).equals(panel)


def test_population_ignores_aggregates(synthetic_settings: Settings) -> None:
    assert synthetic_settings.paths.population_file is not None
    pop = io.read_population(synthetic_settings.paths.population_file)
    assert pop["country"].str.contains(r"^[A-Z]{3}$").all()
    assert pop.select(pl.struct("country", "year").is_unique().all()).item()
