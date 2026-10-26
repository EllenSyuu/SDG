"""Static figures, rendered in a light and a dark theme.

Colour follows the job it does: ordered releases use one sequential hue (older =
fainter, newest = strongest), net additions/withdrawals a two-hue diverging scale with
a neutral midpoint, and data sources three fixed categorical slots. Text always uses
ink tokens, never a series colour. Title blocks are positioned in inches from the top
edge, so they never collide with legends or axes whatever the figure height.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import polars as pl
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Patch


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
    surface="#fcfcfb",
    ink="#0b0b0b",
    ink_2="#52514e",
    ink_3="#8a8984",
    grid="#e4e3df",
    series=("#2a78d6", "#eb6834", "#1baf7a"),
    ramp=("#b7d3f3", "#7fb0ea", "#3d84d9", "#1a5aa8", "#0e3a73"),
    diverging=("#d95926", "#f3f2ee", "#2a78d6"),
)
DARK = Theme(
    name="dark",
    surface="#0d1117",  # GitHub dark canvas, so README images sit flush
    ink="#f0efec",
    ink_2="#c3c2b7",
    ink_3="#8f8e86",
    grid="#2a2e35",
    series=("#3987e5", "#d95926", "#199e70"),
    ramp=("#1d3f6e", "#2a5f9f", "#3d84d9", "#79acec", "#c2dbf7"),
    diverging=("#d95926", "#30343b", "#3987e5"),
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
            "figure.facecolor": t.surface,
            "axes.facecolor": t.surface,
            "savefig.facecolor": t.surface,
            "axes.edgecolor": t.grid,
            "axes.labelcolor": t.ink_2,
            "axes.titlecolor": t.ink,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.color": t.grid,
            "grid.linewidth": 0.6,
            "xtick.color": t.ink_2,
            "ytick.color": t.ink_2,
            "text.color": t.ink,
            "legend.labelcolor": t.ink_2,
            "legend.frameon": False,
            "font.size": 9,
            "axes.titlesize": 10,
            "axes.titleweight": "bold",
            "axes.titlelocation": "left",
            "savefig.dpi": 200,
            "axes.axisbelow": True,
        }
    )
    return t


set_theme("light")


def _ramp(n: int) -> list[str]:
    ramp = _theme.ramp
    if n <= len(ramp):
        return list(ramp[len(ramp) - n :])
    cmap = LinearSegmentedColormap.from_list("ramp", list(ramp))
    return [matplotlib.colors.to_hex(cmap(x)) for x in np.linspace(0, 1, n)]


def _diverging() -> LinearSegmentedColormap:
    return LinearSegmentedColormap.from_list("div", list(_theme.diverging))


def _title(fig: Figure, title: str, subtitle: str) -> None:
    h = fig.get_figheight()
    fig.text(
        0.01,
        1 - 0.15 / h,
        title,
        ha="left",
        va="top",
        fontsize=13,
        fontweight="bold",
        color=_theme.ink,
    )
    fig.text(0.01, 1 - 0.47 / h, subtitle, ha="left", va="top", fontsize=9.5, color=_theme.ink_2)


def _save(fig: Figure, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    plt.close(fig)
    return out


def _label(code: str, names: dict[str, str]) -> str:
    return f"{code}  {names.get(code, '')}".strip()


# --------------------------------------------------------------------------- hero


def hero(curves: pl.DataFrame, names: dict[str, str], code: str, out: Path) -> Path:
    """One indicator, every release: reporting lag on the left, one year's drift on the right."""
    t = _theme
    panel = curves.filter(pl.col("code") == code)
    releases = sorted(panel["release"].unique().to_list())
    colors = dict(zip(releases, _ramp(len(releases)), strict=True))
    fig = plt.figure(figsize=(12, 4.8))
    grid = fig.add_gridspec(
        1,
        2,
        width_ratios=(2.5, 1),
        wspace=0.18,
        left=0.06,
        right=0.985,
        bottom=0.13,
        top=1 - 1.25 / 4.8,
    )
    ax = fig.add_subplot(grid[0])
    for release in releases:
        line = panel.filter(pl.col("release") == release).sort("ref_year")
        latest = release == releases[-1]
        ax.plot(
            line["ref_year"],
            line["n_countries"],
            color=colors[release],
            lw=2.6 if latest else 1.8,
            label=f"{release} release",
            zorder=3 if latest else 2,
        )
        ax.scatter(
            line["ref_year"][-1],
            line["n_countries"][-1],
            s=36,
            color=colors[release],
            edgecolor=t.surface,
            linewidth=1.5,
            zorder=4,
        )
    ax.set_ylim(bottom=0)
    ax.set_xlabel("Reference year")
    ax.set_ylabel("Countries with a value")
    ax.set_title(f"{_label(code, names)}: one curve per release", loc="left")
    ax.legend(loc="lower left", ncols=len(releases))

    # Annotate the newest year of the newest release (reporting lag).
    newest = panel.filter(pl.col("release") == releases[-1]).sort("ref_year")
    x_last, y_last = newest["ref_year"][-1], newest["n_countries"][-1]
    ax.annotate(
        "reporting lag:\nthe newest year is\nonly partly reported",
        xy=(x_last, y_last),
        xytext=(x_last - 5.2, y_last + 6),
        color=t.ink_2,
        fontsize=8.5,
        arrowprops={"arrowstyle": "-|>", "color": t.ink_3, "lw": 1},
    )

    # Right: how one reference year's count moves across releases.
    year = releases[0] - 1
    drift = panel.filter(pl.col("ref_year") == year).sort("release")
    bx = fig.add_subplot(grid[1])
    xs = [str(r) for r in drift["release"].to_list()]
    bx.bar(xs, drift["n_countries"], color=[colors[r] for r in drift["release"]], width=0.62)
    for i, n in enumerate(drift["n_countries"].to_list()):
        bx.text(i, n + 0.6, str(n), ha="center", va="bottom", color=t.ink_2, fontsize=9)
    bx.set_title(f"Reference year {year}, as each release saw it", loc="left")
    bx.set_xlabel("Release")
    bx.grid(axis="x", visible=False)
    counts = drift["n_countries"].to_list()
    bx.set_ylim(0, max([*counts, 1]) * 1.18)

    _title(
        fig,
        "The same statistic, published four times",
        "Synthetic demo data. Each release adds the newest year, backfills older years "
        "and revises what it published before.",
    )
    return _save(fig, out)


