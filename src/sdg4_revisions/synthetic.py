"""Synthetic releases with a known ground truth.

The generator writes files in exactly the layout the pipeline reads
(``<raw_dir>/<YYYYMM>/SDG_DATA_NATIONAL.csv``) plus a population file, so ingestion,
analytics, figures and the explorer all run end to end without any real data. It is
used by the test suite, by CI and by ``sdg4-revisions demo``.

Every effect the analysis is designed to measure is planted deliberately, and every
planted event is recorded in a :class:`GroundTruth` ledger, so the pipeline's output
can be checked against the truth *exactly* rather than approximately:

* **reporting propensity** -- each country reports a given year with its own probability;
* **publication lag**      -- a value for year *y* is first published ``lag`` releases later;
* **backfill**             -- some values miss their first eligible release and arrive later;
* **retraction**           -- a published cell can be withdrawn, permanently;
* **value revision**       -- a carried-over value can change by a clearly non-zero amount;
* **method change**        -- modelled series only exist from ``model_from`` onwards;
* **schema drift**         -- header case alternates between releases;
* **noise**                -- distractor series the taxonomy must ignore.
"""

from __future__ import annotations

import csv
import random
from dataclasses import dataclass, field
from itertools import pairwise
from pathlib import Path

# series_id: (indicator, typical level, noise sd, kind). Identifiers follow the naming
# scheme in config/indicators.yaml, so the synthetic files exercise the real taxonomy.
SERIES: dict[str, tuple[str, float, float, str]] = {
    "ROFST.1.CP": ("4.1.4", 12.0, 3.0, "admin"),
    "ROFST.2.CP": ("4.1.4", 18.0, 4.0, "admin"),
    "ROFST.H.1": ("4.1.4", 14.0, 3.0, "hhs"),
    "ROFST.MOD.1": ("4.1.4", 13.0, 1.0, "model"),
    "CR.1": ("4.1.2", 80.0, 8.0, "hhs"),
    "CR.MOD.1": ("4.1.2", 79.0, 2.0, "model"),
    "AIR.1.GLAST": ("4.1.3", 88.0, 6.0, "admin"),
    "OAEPG.1": ("4.1.5", 9.0, 2.0, "admin"),
    "OAEPG.H.1": ("4.1.5", 10.0, 2.5, "hhs"),
    "TRTP.1": ("4.c.1", 78.0, 7.0, "admin"),
    "XGOVEXP.IMF": ("1.a.2", 14.0, 3.0, "admin"),
    "XGDP.FSGOV": ("FFA", 4.2, 0.8, "admin"),
}
DISTRACTOR_SERIES = ("SAP.1", "ROFST.1.GPIA.XX", "TRTP.ZZ.UNKNOWN")

Cell = tuple[str, str, int]  # (series_id, country, reference year)


@dataclass(frozen=True)
class SyntheticSpec:
    releases: tuple[int, ...] = (2022, 2023, 2024, 2025)
    first_year: int = 2008
    n_countries: int = 60
    backfill_prob: float = 0.15
    retraction_prob: float = 0.02
    revision_prob: float = 0.15
    model_from: int = 2023
    seed: int = 42


@dataclass
class TransitionTruth:
    """Planted events between two consecutive releases, at series level."""

    from_release: int
    to_release: int
    retained: int = 0
    backfilled: int = 0
    retracted: int = 0
    revised: int = 0


@dataclass
class GroundTruth:
    folders: dict[str, int] = field(default_factory=dict)
    transitions: list[TransitionTruth] = field(default_factory=list)


