"""Synthetic releases with known ground truth.

The generator writes files with exactly the bulk-download layout
(``<raw_dir>/<YYYYMM>/SDG_DATA_NATIONAL.csv``) plus a WPP-style population file, so
the full pipeline -- ingestion, analytics, figures -- runs end to end without any
real data. It is used by the test suite, by CI and by ``sdg4v demo``.

The data-generating process encodes the mechanisms the analysis is designed to
detect:

* **reporting propensity** -- each country reports a given year with prob. ``p_c``;
* **publication lag**      -- a value for year *y* first appears ``lag_c`` years later;
* **backfilling**          -- a late value can appear in a later release for an old year;
* **retraction**           -- a published cell can disappear from the next release;
* **value revision**       -- a published value can be revised in the next release.
"""

from __future__ import annotations

import csv
import random
from dataclasses import dataclass
from pathlib import Path

# Identifiers in the taxonomy's naming scheme, so the synthetic files exercise it.
SERIES: dict[str, tuple[str, float, float]] = {
    # series_id: (indicator, typical level, noise sd)
    "ROFST.1.CP": ("4.1.4", 12.0, 3.0),
    "ROFST.2.CP": ("4.1.4", 18.0, 4.0),
    "ROFST.H.1": ("4.1.4", 14.0, 3.0),
    "ROFST.MOD.1": ("4.1.4", 13.0, 1.0),
    "AIR.1.GLAST": ("4.1.3", 88.0, 6.0),
    "CR.1": ("4.1.2", 80.0, 8.0),
    "CR.MOD.1": ("4.1.2", 79.0, 2.0),
    "XGDP.FSGOV": ("FFA", 4.2, 0.8),
}
DISTRACTOR_SERIES = ("SAP.1", "ROFST.1.GPIA.XX", "TRTP.ZZ.UNKNOWN")


@dataclass(frozen=True)
class SyntheticSpec:
    releases: tuple[int, ...] = (2022, 2023, 2024, 2025)
    first_year: int = 2008
    n_countries: int = 60
    retraction_prob: float = 0.02
    revision_prob: float = 0.15
    seed: int = 42


def country_codes(n: int) -> list[str]:
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return [letters[i // 26 % 26] + letters[i % 26] + "X" for i in range(n)]


def generate(raw_dir: Path, spec: SyntheticSpec | None = None) -> dict[str, int]:
    """Write synthetic releases under ``raw_dir``; return {folder: release_year}."""
    spec = spec or SyntheticSpec()
    rng = random.Random(spec.seed)
    countries = country_codes(spec.n_countries)
    propensity = {c: rng.uniform(0.25, 0.95) for c in countries}
    lag = {c: rng.choice((1, 1, 2, 2, 3)) for c in countries}
    level = {c: rng.uniform(0.6, 1.4) for c in countries}
    has_survey = {c: rng.random() < 0.5 for c in countries}

    # Latent "truth": which (series, country, year) will ever be reported, and its value.
    last_year = max(spec.releases)
    truth: dict[tuple[str, str, int], float] = {}
    for series_id, (_, base, sd) in SERIES.items():
        survey = series_id.startswith(("ROFST.H", "CR.1"))
        for country in countries:
            if survey and not has_survey[country]:
                continue
            p = propensity[country] * (0.45 if survey else 1.0)
            if series_id.startswith(("ROFST.MOD", "CR.MOD")):
                p = 1.0  # models fill every country-year
            for year in range(spec.first_year, last_year + 1):
                if rng.random() < p:
                    truth[(series_id, country, year)] = round(
                        max(
                            0.0,
                            base * level[country]
                            - 0.2 * (year - spec.first_year)
                            + rng.gauss(0, sd),
                        ),
                        3,
                    )

    folders: dict[str, int] = {}
    previous: dict[tuple[str, str, int], float] = {}
    for release in spec.releases:
        folder = f"{release}09"
        current: dict[tuple[str, str, int], float] = {}
        for (series_id, country, year), value in truth.items():
            delay = 1 if series_id.startswith(("ROFST.MOD", "CR.MOD")) else lag[country]
            delay += rng.random() < 0.15  # some values arrive one release late (backfill)
            if year > release - delay:
                continue
            key = (series_id, country, year)
            if key in previous and rng.random() < spec.retraction_prob:
                continue
            published = previous.get(key, value)
            if key in previous and rng.random() < spec.revision_prob:
                published = round(published + rng.gauss(0, 0.5), 3)
            current[key] = published
        _write_release(raw_dir / folder, current, countries, rng)
        folders[folder] = release
        previous = current

    _write_population(
        raw_dir / "wpp" / "total_population_by_sex.csv", countries, rng, range(2015, last_year + 1)
    )
    return folders


def _write_release(
    folder: Path, cells: dict[tuple[str, str, int], float], countries: list[str], rng: random.Random
) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    # Alternate header case across releases, as the real files do.
    upper = int(folder.name[:4]) % 2 == 1
    header = ["indicator_id", "country_id", "year", "value", "magnitude", "qualifier"]
    with (folder / "SDG_DATA_NATIONAL.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, quoting=csv.QUOTE_NONNUMERIC)
        writer.writerow([h.upper() for h in header] if upper else header)
        for (series_id, country, year), value in sorted(cells.items()):
            writer.writerow([series_id, country, year, value, "", ""])
        for distractor in DISTRACTOR_SERIES:  # series the taxonomy must ignore
            writer.writerow([distractor, rng.choice(countries), 2015, 1.0, "", ""])


def _write_population(path: Path, countries: list[str], rng: random.Random, years: range) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Iso3", "Location", "Time", "Sex", "Value"])
        for country in countries:
            size = rng.lognormvariate(16, 1.2)
            for year in years:
                writer.writerow(
                    [
                        country,
                        f"Country {country}",
                        year,
                        "Both sexes",
                        round(size * 1.01 ** (year - years.start)),
                    ]
                )
        writer.writerow(["", "World", years.start, "Both sexes", 8e9])  # aggregate: ignored