# --------------------------------------------------------------------------- panels


def vintage_curves(
    curves: pl.DataFrame, names: dict[str, str], codes: list[str], out: Path
) -> Path:
    releases = sorted(curves["release"].unique().to_list())
    colors = dict(zip(releases, _ramp(len(releases)), strict=True))
    ncols = 3
    nrows = int(np.ceil(len(codes) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(12, 2.9 * nrows + 1.2), squeeze=False)
    for ax, code in zip(axes.ravel(), codes, strict=False):
        panel = curves.filter(pl.col("code") == code)
        for release in releases:
            line = panel.filter(pl.col("release") == release).sort("ref_year")
            ax.plot(
                line["ref_year"],
                line["n_countries"],
                color=colors[release],
                lw=2.4 if release == releases[-1] else 1.6,
                label=f"{release} release",
            )
        ax.set_title(_label(code, names))
        ax.set_ylim(bottom=0)
    for ax in axes.ravel()[len(codes) :]:
        ax.axis("off")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="upper left",
        ncols=len(releases),
        bbox_to_anchor=(0.005, 1 - 0.72 / fig.get_figheight()),
    )
    _title(
        fig,
        "Vintage curves, by indicator",
        "Countries reporting each reference year, as seen by each release (synthetic demo data).",
    )
    fig.supxlabel("Reference year", color=_theme.ink_2)
    fig.supylabel("Countries with a value", color=_theme.ink_2)
    fig.tight_layout(rect=(0, 0, 1, 1 - 1.1 / fig.get_figheight()))
    return _save(fig, out)


