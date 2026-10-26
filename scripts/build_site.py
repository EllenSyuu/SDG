"""Build the static explorer site from synthetic data.

    python scripts/build_site.py [OUT_DIR]      # default: build/site

Generates the synthetic releases, runs the pipeline, and writes ``index.html`` plus a
``data.json`` that carries both the pipeline's counts and the generator's planted
ledger, so the page can show that they agree. No real data is read.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from sdg4vintage import io
from sdg4vintage.config import load_settings
from sdg4vintage.explorer import export
from sdg4vintage.synthetic import generate
from sdg4vintage.taxonomy import load_taxonomy

ROOT = Path(__file__).resolve().parents[1]


def main(out_dir: Path) -> None:
    settings = load_settings(ROOT / "config" / "demo.yaml")
    if settings.paths.raw_dir.exists():
        shutil.rmtree(settings.paths.raw_dir)
    truth = generate(settings.paths.raw_dir)
    panel = io.build_panel(settings, load_taxonomy(settings.paths.indicators_file))
    io.write_panel(panel, settings)
    out_dir.mkdir(parents=True, exist_ok=True)
    export(settings, out_dir / "data.json", planted=[vars(t) for t in truth.transitions])
    shutil.copy(ROOT / "docs" / "explorer" / "index.html", out_dir / "index.html")
    print(f"site written to {out_dir}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "build" / "site")
