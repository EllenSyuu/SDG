"""Static figures, rendered in a light and a dark theme.

Every figure is designed for the width at which it is actually read: a README column
on GitHub is about 880 px wide, so figures are laid out at 10 inches with type sized
so that the smallest label still renders at roughly 11 px on screen. Multi-panel
figures stack vertically rather than squeezing panels side by side.

Colour follows the job it does: ordered releases use one sequential hue (older =
fainter, newest = strongest), net additions/withdrawals a two-hue diverging scale with
a neutral midpoint, and data sources three fixed categorical slots. Text always uses
ink tokens, never a series colour.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import polars as pl
from matplotlib.animation import FuncAnimation, PillowWriter
from matplotlib.artist import Artist
from matplotlib.axes import Axes
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

WIDTH = 10.0  # inches; displayed at ~880 px in a README column


@dataclass(frozen=True)
class Theme:
    name: str
    surface: str
    ink: str
    ink_2: str
    ink_3: str
    grid: str
    series: tuple[str, str, str]  # categorical slots 1-3: blue, orange, aqua
    ramp: tuple[str, ...]  # sequential blue, faint -> strong
    diverging: tuple[str, str, str]  # orange, neutral, blue


LIGHT = Theme(
    name="light",
    surface="#ffffff",
    ink="#16202e",
    ink_2="#4b5768",
    ink_3="#7d8896",
    grid="#e6eaef",
    series=("#2a78d6", "#eb6834", "#1baf7a"),
    ramp=("#b9d3f0", "#7eaee6", "#3b7dd8", "#1b4f9c", "#0e3a73"),
    diverging=("#e2622b", "#f1f3f5", "#2a78d6"),
)
DARK = Theme(
    name="dark",
    surface="#0d1117",  # GitHub dark canvas, so README images sit flush
    ink="#e8edf3",
    ink_2="#a3afbd",
    ink_3="#6f7c8c",
    grid="#222b36",
    series=("#4a94ea", "#f07a45", "#1fb98f"),
    ramp=("#1d3f6e", "#2f6ab2", "#5c9be6", "#9cc4f3", "#d3e5fa"),
    diverging=("#f07a45", "#1a222c", "#4a94ea"),
)
THEMES = {"light": LIGHT, "dark": DARK}
_theme: Theme = LIGHT


def set_theme(name: str = "light") -> Theme:
    """Activate a theme for every figure rendered afterwards."""
    global _theme  # noqa: PLW0603 - module-level rendering state, by design
    _theme = THEMES[name]
    t = _theme
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Inter", "Helvetica Neue", "Arial", "DejaVu Sans"],
            "font.size": 12,
            "figure.facecolor": t.surface,
            "axes.facecolor": t.surface,
            "savefig.facecolor": t.surface,
            "savefig.dpi": 200,
            "axes.edgecolor": t.grid,
            "axes.linewidth": 1.0,
            "axes.labelcolor": t.ink_2,
            "axes.labelsize": 12,
            "axes.labelpad": 8,
            "axes.titlecolor": t.ink,
            "axes.titlesize": 13.5,
            "axes.titleweight": "bold",
            "axes.titlelocation": "left",
            "axes.titlepad": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.spines.left": False,
            "axes.grid": True,
            "axes.grid.axis": "y",
            "axes.axisbelow": True,
            "grid.color": t.grid,
            "grid.linewidth": 1.0,
            "xtick.color": t.ink_2,
            "ytick.color": t.ink_2,
            "xtick.labelsize": 11,
            "ytick.labelsize": 11,
            "ytick.major.size": 0,
            "xtick.major.size": 4,
            "xtick.major.pad": 6,
            "ytick.major.pad": 6,
            "text.color": t.ink,
            "legend.labelcolor": t.ink_2,
            "legend.fontsize": 11.5,
            "legend.frameon": False,
            "legend.handlelength": 1.6,
            "legend.columnspacing": 1.6,
            "lines.solid_capstyle": "round",
        }
    )
    return t


set_theme("light")


# --------------------------------------------------------------------------- helpers


def _ramp(n: int) -> list[str]:
    ramp = _theme.ramp
    if n <= len(ramp):
        return list(ramp[len(ramp) - n :])
    cmap = LinearSegmentedColormap.from_list("ramp", list(ramp))
    return [matplotlib.colors.to_hex(cmap(x)) for x in np.linspace(0, 1, n)]


def _diverging() -> LinearSegmentedColormap:
    return LinearSegmentedColormap.from_list("div", list(_theme.diverging))


def _figure(height: float, title: str, subtitle: str, legend: bool = False) -> Figure:
    """A constrained-layout figure with a title block laid out in inches.

    The plotting area starts below the title, subtitle and (optional) legend row,
    whatever the figure height, so nothing ever overlaps.
    """
    fig = plt.figure(figsize=(WIDTH, height), layout="constrained")
    fig.text(
        0.012,
        1 - 0.2 / height,
        title,
        ha="left",
        va="top",
        fontsize=19,
        fontweight="bold",
        color=_theme.ink,
    )
    fig.text(
        0.012,
        1 - 0.62 / height,
        subtitle,
        ha="left",
        va="top",
        fontsize=12.5,
        color=_theme.ink_2,
        wrap=True,
    )
    top = 1 - (1.42 if legend else 1.05) / height
    engine = fig.get_layout_engine()
    if engine is not None:
        cast(Any, engine).set(rect=(0, 0, 1, top), w_pad=0.08, h_pad=0.12, hspace=0.06, wspace=0.04)
    return fig


def _legend(fig: Figure, handles: Sequence[Artist], ncols: int) -> None:
    fig.legend(
        handles=handles,
        loc="upper left",
        ncols=ncols,
        bbox_to_anchor=(0.006, 1 - 0.98 / fig.get_figheight()),
    )


def _save(fig: Figure, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    plt.close(fig)
    return out


def _label(code: str, names: dict[str, str]) -> str:
    return f"{code}  {names.get(code, '')}".strip()


def _release_lines(
    ax: Axes, panel: pl.DataFrame, releases: list[int], colors: dict[int, str], lw: float = 2.2
) -> None:
    t = _theme
    for release in releases:
        line = panel.filter(pl.col("release") == release).sort("ref_year")
        if line.is_empty():
            continue
        latest = release == releases[-1]
        ax.plot(
            line["ref_year"],
            line["n_countries"],
            color=colors[release],
            lw=lw + 0.8 if latest else lw,
            zorder=3 if latest else 2,
        )
        ax.scatter(
            line["ref_year"][-1],
            line["n_countries"][-1],
            s=46 if latest else 34,
            color=colors[release],
            edgecolor=t.surface,
            linewidth=1.8,
            zorder=4,
        )


def _release_handles(releases: list[int], colors: dict[int, str]) -> list[Line2D]:
    return [Line2D([], [], color=colors[r], lw=3, label=f"{r} release") for r in releases]


# --------------------------------------------------------------------------- hero


def hero(curves: pl.DataFrame, names: dict[str, str], code: str, out: Path) -> Path:
    """One indicator, every release: curves on the left, one year's drift on the right."""
    t = _theme
    panel = curves.filter(pl.col("code") == code)
    releases = sorted(panel["release"].unique().to_list())
    colors = dict(zip(releases, _ramp(len(releases)), strict=True))
    fig = _figure(
        6.0,
        "The same statistic, published four times",
        f"{_label(code, names)}: each release adds a year, fills in late data and revises "
        "the past.",
        legend=True,
    )
    _legend(fig, _release_handles(releases, colors), len(releases))
    ax, bx = fig.subplots(1, 2, width_ratios=(2.2, 1))

    _release_lines(ax, panel, releases, colors, lw=2.4)
    ax.set_ylim(bottom=0)
    ax.set_title("Countries with a value, by reference year")
    ax.set_xlabel("Reference year")
    newest = panel.filter(pl.col("release") == releases[-1]).sort("ref_year")
    x_last, y_last = newest["ref_year"][-1], newest["n_countries"][-1]
    ax.annotate(
        "newest year: only\npartly reported",
        xy=(x_last, y_last),
        xytext=(x_last - 4.2, max(2.0, y_last * 0.25)),
        color=t.ink_2,
        fontsize=11,
        ha="right",
        va="center",
        arrowprops={"arrowstyle": "-|>", "color": t.ink_3, "lw": 1.2, "shrinkB": 6},
    )

    year = releases[0] - 1
    drift = panel.filter(pl.col("ref_year") == year).sort("release")
    counts = drift["n_countries"].to_list()
    labels = [str(r) for r in drift["release"].to_list()]
    bx.bar(labels, counts, color=[colors[r] for r in drift["release"]], width=0.66)
    for i, n in enumerate(counts):
        bx.text(
            i, n, f"{n}", ha="center", va="bottom", color=t.ink, fontsize=12.5, fontweight="bold"
        )
        if i:
            change = n - counts[i - 1]
            if change:
                bx.annotate(
                    f"{'+' if change > 0 else '−'}{abs(change)}",
                    (i, n),
                    xytext=(0, 20),
                    textcoords="offset points",
                    ha="center",
                    color=t.series[2] if change > 0 else t.series[1],
                    fontsize=11,
                )
    bx.set_ylim(0, max([*counts, 1]) * 1.3)
    bx.set_title(f"{year}, as each release saw it")
    bx.set_xlabel("Release")
    bx.grid(axis="y", visible=False)
    bx.set_yticks([])
    return _save(fig, out)


