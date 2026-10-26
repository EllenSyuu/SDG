"""Static figures (PNG) for the report and README.

Colour follows the job it does: ordered releases use a single-hue sequential ramp,
net additions/removals a two-hue diverging scale with a grey midpoint, and source
layers three fixed categorical slots. Text is always ink, never a series colour.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import polars as pl
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
from matplotlib.figure import Figure
from matplotlib.patches import Patch

INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e4e3df"
SURFACE = "#fcfcfb"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]  # categorical slots 1-3
BLUE_RAMP = ["#b7d3f3", "#7fb0ea", "#3d84d9", "#1a5aa8", "#0e3a73"]
DIVERGING = LinearSegmentedColormap.from_list("div", ["#d95926", "#f3f2ee", "#2a78d6"])

plt.rcParams.update(
    {
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "axes.edgecolor": GRID,
        "axes.labelcolor": INK_2,
        "axes.titlecolor": INK,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.6,
        "xtick.color": INK_2,
        "ytick.color": INK_2,
        "font.size": 9,
        "axes.titlesize": 10,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "legend.frameon": False,
    }
)


def _ramp(n: int) -> list[str]:
    if n <= len(BLUE_RAMP):
        return BLUE_RAMP[len(BLUE_RAMP) - n :]
    shades = plt.get_cmap("Blues")(np.linspace(0.35, 0.95, n))
    return [matplotlib.colors.to_hex(c) for c in shades]


def _title(fig: Figure, title: str, subtitle: str) -> None:
    """Title block positioned in inches from the top, so it never collides with content."""
    h = fig.get_figheight()
    fig.text(
        0.01, 1 - 0.15 / h, title, ha="left", va="top", fontsize=13, fontweight="bold", color=INK
    )
    fig.text(0.01, 1 - 0.47 / h, subtitle, ha="left", va="top", fontsize=9.5, color=INK_2)


def vintage_curves(
    curves: pl.DataFrame, names: dict[str, str], codes: list[str], out: Path
) -> Path:
    releases = sorted(curves["release"].unique().to_list())
    colors = dict(zip(releases, _ramp(len(releases)), strict=True))
    ncols = 3
    nrows = int(np.ceil(len(codes) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(12, 3.0 * nrows + 1.0), squeeze=False)
    for ax, code in zip(axes.ravel(), codes, strict=False):
        panel = curves.filter(pl.col("code") == code)
        for release in releases:
            line = panel.filter(pl.col("release") == release).sort("ref_year")
            ax.plot(
                line["ref_year"],
                line["n_countries"],
                color=colors[release],
                lw=2,
                label=str(release),
            )
        ax.set_title(f"{code}  {names.get(code, '')}")
        ax.set_ylim(bottom=0)
    for ax in axes.ravel()[len(codes) :]:
        ax.axis("off")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(
        handles,
        [f"{label} release" for label in labels],
        loc="upper left",
        ncols=len(releases),
        bbox_to_anchor=(0.005, 1 - 0.72 / fig.get_figheight()),
    )
    _title(
        fig,
        "Vintage curves: countries reporting each reference year, by release",
        "Each line is one published release. The right-hand sag is reporting lag; "
        "lines lifting between releases are backfilled data.",
    )
    fig.supxlabel("Reference year", color=INK_2)
    fig.supylabel("Countries with a value", color=INK_2)
    fig.tight_layout(rect=(0, 0, 1, 1 - 1.1 / fig.get_figheight()))
    fig.savefig(out, dpi=160)
    plt.close(fig)
    return out


def transition_heatmap(
    flows: pl.DataFrame, names: dict[str, str], codes: list[str], out: Path
) -> Path:
    transitions = flows.select("from_release", "to_release").unique().sort("from_release").rows()
    years = sorted(flows["ref_year"].unique().to_list())
    width = 4.0 * len(transitions) + 4.4
    height = 0.36 * len(codes) + 2.4
    fig = plt.figure(figsize=(width, height))
    left, right, gap = 3.4 / width, 1.0 - 1.1 / width, 0.25 / width
    panel_w = (right - left - gap * (len(transitions) - 1)) / len(transitions)
    bottom, top = 0.85 / height, 1.0 - 1.15 / height
    peak = flows.filter(pl.col("code").is_in(codes)).select(pl.col("net").abs().max()).item()
    limit = max(1, int(peak or 1))
    norm = TwoSlopeNorm(vmin=-limit, vcenter=0, vmax=limit)
    image = None
    for i, (before, after) in enumerate(transitions):
        ax = fig.add_axes((left + i * (panel_w + gap), bottom, panel_w, top - bottom))
        grid = np.full((len(codes), len(years)), np.nan)
        part = flows.filter((pl.col("from_release") == before) & pl.col("code").is_in(codes))
        for code, year, net in part.select("code", "ref_year", "net").iter_rows():
            grid[codes.index(code), years.index(year)] = net
        image = ax.imshow(grid, cmap=DIVERGING, norm=norm, aspect="auto", interpolation="nearest")
        ax.set_title(f"{before} → {after} release", fontsize=9.5)
        ticks = [j for j, y in enumerate(years) if y % 4 == 0]
        ax.set_xticks(ticks, [str(years[j]) for j in ticks])
        if i == 0:
            ax.set_yticks(range(len(codes)), [f"{c}  {names.get(c, '')}" for c in codes])
        else:
            ax.set_yticks([])
        ax.tick_params(length=0)
        ax.grid(False)
        for spine in ax.spines.values():
            spine.set_visible(False)
    assert image is not None
    cax = fig.add_axes((right + 0.25 / width, bottom, 0.16 / width, top - bottom))
    bar = fig.colorbar(image, cax=cax)
    bar.set_label("Net country-years (added − dropped)", color=INK_2)
    bar.outline.set_visible(False)
    _title(
        fig,
        "Release-to-release revisions of coverage",
        "Blue: country-years that appeared for an already-eligible reference year "
        "(backfill). Orange: country-years withdrawn. Grey: no change or not yet eligible.",
    )
    fig.savefig(out, dpi=160)
    plt.close(fig)
    return out


def value_revisions(
    revisions: pl.DataFrame, names: dict[str, str], codes: list[str], out: Path
) -> Path:
    transitions = (
        revisions.select("from_release", "to_release").unique().sort("from_release").rows()
    )
    fig, ax = plt.subplots(figsize=(9, 0.45 * len(codes) + 2.2))
    y = np.arange(len(codes))
    for slot, (before, after) in enumerate(transitions[-3:]):
        part = revisions.filter(pl.col("from_release") == before)
        share = {c: s for c, s in part.select("code", "share_revised").iter_rows()}
        ax.scatter(
            [100 * share.get(c, np.nan) for c in codes],
            y,
            s=46,
            color=SERIES[slot],
            edgecolor=SURFACE,
            linewidth=1.5,
            zorder=3,
            label=f"{before} → {after}",
        )
    ax.set_yticks(y, [f"{c}  {names.get(c, '')}" for c in codes])
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xlabel("Published values changed in the next release (%)")
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower right", title="Release transition", title_fontsize=8.5)
    _title(
        fig,
        "How often published values are revised",
        "Same series, country and reference year compared across consecutive releases "
        "(changes ≤ 0.001 ignored).",
    )
    fig.tight_layout(rect=(0, 0, 1, 1 - 0.8 / fig.get_figheight()))
    fig.savefig(out, dpi=160)
    plt.close(fig)
    return out


def source_layers(layers: pl.DataFrame, names: dict[str, str], release: int, out: Path) -> Path:
    latest = layers.filter(pl.col("release") == release)
    wide = latest.pivot(on="layer", index="code", values="n_countries").fill_null(0)
    for column in ("admin", "+ hhs", "+ model"):
        if column not in wide.columns:
            wide = wide.with_columns(pl.lit(0).alias(column))
    wide = wide.with_columns(
        (pl.col("+ hhs") - pl.col("admin")).alias("hhs_gain"),
        (pl.col("+ model") - pl.col("+ hhs")).alias("model_gain"),
    ).filter((pl.col("hhs_gain") > 0) | (pl.col("model_gain") > 0) | (pl.col("admin") == 0))
    wide = wide.sort("+ model")
    codes = wide["code"].to_list()
    fig, ax = plt.subplots(figsize=(9, 0.5 * len(codes) + 2.0))
    left = np.zeros(len(codes))
    parts = [
        ("admin", "Administrative"),
        ("hhs_gain", "+ household survey"),
        ("model_gain", "+ modelled"),
    ]
    for slot, (column, label) in enumerate(parts):
        values = wide[column].to_numpy().astype(float)
        ax.barh(
            codes,
            values,
            left=left,
            color=SERIES[slot],
            height=0.6,
            label=label,
            edgecolor=SURFACE,
            linewidth=2,
        )
        left += values
    for i, total in enumerate(left):
        ax.text(total + 2, i, f"{int(total)}", va="center", color=INK_2, fontsize=8.5)
    ax.set_yticks(range(len(codes)), [f"{c}  {names.get(c, '')}" for c in codes])
    ax.set_xlabel(f"Countries with any value, 2008–{release - 1} ({release} release)")
    ax.grid(axis="y", visible=False)
    handles = [Patch(facecolor=SERIES[i], label=label) for i, (_, label) in enumerate(parts)]
    fig.legend(
        handles=handles,
        loc="upper left",
        ncols=3,
        bbox_to_anchor=(0.005, 1 - 0.72 / fig.get_figheight()),
    )
    _title(
        fig,
        "Where coverage comes from",
        "Countries covered by administrative data alone, and the extra countries "
        "reached by surveys and models.",
    )
    fig.tight_layout(rect=(0, 0, 1, 1 - 1.1 / fig.get_figheight()))
    fig.savefig(out, dpi=160)
    plt.close(fig)
    return out
