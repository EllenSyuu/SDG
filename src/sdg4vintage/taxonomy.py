"""Rule-based mapping from series identifiers to SDG indicators and data sources.

A release publishes thousands of series (``ROFST.1.F.CP``,
``CR.MOD.2`` ...). An SDG indicator such as 4.1.4 (out-of-school rate) is the union
of many of them, coming from three kinds of source:

* ``admin`` -- administrative enrolment data reported by countries;
* ``hhs``   -- household-survey estimates;
* ``model`` -- statistically modelled estimates.

The mapping is declared as ordered regular-expression rules in
``config/indicators.yaml``. Rules are full-match, case-insensitive, and every series
may resolve to at most one indicator: an ambiguous series is a configuration error,
not something to resolve silently.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import polars as pl
import yaml


class Source(StrEnum):
    ADMIN = "admin"
    HHS = "hhs"
    MODEL = "model"


@dataclass(frozen=True, slots=True)
class SeriesRule:
    pattern: re.Pattern[str]
    source: Source


@dataclass(frozen=True, slots=True)
class Indicator:
    code: str
    name: str
    target: str
    rules: tuple[SeriesRule, ...]

    def match(self, series_id: str) -> Source | None:
        for rule in self.rules:
            if rule.pattern.fullmatch(series_id):
                return rule.source
        return None


class AmbiguousSeriesError(ValueError):
    """A series identifier matched the rules of more than one indicator."""


@dataclass(frozen=True, slots=True)
class Taxonomy:
    indicators: tuple[Indicator, ...]

    @property
    def codes(self) -> list[str]:
        return [indicator.code for indicator in self.indicators]

    def get(self, code: str) -> Indicator:
        for indicator in self.indicators:
            if indicator.code == code:
                return indicator
        raise KeyError(code)

    def classify(self, series_id: str) -> tuple[str, Source] | None:
        """Return ``(indicator code, source)`` for one series, or ``None``."""
        key = series_id.strip().upper()
        hits = [
            (indicator.code, source)
            for indicator in self.indicators
            if (source := indicator.match(key)) is not None
        ]
        if len(hits) > 1:
            raise AmbiguousSeriesError(f"{series_id!r} matches {[code for code, _ in hits]}")
        return hits[0] if hits else None

    def mapping_frame(self, series_ids: Iterable[str]) -> pl.DataFrame:
        """Classify a set of identifiers; unmatched identifiers are dropped."""
        rows = []
        for series_id in sorted({s.strip().upper() for s in series_ids}):
            hit = self.classify(series_id)
            if hit is not None:
                rows.append({"series_id": series_id, "code": hit[0], "source": hit[1].value})
        schema = {"series_id": pl.String, "code": pl.String, "source": pl.String}
        return pl.DataFrame(rows, schema=schema)


def load_taxonomy(path: str | Path) -> Taxonomy:
    with Path(path).open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    indicators = []
    for code, spec in raw["indicators"].items():
        rules = tuple(
            SeriesRule(re.compile(rule["pattern"], re.IGNORECASE), Source(rule["source"]))
            for rule in spec["series"]
        )
        indicators.append(
            Indicator(code=str(code), name=spec["name"], target=str(spec["target"]), rules=rules)
        )
    return Taxonomy(tuple(indicators))