def transition_heatmap(
    flows: pl.DataFrame, names: dict[str, str], codes: list[str], out: Path
) -> Path:
    t = _theme
    transitions = flows.select("from_release", "to_release").unique().sort("from_release").rows()
    years = sorted(flows["ref_year"].unique().to_list())
    width = 4.0 * len(transitions) + 4.4
    height = 0.36 * len(codes) + 2.5
    fig = plt.figure(figsize=(width, height))
    left, right, gap = 3.4 / width, 1.0 - 1.1 / width, 0.25 / width
    panel_w = (right - left - gap * (len(transitions) - 1)) / len(transitions)
    bottom, top = 0.75 / height, 1.0 - 1.2 / height
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
        image = ax.imshow(
            grid, cmap=_diverging(), norm=norm, aspect="auto", interpolation="nearest"
        )
        ax.set_title(f"{before} → {after}", fontsize=9.5)
        ticks = [j for j, y in enumerate(years) if y % 4 == 0]
        ax.set_xticks(ticks, [str(years[j]) for j in ticks])
        if i == 0:
            ax.set_yticks(range(len(codes)), [_label(c, names) for c in codes])
        else:
            ax.set_yticks([])
        ax.tick_params(length=0)
        ax.grid(False)
        for spine in ax.spines.values():
            spine.set_visible(False)
    assert image is not None
    cax = fig.add_axes((right + 0.25 / width, bottom, 0.16 / width, top - bottom))
    bar = fig.colorbar(image, cax=cax)
    bar.set_label("Net country-years (added − withdrawn)", color=t.ink_2)
    bar.outline.set_visible(False)
    bar.ax.tick_params(color=t.ink_2, labelcolor=t.ink_2, length=0)
    _title(
        fig,
        "What changed between consecutive releases",
        "Blue: country-years backfilled for an already-eligible year. Orange: withdrawn. "
        "Neutral: unchanged. Blank: not yet eligible.",
    )
    return _save(fig, out)


def value_revisions(
    revisions: pl.DataFrame, names: dict[str, str], codes: list[str], out: Path
) -> Path:
    t = _theme
    transitions = (
        revisions.select("from_release", "to_release").unique().sort("from_release").rows()
    )
    fig, ax = plt.subplots(figsize=(9, 0.42 * len(codes) + 2.3))
    y = np.arange(len(codes))
    for row in range(len(codes)):
        ax.axhline(row, color=t.grid, lw=0.6, zorder=1)
    for slot, (before, after) in enumerate(transitions[-3:]):
        part = revisions.filter(pl.col("from_release") == before)
        share = dict(part.select("code", "share_revised").iter_rows())
        ax.scatter(
            [100 * share.get(c, np.nan) for c in codes],
            y,
            s=54,
            color=t.series[slot],
            edgecolor=t.surface,
            linewidth=1.8,
            zorder=3,
            label=f"{before} → {after}",
        )
    ax.set_yticks(y, [_label(c, names) for c in codes])
    ax.invert_yaxis()
    ax.set_xlim(left=0)
    ax.set_xlabel("Published values changed in the next release (%)")
    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", length=0)
    fig.legend(loc="upper left", ncols=3, bbox_to_anchor=(0.005, 1 - 0.72 / fig.get_figheight()))
    _title(
        fig,
        "How often published values are revised",
        "Same series, country and reference year in consecutive releases; changes ≤ 0.001 "
        "ignored (synthetic demo data).",
    )
    fig.tight_layout(rect=(0, 0, 1, 1 - 1.05 / fig.get_figheight()))
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
    ).sort("+ model")
    codes = wide["code"].to_list()
    fig, ax = plt.subplots(figsize=(9, 0.42 * len(codes) + 2.2))
    left = np.zeros(len(codes))
    parts = [
        ("admin", "Administrative"),
        ("hhs_gain", "+ household survey"),
        ("model_gain", "+ modelled"),
    ]
    for slot, (column, _) in enumerate(parts):
        values = wide[column].to_numpy().astype(float)
        ax.barh(
            range(len(codes)),
            values,
            left=left,
            color=t.series[slot],
            height=0.62,
            edgecolor=t.surface,
            linewidth=2,
        )
        left += values
    for i, total in enumerate(left):
        ax.text(total + 0.6, i, f"{int(total)}", va="center", color=t.ink_2, fontsize=8.5)
    ax.set_yticks(range(len(codes)), [_label(c, names) for c in codes])
    ax.set_xlabel(f"Countries with any value, eligible years ({release} release)")
    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", length=0)
    handles = [Patch(facecolor=t.series[i], label=label) for i, (_, label) in enumerate(parts)]
    fig.legend(
        handles=handles,
        loc="upper left",
        ncols=3,
        bbox_to_anchor=(0.005, 1 - 0.72 / fig.get_figheight()),
    )
    _title(
        fig,
        "Where coverage comes from",
        "Countries reached by administrative data alone, and the extra countries reached "
        "by surveys and models (synthetic demo data).",
    )
    fig.tight_layout(rect=(0, 0, 1, 1 - 1.05 / fig.get_figheight()))
    return _save(fig, out)


