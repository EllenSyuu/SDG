"""Command-line interface: ``sdg4v --help``."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Annotated

import typer

from sdg4vintage import pipeline
from sdg4vintage.config import load_settings
from sdg4vintage.explorer import export
from sdg4vintage.synthetic import generate

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Release-vintage analytics for SDG 4 education statistics.",
)

ConfigOpt = Annotated[Path, typer.Option("--config", "-c", help="Run configuration (YAML).")]


@app.command()
def run(
    config: ConfigOpt = Path("config/default.yaml"),
    figures: Annotated[bool, typer.Option(help="Render PNG figures.")] = True,
) -> None:
    """Build the panel and every table/figure from the configured releases."""
    settings = load_settings(config)
    result = pipeline.run(settings, figures=figures)
    typer.echo(f"panel: {result.panel_rows:,} rows in {result.seconds:.1f}s")
    for kind, paths in (("table", result.tables), ("figure", result.figures)):
        for name, path in paths.items():
            typer.echo(f"  {kind:<6} {name:<20} {path}")


@app.command()
def demo(config: ConfigOpt = Path("config/demo.yaml")) -> None:
    """Generate synthetic releases and run the full pipeline on them (no data needed)."""
    settings = load_settings(config)
    if settings.paths.raw_dir.exists():
        shutil.rmtree(settings.paths.raw_dir)
    generate(settings.paths.raw_dir)
    result = pipeline.run(settings)
    typer.echo(f"demo panel: {result.panel_rows:,} rows -> {settings.paths.figures_dir}")


@app.command()
def explorer(
    config: ConfigOpt = Path("config/demo.yaml"),
    out: Annotated[Path, typer.Option()] = Path("docs/explorer/data.json"),
) -> None:
    """Export the compact JSON that powers the static coverage explorer."""
    settings = load_settings(config)
    path = export(settings, out)
    typer.echo(f"wrote {path} ({path.stat().st_size / 1024:.0f} KB)")
    typer.echo(json.dumps({"open": str(out.parent / "index.html")}))


if __name__ == "__main__":
    app()