# --------------------------------------------------------------------------- panels


def vintage_curves(
    curves: pl.DataFrame, names: dict[str, str], codes: list[str], out: Path
) -> Path:
    releases = sorted(curves["release"].unique().to_list())
    colors = dict(zip(releases, _ramp(len(releases)), strict=True))
    nrows = int(np.ceil(len(codes) / 2))
    fig = _figure(
        2.9 * nrows + 1.7,
        "Vintage curves for six indicators",
        "Countries with a value in each reference year, as seen by each release.",
        legend=True,
    )
    _legend(fig, _release_handles(releases, colors), len(releases))
    axes = fig.subplots(nrows, 2, sharex=True, squeeze=False)
    for ax, code in zip(axes.ravel(), codes, strict=False):
        _release_lines(ax, curves.filter(pl.col("code") == code), releases, colors, lw=1.9)
        ax.set_title(_label(code, names), fontsize=12.5)
        ax.set_ylim(bottom=0)
    for ax in axes.ravel()[len(codes) :]:
        ax.set_visible(False)
    fig.supxlabel("Reference year", color=_theme.ink_2, fontsize=12)
    return _save(fig, out)


def transition_heatmap(
    flows: pl.DataFrame, names: dict[str, str], codes: list[str], out: Path
) -> Path:
    t = _theme
    transitions = flows.select("from_release", "to_release").unique().sort("from_release").rows()
    years = sorted(flows["ref_year"].unique().to_list())
    height = len(transitions) * (0.36 * len(codes) + 0.75) + 2.1
    fig = _figure(
        height,
        "What changed between consecutive releases",
        "Net country-years per indicator and year. Blue: filled in late. Orange: withdrawn.",
    )
    axes = fig.subplots(len(transitions), 1, sharex=True, squeeze=False)[:, 0]
    nets = flows.filter(pl.col("code").is_in(codes) & (pl.col("net") != 0))["net"].abs()
    limit = max(5, int(np.percentile(nets.to_numpy(), 95))) if nets.len() else 5
    norm = TwoSlopeNorm(vmin=-limit, vcenter=0, vmax=limit)
    image = None
    for ax, (before, after) in zip(axes, transitions, strict=True):
        grid = np.full((len(codes), len(years)), np.nan)
        part = flows.filter((pl.col("from_release") == before) & pl.col("code").is_in(codes))
        for code, year, net in part.select("code", "ref_year", "net").iter_rows():
            grid[codes.index(code), years.index(year)] = net
        image = ax.pcolormesh(
            np.arange(len(years) + 1),
            np.arange(len(codes) + 1),
            grid,
            cmap=_diverging(),
            norm=norm,
            edgecolors=t.surface,
            linewidth=1.5,
        )
        ax.invert_yaxis()
        ax.set_title(f"{before} → {after} release", fontsize=12.5)
        ax.set_yticks(np.arange(len(codes)) + 0.5, [_label(c, names) for c in codes], fontsize=10.5)
        ticks = [j for j, y in enumerate(years) if y % 2 == 0]
        ax.set_xticks(np.array(ticks) + 0.5, [str(years[j]) for j in ticks])
        ax.grid(False)
        ax.tick_params(length=0)
        for spine in ax.spines.values():
            spine.set_visible(False)
    assert image is not None
    bar = fig.colorbar(
        image,
        ax=list(axes),
        orientation="horizontal",
        location="bottom",
        shrink=0.45,
        aspect=40,
        pad=0.02,
    )
    bar.set_label("Net country-years (added − withdrawn)", color=t.ink_2, fontsize=11)
    bar.outline.set_visible(False)
    bar.ax.tick_params(color=t.ink_2, labelcolor=t.ink_2, length=0, labelsize=10.5)
    return _save(fig, out)