def country_codes(n: int) -> list[str]:
    """Placeholder 3-character codes (``AAX``, ``ABX`` ...), never real country codes."""
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return [letters[i // 26 % 26] + letters[i % 26] + "X" for i in range(n)]


def generate(raw_dir: Path, spec: SyntheticSpec | None = None) -> GroundTruth:
    """Write synthetic releases under ``raw_dir`` and return the ground-truth ledger."""
    spec = spec or SyntheticSpec()
    rng = random.Random(spec.seed)
    countries = country_codes(spec.n_countries)
    value, arrival = _latent_cells(spec, countries, rng)

    truth = GroundTruth()
    published = _publish(spec, value, arrival, rng)
    for release, cells in published.items():
        folder = f"{release}09"
        _write_release(raw_dir / folder, cells, countries, rng, upper=release % 2 == 1)
        truth.folders[folder] = release
    truth.transitions = [
        _ledger(before, after, published[before], published[after])
        for before, after in pairwise(spec.releases)
    ]
    _write_population(
        raw_dir / "wpp" / "total_population_by_sex.csv",
        countries,
        rng,
        range(2015, max(spec.releases) + 1),
    )
    return truth


def _latent_cells(
    spec: SyntheticSpec, countries: list[str], rng: random.Random
) -> tuple[dict[Cell, float], dict[Cell, int]]:
    """Every cell that will ever be published, its value, and its first release.

    The first release is fixed once per cell, so the timing of each cell is known.
    """
    propensity = {c: rng.uniform(0.3, 0.95) for c in countries}
    lag = {c: rng.choice((1, 1, 2, 2, 3)) for c in countries}
    level = {c: rng.uniform(0.6, 1.4) for c in countries}
    has_survey = {c: rng.random() < 0.55 for c in countries}
    value: dict[Cell, float] = {}
    arrival: dict[Cell, int] = {}
    for series_id, (_, base, sd, kind) in SERIES.items():
        for country in countries:
            if kind == "hhs" and not has_survey[country]:
                continue
            p = 1.0 if kind == "model" else propensity[country] * (0.5 if kind == "hhs" else 1)
            for year in range(spec.first_year, max(spec.releases)):
                if rng.random() >= p:
                    continue
                cell = (series_id, country, year)
                trend = base * level[country] - 0.2 * (year - spec.first_year)
                value[cell] = round(max(0.0, trend + rng.gauss(0, sd)), 3)
                delay = (1 if kind == "model" else lag[country]) + int(
                    rng.random() < spec.backfill_prob
                )
                first = year + delay
                arrival[cell] = max(first, spec.model_from) if kind == "model" else first
    return value, arrival


def _publish(
    spec: SyntheticSpec,
    value: dict[Cell, float],
    arrival: dict[Cell, int],
    rng: random.Random,
) -> dict[int, dict[Cell, float]]:
    """Cells published in each release, with permanent retractions and revisions."""
    retracted: set[Cell] = set()
    published: dict[int, dict[Cell, float]] = {}
    previous: dict[Cell, float] = {}
    for release in spec.releases:
        current: dict[Cell, float] = {}
        for cell, first in arrival.items():
            if first > release or cell in retracted:
                continue
            if cell in previous and rng.random() < spec.retraction_prob:
                retracted.add(cell)
                continue
            current[cell] = previous.get(cell, value[cell])
            if cell in previous and rng.random() < spec.revision_prob:
                shift = rng.uniform(0.05, 1.5) * rng.choice((-1, 1))
                current[cell] = round(current[cell] + shift, 3)
        published[release] = previous = current
    return published


def _ledger(
    before: int, after: int, old: dict[Cell, float], new: dict[Cell, float]
) -> TransitionTruth:
    """Count planted events for cells eligible in the earlier release."""
    ledger = TransitionTruth(before, after)
    for cell in old.keys() | new.keys():
        if cell[2] > before - 1:
            continue
        if cell in old and cell in new:
            ledger.retained += 1
            ledger.revised += old[cell] != new[cell]
        elif cell in new:
            ledger.backfilled += 1
        else:
            ledger.retracted += 1
    return ledger


def _write_release(
    folder: Path,
    cells: dict[Cell, float],
    countries: list[str],
    rng: random.Random,
    *,
    upper: bool,
) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    header = ["indicator_id", "country_id", "year", "value", "magnitude", "qualifier"]
    with (folder / "SDG_DATA_NATIONAL.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, quoting=csv.QUOTE_NONNUMERIC)
        writer.writerow([h.upper() for h in header] if upper else header)
        for (series_id, country, year), number in sorted(cells.items()):
            writer.writerow([series_id, country, year, number, "", ""])
        for distractor in DISTRACTOR_SERIES:
            writer.writerow([distractor, rng.choice(countries), 2015, 1.0, "", ""])


def _write_population(path: Path, countries: list[str], rng: random.Random, years: range) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Iso3", "Location", "Time", "Sex", "Value"])
        for country in countries:
            size = rng.lognormvariate(16, 1.2)
            for year in years:
                growth = 1.01 ** (year - years.start)
                writer.writerow(
                    [country, f"Country {country}", year, "Both sexes", round(size * growth)]
                )
        writer.writerow(["", "Aggregate", years.start, "Both sexes", 1e9])  # must be ignored
