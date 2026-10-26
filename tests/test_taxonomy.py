import re

import pytest

from sdg4vintage.taxonomy import (
    AmbiguousSeriesError,
    Indicator,
    SeriesRule,
    Source,
    Taxonomy,
)


@pytest.mark.parametrize(
    ("series_id", "expected"),
    [
        ("ROFST.1.CP", ("4.1.4", Source.ADMIN)),
        ("rofst.1t2.f.cp", ("4.1.4", Source.ADMIN)),  # case-insensitive
        ("ROFST.H.2.URB.Q1.F", ("4.1.4", Source.HHS)),
        ("ROFST.MOD.3.M", ("4.1.4", Source.MODEL)),
        ("CR.MOD.1", ("4.1.2", Source.MODEL)),
        ("CR.2.RUR.Q5", ("4.1.2", Source.HHS)),
        ("AIR.2.GPV.GLAST.F", ("4.1.3", Source.ADMIN)),
        ("NERA.AGM1.F.CP", ("4.2.2", Source.ADMIN)),
        ("GER.5T8", ("4.3.2", Source.ADMIN)),
        ("PTRHC.2T3.TRAINED", ("4.c.2", Source.ADMIN)),
        ("PTRHC.2T3.QUALIFIED", ("4.c.4", Source.ADMIN)),
        ("XGOVEXP.IMFCALC", ("1.a.2", Source.ADMIN)),
        ("XGDP.FSGOV", ("FFA", Source.ADMIN)),
    ],
)
def test_known_series(taxonomy: Taxonomy, series_id: str, expected: tuple[str, Source]) -> None:
    assert taxonomy.classify(series_id) == expected


@pytest.mark.parametrize(
    "series_id",
    ["ROFST.1.GPIA", "ROFST.1.CP.EXTRA", "CR.4", "GER.1", "PTRHC.1", "XGOVEXP", "SAP.1", ""],
)
def test_near_misses_are_rejected(taxonomy: Taxonomy, series_id: str) -> None:
    assert taxonomy.classify(series_id) is None


def test_every_indicator_has_rules(taxonomy: Taxonomy) -> None:
    assert len(taxonomy.codes) == 12
    assert all(indicator.rules for indicator in taxonomy.indicators)


def test_ambiguous_series_fail_loudly() -> None:
    rule = (SeriesRule(re.compile("X\\..*"), Source.ADMIN),)
    clash = Taxonomy((Indicator("a", "A", "t", rule), Indicator("b", "B", "t", rule)))
    with pytest.raises(AmbiguousSeriesError):
        clash.classify("X.1")


def test_mapping_frame_drops_unknown_and_dedupes(taxonomy: Taxonomy) -> None:
    frame = taxonomy.mapping_frame(["ROFST.1.CP", "rofst.1.cp ", "UNKNOWN"])
    assert frame.to_dicts() == [{"series_id": "ROFST.1.CP", "code": "4.1.4", "source": "admin"}]