def flow_bars(summary: pl.DataFrame, names: dict[str, str], codes: list[str], out: Path) -> Path:
    """Country-years backfilled (right) and withdrawn (left), per indicator and transition."""
    t = _theme
    transitions = summary.select("from_release", "to_release").unique().sort("from_release").rows()
    fig = _figure(
        0.46 * len(codes) + 2.7,
        "What each new release changed",
        "Country-years filled in late (right) and withdrawn (left) for years already due. "
        "› marks a bar cut short.",
        legend=True,
    )
    _legend(
        fig,
        [
            Patch(facecolor=t.series[0], label="filled in late"),
            Patch(facecolor=t.series[1], label="withdrawn"),
        ],
        2,
    )
    axes = fig.subplots(1, len(transitions), sharey=True, sharex=True, squeeze=False)[0]
    values = summary.select(pl.concat_list("added", "dropped").explode()).to_series().to_numpy()
    cap = float(max(10, np.ceil(2.2 * np.percentile(values, 90))))  # long outliers are clipped
    y = np.arange(len(codes))
    for k, (ax, (before, after)) in enumerate(zip(axes, transitions, strict=True)):
        part = summary.filter(pl.col("from_release") == before)
        added = dict(part.select("code", "added").iter_rows())
        dropped = dict(part.select("code", "dropped").iter_rows())
        a = np.array([added.get(c, 0) for c in codes], dtype=float)
        d = np.array([dropped.get(c, 0) for c in codes], dtype=float)
        ax.barh(y, np.minimum(a, cap), color=t.series[0], height=0.62)
        ax.barh(y, -np.minimum(d, cap), color=t.series[1], height=0.62)
        for yi, (av, dv) in enumerate(zip(a, d, strict=True)):
            if av:
                clipped = av > cap
                ax.text(
                    min(av, cap) + cap * 0.04,
                    yi,
                    f"+{int(av)}" + (" ›" if clipped else ""),
                    va="center",
                    fontsize=10.5,
                    color=t.ink if clipped else t.ink_2,
                    fontweight="bold" if clipped else "normal",
                )
            if dv:
                ax.text(
                    -min(dv, cap) - cap * 0.04,
                    yi,
                    f"−{int(dv)}",
                    va="center",
                    ha="right",
                    fontsize=10.5,
                    color=t.ink_2,
                )
        ax.axvline(0, color=t.ink_3, lw=1)
        ax.set_title(f"{before} → {after}", fontsize=12.5)
        ax.set_xlim(-cap * 0.75, cap * 1.45)
        ax.set_xticks([])
        ax.grid(False)
        ax.spines["bottom"].set_visible(False)
        ax.tick_params(axis="y", length=0)
        if k == 0:
            ax.set_yticks(y, [_label(c, names) for c in codes])
            ax.invert_yaxis()
    return _save(fig, out)


