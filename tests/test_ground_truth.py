"""The pipeline must recover every event the synthetic generator planted, exactly."""

from pathlib import Path

import pytest

from sdg4_revisions import analysis, io
from sdg4_revisions.synthetic import SyntheticSpec, generate
from sdg4_revisions.taxonomy import Taxonomy

from .conftest import make_settings


@pytest.mark.parametrize("seed", [1, 7, 42])
def test_series_ledger_matches_planted_truth(tmp_path: Path, taxonomy: Taxonomy, seed: int) -> None:
    truth = generate(tmp_path / "raw", SyntheticSpec(seed=seed, n_countries=30))
    settings = make_settings(tmp_path, releases=truth.folders)
    panel = io.build_panel(settings, taxonomy)
    measured = analysis.series_transitions(panel, settings).to_dicts()

    assert len(measured) == len(truth.transitions) == 3
    for got, planted in zip(measured, truth.transitions, strict=True):
        assert (got["from_release"], got["to_release"]) == (
            planted.from_release,
            planted.to_release,
        )
        assert got["retained"] == planted.retained
        assert got["backfilled"] == planted.backfilled
        assert got["retracted"] == planted.retracted
        assert got["revised"] == planted.revised
    # sanity: the generator actually planted every kind of event
    assert all(t.backfilled and t.retracted and t.revised for t in truth.transitions)


def test_method_change_is_visible(tmp_path: Path, taxonomy: Taxonomy) -> None:
    """Modelled series exist only from `model_from`, so 4.1.2 jumps between releases."""
    truth = generate(tmp_path / "raw", SyntheticSpec(n_countries=30, model_from=2023))
    settings = make_settings(tmp_path, releases=truth.folders)
    panel = io.build_panel(settings, taxonomy)
    sources = {r: set(panel.filter(panel["release"] == r)["source"].unique()) for r in (2022, 2023)}
    assert "model" not in sources[2022] and "model" in sources[2023]
