"""Typed run configuration.

Every analysis parameter that the original exploratory scripts hard-coded (paths,
release list, reference window, eligibility rule, lookback length) lives in one
validated object, loaded from YAML. Paths are resolved relative to the config file,
so the same config works on any machine.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Eligibility(StrEnum):
    """Which reference years a release can be expected to contain.

    ``strict``    -- reference year < release year (a September release cannot hold
                     the current school year).
    ``inclusive`` -- reference year <= release year.
    """

    STRICT = "strict"
    INCLUSIVE = "inclusive"

    def last_reference_year(self, release_year: int) -> int:
        return release_year - 1 if self is Eligibility.STRICT else release_year


class Paths(BaseModel):
    model_config = ConfigDict(frozen=True)

    raw_dir: Path = Path("data/raw")
    processed_dir: Path = Path("data/processed")
    population_file: Path | None = Path("data/raw/wpp/total_population_by_sex.csv")
    indicators_file: Path = Path("config/indicators.yaml")
    figures_dir: Path = Path("reports/figures")
    tables_dir: Path = Path("reports/tables")


class Settings(BaseModel):
    """Validated settings for one pipeline run."""

    model_config = ConfigDict(frozen=True)

    paths: Paths = Field(default_factory=Paths)
    releases: dict[str, int] = Field(
        description="Release folder name (e.g. '202509') -> release year (e.g. 2025)."
    )
    reference_start: int = 2008
    reference_end: int = 2025
    eligibility: Eligibility = Eligibility.STRICT
    lookback_years: int = Field(default=5, ge=1, le=20)
    revision_tolerance: float = Field(
        default=1e-3,
        ge=0,
        description="Absolute change at or below which a value counts as unrevised "
        "(absorbs float noise from publication rounding).",
    )

    @field_validator("releases")
    @classmethod
    def _releases_sorted_unique(cls, value: dict[str, int]) -> dict[str, int]:
        if not value:
            raise ValueError("at least one release is required")
        years = list(value.values())
        if len(set(years)) != len(years):
            raise ValueError("two release folders map to the same release year")
        return dict(sorted(value.items(), key=lambda item: item[1]))

    @model_validator(mode="after")
    def _window_is_valid(self) -> Self:
        if self.reference_start > self.reference_end:
            raise ValueError("reference_start must be <= reference_end")
        return self

    @property
    def release_years(self) -> list[int]:
        return list(self.releases.values())

    @property
    def reference_years(self) -> list[int]:
        return list(range(self.reference_start, self.reference_end + 1))

    def resolve(self, base: Path) -> Settings:
        """Return a copy whose relative paths are anchored at ``base``."""
        resolved = {
            name: (base / value) if isinstance(value, Path) and not value.is_absolute() else value
            for name, value in self.paths.model_dump().items()
        }
        return self.model_copy(update={"paths": Paths(**resolved)})


def load_settings(path: str | Path) -> Settings:
    """Load settings from YAML; relative paths resolve against the repository root
    (the parent of the ``config/`` folder) when the file lives in ``config/``."""
    path = Path(path).resolve()
    with path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    base = path.parent.parent if path.parent.name == "config" else path.parent
    return Settings.model_validate(raw).resolve(base)