def value_revisions(
    revisions: pl.DataFrame, names: dict[str, str], codes: list[str], out: Path
) -> Path:
    t = _theme
    transitions = (
        revisions.select("from_release", "to_release").unique().sort("from_release").rows()
    )[-3:]
    fig = _figure(
        0.5 * len(codes) + 2.6,
        "How often published values are revised",
        "Share of values in two consecutive releases that changed by more than 0.001.",
        legend=True,
    )
    ramp = _ramp(5)
    colors = [ramp[i] for i in (1, 2, 4)][-len(transitions) :]
    handles = [
        Line2D([], [], marker="o", ls="", markersize=9, color=colors[i], label=f"{a} → {b}")
        for i, (a, b) in enumerate(transitions)
    ]
    _legend(fig, handles, len(transitions))
    ax = fig.subplots()
    y = np.arange(len(codes))
    shares = {
        (code, a): 100 * s
        for code, a, s in revisions.select("code", "from_release", "share_revised").iter_rows()
    }
    for i, code in enumerate(codes):
        xs = [shares[(code, a)] for a, _ in transitions if (code, a) in shares]
        if len(xs) > 1:
            ax.plot(
                [min(xs), max(xs)], [i, i], color=t.grid, lw=5, solid_capstyle="round", zorder=1
            )
    for slot, (before, _) in enumerate(transitions):
        ax.scatter(
            [shares.get((c, before), np.nan) for c in codes],
            y,
            s=90,
            color=colors[slot],
            edgecolor=t.surface,
            linewidth=2,
            zorder=3,
        )
    ax.set_yticks(y, [_label(c, names) for c in codes])
    ax.invert_yaxis()
    values = [v for v in shares.values() if np.isfinite(v)]
    ax.set_xlim(max(0.0, np.floor(min(values)) - 2), np.ceil(max(values)) + 2)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(decimals=0))
    ax.grid(axis="x", visible=True)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Values revised in the next release")
    return _save(fig, out)