def ground_truth(measured: pl.DataFrame, planted: pl.DataFrame, out: Path) -> Path:
    """Planted vs recovered series-level events, per release transition."""
    t = _theme
    kinds = ["backfilled", "retracted", "revised"]
    transitions = [f"{a} → {b}" for a, b in measured.select("from_release", "to_release").rows()]
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.6), sharey=False)
    x = np.arange(len(transitions))
    for slot, (ax, kind) in enumerate(zip(axes, kinds, strict=True)):
        truth = planted[kind].to_numpy()
        got = measured[kind].to_numpy()
        ax.bar(x, truth, width=0.62, color=t.series[slot], alpha=0.35, label="planted")
        ax.scatter(
            x,
            got,
            s=70,
            marker="D",
            color=t.series[slot],
            edgecolor=t.surface,
            linewidth=1.5,
            zorder=3,
            label="recovered",
        )
        for xi, value in zip(x, got, strict=True):
            ax.annotate(
                f"{int(value)}",
                (xi, value),
                xytext=(0, 9),
                textcoords="offset points",
                ha="center",
                va="bottom",
                color=t.ink_2,
                fontsize=8.5,
            )
        ax.set_xticks(x, transitions)
        ax.set_title(kind.capitalize())
        ax.grid(axis="x", visible=False)
        ax.set_ylim(0, max(truth.max(), got.max()) * 1.25 + 2)
    handles = [
        Patch(facecolor=t.ink_3, alpha=0.35, label="planted by the generator"),
        Line2D([], [], marker="D", ls="", color=t.ink_3, label="recovered by the pipeline"),
    ]
    fig.legend(
        handles=handles,
        loc="upper left",
        ncols=2,
        bbox_to_anchor=(0.005, 1 - 0.72 / fig.get_figheight()),
    )
    _title(
        fig,
        "Validated against a planted ground truth",
        "Series-level events between consecutive synthetic releases. "
        "The pipeline recovers every count exactly.",
    )
    fig.tight_layout(rect=(0, 0, 1, 1 - 1.05 / fig.get_figheight()))
    return _save(fig, out)


def social_card(curves: pl.DataFrame, code: str, out: Path) -> Path:
    """1280x640 repository preview image: name, one-line pitch, a vintage-curve motif."""
    t = _theme
    fig = plt.figure(figsize=(12.8, 6.4), dpi=100)
    fig.text(0.06, 0.80, "sdg4vintage", fontsize=46, fontweight="bold", color=t.ink, va="top")
    fig.text(
        0.06,
        0.62,
        "Release-vintage analytics for SDG 4 education statistics",
        fontsize=20,
        color=t.ink_2,
        va="top",
    )
    fig.text(
        0.06,
        0.53,
        "reporting lag · backfill · withdrawals · value revisions",
        fontsize=15,
        color=t.ink_3,
        va="top",
    )
    ax = fig.add_axes((0.06, 0.08, 0.88, 0.36))
    panel = curves.filter(pl.col("code") == code)
    releases = sorted(panel["release"].unique().to_list())
    for release, color in zip(releases, _ramp(len(releases)), strict=True):
        line = panel.filter(pl.col("release") == release).sort("ref_year")
        ax.plot(line["ref_year"], line["n_countries"], color=color, lw=4)
    ax.axis("off")
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=100)
    plt.close(fig)
    return out
