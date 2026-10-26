"""End-to-end: synthetic releases -> tables, figures, explorer payload."""

import json
from pathlib import Path

from sdg4vintage import pipeline
from sdg4vintage.config import Settings
from sdg4vintage.explorer import export


def test_full_run(synthetic_settings: Settings, tmp_path: Path) -> None:
    result = pipeline.run(synthetic_settings, figures=True)
    assert result.panel_rows > 1_000
    assert {"vintage_curves", "transition_flows", "value_revisions"} <= set(result.tables)
    for path in result.figures.values():
        assert path.stat().st_size > 10_000  # a rendered PNG, not an empty file
    summary = json.loads((synthetic_settings.paths.tables_dir / "summary.json").read_text())
    assert summary["indicators"] == 4
    # The generator plants backfills, retractions and revisions; all must be detected.
    assert summary["coverage_revisions"]["added"] > 0
    assert summary["coverage_revisions"]["dropped"] > 0
    assert 0 < summary["value_revisions"]["share_revised"] < 1

    payload = json.loads(export(synthetic_settings, tmp_path / "data.json").read_text())
    assert payload["releases"] == [2022, 2023, 2024, 2025]
    assert set(payload["masks"]) == {"4.1.2", "4.1.3", "4.1.4", "FFA"}