def source_layers(layers: pl.DataFrame, names: dict[str, str], release: int, out: Path) -> Path:
    t = _theme
    latest = layers.filter(pl.col("release") == release)
    wide = latest.pivot(on="layer", index="code", values="n_countries").fill_null(0)
    for column in ("admin", "+ hhs", "+ model"):
        if column not in wide.columns:
            wide = wide.with_columns(pl.lit(0).alias(column))
    wide = wide.with_columns(
        (pl.col("+ hhs") - pl.col("admin")).alias("hhs_gain"),
        (pl.col("+ model") - pl.col("+ hhs")).alias("model_gain"),
    ).sort("+ model", descending=True)
    codes = wide["code"].to_list()
    parts = [
        ("admin", "Administrative data"),
        ("hhs_gain", "+ household surveys"),
        ("model_gain", "+ modelled estimates"),
    ]
    fig = _figure(
        0.52 * len(codes) + 2.6,
        "Where coverage comes from",
        f"Countries with any value in the {release} release, by the kind of source "
        "that reaches them.",
        legend=True,
    )
    _legend(
        fig, [Patch(facecolor=t.series[i], label=label) for i, (_, label) in enumerate(parts)], 3
    )
    ax = fig.subplots()
    left = np.zeros(len(codes))
    for slot, (column, _) in enumerate(parts):
        values = wide[column].to_numpy().astype(float)
        ax.barh(
            range(len(codes)),
            values,
            left=left,
            color=t.series[slot],
            height=0.64,
            edgecolor=t.surface,
            linewidth=2,
        )
        left += values
    for i, total in enumerate(left):
        ax.text(
            total + 0.8,
            i,
            f"{int(total)}",
            va="center",
            color=t.ink,
            fontsize=11.5,
            fontweight="bold",
        )
    ax.set_yticks(range(len(codes)), [_label(c, names) for c in codes])
    ax.invert_yaxis()
    ax.set_xlim(0, max(left.max(), 1) * 1.08)
    ax.grid(axis="x", visible=True)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Countries")
    return _save(fig, out)


def ground_truth(measured: pl.DataFrame, planted: pl.DataFrame, out: Path) -> Path:
    """Planted vs recovered series-level events, per release transition."""
    t = _theme
    kinds = [("backfilled", "Backfilled"), ("retracted", "Withdrawn"), ("revised", "Revised")]
    transitions = [f"{a}→{b}" for a, b in measured.select("from_release", "to_release").rows()]
    fig = _figure(
        5.0,
        "Checked against a planted ground truth",
        "Events between consecutive synthetic releases: bars are what the generator "
        "planted, diamonds what the pipeline found.",
        legend=True,
    )
    _legend(
        fig,
        [
            Patch(facecolor=t.ink_3, alpha=0.3, label="planted by the generator"),
            Line2D(
                [],
                [],
                marker="D",
                ls="",
                markersize=9,
                color=t.ink_2,
                label="recovered by the pipeline",
            ),
        ],
        2,
    )
    axes = fig.subplots(1, 3)
    x = np.arange(len(transitions))
    for slot, (ax, (kind, title)) in enumerate(zip(axes, kinds, strict=True)):
        truth = planted[kind].to_numpy()
        got = measured[kind].to_numpy()
        ax.bar(x, truth, width=0.62, color=t.series[slot], alpha=0.3)
        ax.scatter(
            x,
            got,
            s=90,
            marker="D",
            color=t.series[slot],
            edgecolor=t.surface,
            linewidth=1.8,
            zorder=3,
        )
        for xi, value in zip(x, got, strict=True):
            ax.annotate(
                f"{int(value):,}",
                (xi, value),
                xytext=(0, 11),
                textcoords="offset points",
                ha="center",
                va="bottom",
                color=t.ink,
                fontsize=11,
                fontweight="bold",
            )
        ax.set_xticks(x, transitions, fontsize=10.5)
        ax.set_title(title)
        ax.set_yticks([])
        ax.grid(False)
        ax.set_ylim(0, max(truth.max(), got.max()) * 1.3 + 1)
    return _save(fig, out)


