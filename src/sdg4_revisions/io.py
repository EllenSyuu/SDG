"""Ingestion: release files -> one tidy, typed vintage panel.

Each release is one ``SDG_DATA_NATIONAL.csv`` (layout: docs/data.md). Releases differ in small but
breaking ways (upper- vs lower-case headers, empty strings vs nulls), so every file
passes through one normalisation function before anything else touches it.

The panel is the single contract between ingestion and analysis::

    release   Int16   release year the row was published in
    code      String  SDG indicator code (from the taxonomy)
    source    String  admin | hhs | model
    series_id String  series identifier (upper-case)
    country   String  ISO3 country code
    ref_year  Int16   reference year the value describes
    value     Float64 published value (null if the release published no number)

Files are scanned lazily with Polars and filtered to the taxonomy's series before
materialising, so peak memory is a fraction of the raw file size.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

from sdg4_revisions.config import Settings
from sdg4_revisions.taxonomy import Taxonomy

DATA_FILE = "SDG_DATA_NATIONAL.csv"
REQUIRED_COLUMNS = ("indicator_id", "country_id", "year", "value")

PANEL_SCHEMA: dict[str, pl.DataType] = {
    "release": pl.Int16(),
    "code": pl.String(),
    "source": pl.String(),
    "series_id": pl.String(),
    "country": pl.String(),
    "ref_year": pl.Int16(),
    "value": pl.Float64(),
}


class SchemaError(ValueError):
    """A release file does not have the expected bulk-download layout."""


def scan_release(path: Path, release_year: int) -> pl.LazyFrame:
    """Lazily read one release file into a normalised long frame."""
    frame = pl.scan_csv(path, infer_schema=False, quote_char='"')
    columns = {name: name.strip().lower() for name in frame.collect_schema().names()}
    missing = set(REQUIRED_COLUMNS) - set(columns.values())
    if missing:
        raise SchemaError(f"{path}: missing columns {sorted(missing)}")
    return (
        frame.rename(columns)
        .select(
            pl.lit(release_year, dtype=pl.Int16).alias("release"),
            pl.col("indicator_id").str.strip_chars().str.to_uppercase().alias("series_id"),
            pl.col("country_id").str.strip_chars().str.to_uppercase().alias("country"),
            pl.col("year").str.strip_chars().cast(pl.Int16, strict=False).alias("ref_year"),
            pl.col("value").str.strip_chars().cast(pl.Float64, strict=False).alias("value"),
        )
        .filter(pl.col("ref_year").is_not_null() & (pl.col("country").str.len_chars() > 0))
    )


def release_path(settings: Settings, folder: str) -> Path:
    return settings.paths.raw_dir / folder / DATA_FILE


def build_panel(settings: Settings, taxonomy: Taxonomy) -> pl.DataFrame:
    """Read every configured release and return the vintage panel."""
    parts: list[pl.DataFrame] = []
    for folder, release_year in settings.releases.items():
        path = release_path(settings, folder)
        if not path.exists():
            raise FileNotFoundError(
                f"{path} not found. Place release files in the layout described in "
                "docs/data.md, or run `sdg4-revisions demo` to use synthetic data."
            )
        lazy = scan_release(path, release_year)
        series = lazy.select(pl.col("series_id").unique()).collect()["series_id"]
        mapping = taxonomy.mapping_frame(series.to_list())
        part = (
            lazy.join(mapping.lazy(), on="series_id", how="inner")
            .unique(subset=["series_id", "country", "ref_year"], keep="first")
            .select(list(PANEL_SCHEMA))
            .collect()
        )
        parts.append(part)
    panel = pl.concat(parts, how="vertical").cast(PANEL_SCHEMA)  # type: ignore[arg-type]
    validate_panel(panel)
    return panel.sort(["code", "release", "country", "ref_year", "series_id"])


def validate_panel(panel: pl.DataFrame) -> None:
    """Fail fast if the panel breaks its contract."""
    if dict(panel.schema) != PANEL_SCHEMA:
        raise SchemaError(f"panel schema {dict(panel.schema)} != {PANEL_SCHEMA}")
    keys = ["release", "series_id", "country", "ref_year"]
    duplicated = panel.select(keys).is_duplicated().sum()
    if duplicated:
        raise SchemaError(f"{duplicated} duplicated (release, series, country, year) keys")
    nulls = panel.select(pl.col([*keys, "code", "source"]).null_count()).row(0)
    if any(nulls):
        raise SchemaError("null keys in panel")
    bad_iso = panel.filter(~pl.col("country").str.contains(r"^[A-Z0-9]{3}$")).height
    if bad_iso:
        raise SchemaError(f"{bad_iso} rows with a malformed country code")


def write_panel(panel: pl.DataFrame, settings: Settings) -> Path:
    settings.paths.processed_dir.mkdir(parents=True, exist_ok=True)
    out = settings.paths.processed_dir / "panel.parquet"
    panel.write_parquet(out, compression="zstd", statistics=True)
    return out


def read_panel(settings: Settings) -> pl.DataFrame:
    panel = pl.read_parquet(settings.paths.processed_dir / "panel.parquet")
    validate_panel(panel)
    return panel


# --------------------------------------------------------------------------- population


def read_population(path: Path) -> pl.DataFrame:
    """UN WPP 'Total population by sex' export -> (country, year, population).

    Only national rows (non-empty ISO3), both sexes, are kept, so regional aggregates
    can never be double-counted in a population-weighted coverage share.
    """
    frame = pl.read_csv(path, infer_schema=False, encoding="utf8-lossy")
    frame = frame.rename({name: name.strip().lstrip("﻿") for name in frame.columns})
    return (
        frame.filter((pl.col("Sex") == "Both sexes") & pl.col("Iso3").str.contains(r"^[A-Z]{3}$"))
        .select(
            pl.col("Iso3").alias("country"),
            pl.col("Time").cast(pl.Int16).alias("year"),
            pl.col("Value").cast(pl.Float64).alias("population"),
        )
        .unique(subset=["country", "year"], keep="first")
        .sort(["country", "year"])
    )
