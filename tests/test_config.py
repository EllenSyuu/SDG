from pathlib import Path

import pytest
from pydantic import ValidationError

from sdg4vintage.config import Eligibility, Settings, load_settings

ROOT = Path(__file__).resolve().parents[1]


def test_default_config_loads_and_resolves_paths() -> None:
    settings = load_settings(ROOT / "config" / "default.yaml")
    assert settings.release_years == [2022, 2023, 2024, 2025]
    assert settings.paths.raw_dir == ROOT / "data" / "raw"
    assert settings.paths.indicators_file.exists()


def test_releases_are_sorted_by_year() -> None:
    settings = Settings(releases={"202509": 2025, "202209": 2022})
    assert list(settings.releases) == ["202209", "202509"]


@pytest.mark.parametrize(
    "bad",
    [
        {"releases": {}},
        {"releases": {"a": 2022, "b": 2022}},
        {"releases": {"a": 2022}, "reference_start": 2020, "reference_end": 2010},
        {"releases": {"a": 2022}, "lookback_years": 0},
    ],
)
def test_invalid_settings_are_rejected(bad: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate(bad)


def test_eligibility_rule() -> None:
    assert Eligibility.STRICT.last_reference_year(2025) == 2024
    assert Eligibility.INCLUSIVE.last_reference_year(2025) == 2025