def social_card(curves: pl.DataFrame, code: str, out: Path) -> Path:
    """1280x640 repository preview image: name, one-line pitch, a vintage-curve motif."""
    t = _theme
    fig = plt.figure(figsize=(12.8, 6.4), dpi=100)
    fig.text(
        0.06,
        0.80,
        "SDG 4 Data Revision Tracker",
        fontsize=40,
        fontweight="bold",
        color=t.ink,
        va="top",
    )
    fig.text(
        0.06,
        0.64,
        "How education statistics change from one data release to the next",
        fontsize=19,
        color=t.ink_2,
        va="top",
    )
    fig.text(
        0.06,
        0.55,
        "Reporting lag, backfill, withdrawals and value revisions",
        fontsize=15,
        color=t.ink_3,
        va="top",
    )
    ax = fig.add_axes((0.06, 0.08, 0.88, 0.36))
    panel = curves.filter(pl.col("code") == code)
    releases = sorted(panel["release"].unique().to_list())
    for release, color in zip(releases, _ramp(len(releases)), strict=True):
        line = panel.filter(pl.col("release") == release).sort("ref_year")
        ax.plot(line["ref_year"], line["n_countries"], color=color, lw=4.5)
    ax.axis("off")
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=100)
    plt.close(fig)
    return out


def hero_animation(curves: pl.DataFrame, names: dict[str, str], code: str, out: Path) -> Path:
    """Animated GIF: releases are layered on one at a time, then the stack holds."""
    panel = curves.filter(pl.col("code") == code)
    releases = sorted(panel["release"].unique().to_list())
    colors = dict(zip(releases, _ramp(len(releases)), strict=True))
    lines = {
        r: panel.filter(pl.col("release") == r).sort("ref_year").select("ref_year", "n_countries")
        for r in releases
    }
    fig = _figure(
        5.4,
        "Every release rewrites the past",
        f"{_label(code, names)}: countries with a value per reference year, one line per release.",
        legend=True,
    )
    _legend(fig, _release_handles(releases, colors), len(releases))
    ax = fig.subplots()
    ymax = max([1, *panel["n_countries"].to_list()]) * 1.12
    years = panel["ref_year"].to_list()
    steps = 14  # frames to draw one release
    hold = 20

    def frame(i: int) -> None:
        ax.clear()
        ax.set_xlim(min(years) - 0.4, max(years) + 0.4)
        ax.set_ylim(0, ymax)
        ax.set_xlabel("Reference year")
        ax.set_ylabel("Countries with a value")
        shown = min(len(releases), i // steps + 1)
        for k, r in enumerate(releases[:shown]):
            data = lines[r]
            frac = 1.0 if k < shown - 1 else min(1.0, (i % steps + 1) / steps)
            n = max(2, round(frac * data.height))
            latest = k == shown - 1
            ax.plot(
                data["ref_year"][:n],
                data["n_countries"][:n],
                color=colors[r],
                lw=3.2 if latest else 2.2,
            )
            if n == data.height:
                ax.scatter(
                    data["ref_year"][-1],
                    data["n_countries"][-1],
                    s=46,
                    color=colors[r],
                    edgecolor=_theme.surface,
                    linewidth=1.8,
                    zorder=3,
                )

    total = steps * len(releases) + hold
    anim = FuncAnimation(fig, lambda i: frame(min(i, steps * len(releases) - 1)), frames=total)
    out.parent.mkdir(parents=True, exist_ok=True)
    anim.save(out, writer=PillowWriter(fps=16), dpi=100)
    plt.close(fig)
    return out
