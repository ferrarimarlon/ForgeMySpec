#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-forgemyspec")

import matplotlib

matplotlib.use("Agg")

import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import numpy as np


WF_ALL = [5, 5, 5, 5, 5, 5, 4, 5, 4, 5, 5, 5, 5, 5, 5, 4.8]
NF_ALL = [4, 4, 4, 3, 4, 4, 4, 3, 5, 5, 4, 5, 4, 5, 5, 4.2]

GROUPS = {
    "Simple": {"idxs": [2, 9, 11, 14], "sample_size": 4},
    "Medium": {"idxs": [0, 5, 7, 12, 13], "sample_size": 5},
    "Complex": {"idxs": [1, 3, 4, 6, 8, 10], "sample_size": 6},
    "Security": {"idxs": [15], "sample_size": 1},
}

BG = "#FBF7F1"
PANEL = "#FFFDF9"
INK = "#231F20"
MUTED = "#6E6259"
GRID = "#E8DED1"
WITH_SPEC = "#F59E0B"
WITH_SPEC_SOFT = "#FCD58A"
WITHOUT_SPEC = "#6B7280"
WITHOUT_SPEC_SOFT = "#C7CDD6"
HIGHLIGHT = "#FFF1D6"


def pick_font() -> str:
    available = {font.name for font in fm.fontManager.ttflist}
    for candidate in ["Avenir Next", "Helvetica Neue", "Gill Sans", "Futura", "DejaVu Sans"]:
        if candidate in available:
            return candidate
    return "DejaVu Sans"


def build_rows() -> list[dict[str, float | int | str]]:
    rows: list[dict[str, float | int | str]] = []
    for label, group in GROUPS.items():
        wf_avg = float(np.mean([WF_ALL[i] for i in group["idxs"]]))
        nf_avg = float(np.mean([NF_ALL[i] for i in group["idxs"]]))
        gap = wf_avg - nf_avg
        gain_pct = (gap / nf_avg * 100) if nf_avg else 0.0
        rows.append(
            {
                "label": label,
                "sample_size": int(group["sample_size"]),
                "wf_avg": wf_avg,
                "nf_avg": nf_avg,
                "gap": gap,
                "gain_pct": gain_pct,
            }
        )
    return rows


def style_matplotlib(font_name: str) -> None:
    plt.rcParams.update(
        {
            "font.family": font_name,
            "axes.facecolor": BG,
            "figure.facecolor": BG,
            "savefig.facecolor": BG,
            "text.color": INK,
            "axes.labelcolor": MUTED,
            "axes.edgecolor": GRID,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
        }
    )


def draw_background(ax: plt.Axes, row_positions: list[float]) -> None:
    for y in row_positions:
        card = FancyBboxPatch(
            (0.10, y - 0.38),
            5.10,
            0.76,
            boxstyle="round,pad=0.02,rounding_size=0.08",
            linewidth=0,
            facecolor=PANEL,
            zorder=0,
        )
        ax.add_patch(card)


def plot_category_chart(output_dir: Path) -> tuple[Path, Path]:
    font_name = pick_font()
    style_matplotlib(font_name)
    rows = build_rows()

    labels = [row["label"] for row in rows]
    row_positions = list(range(len(rows)))[::-1]
    wf_values = [float(row["wf_avg"]) for row in rows]
    nf_values = [float(row["nf_avg"]) for row in rows]
    gains = [float(row["gain_pct"]) for row in rows]
    sample_sizes = [int(row["sample_size"]) for row in rows]

    fig, ax = plt.subplots(figsize=(11, 7.2))
    fig.subplots_adjust(left=0.21, right=0.94, top=0.78, bottom=0.14)

    draw_background(ax, row_positions)

    for x in np.arange(0, 5.1, 1.0):
        ax.axvline(x, color=GRID, lw=1, zorder=0)

    for y, nf, wf, gain, sample_size in zip(row_positions, nf_values, wf_values, gains, sample_sizes):
        ax.plot([nf, wf], [y, y], color=WITH_SPEC_SOFT, lw=8, solid_capstyle="round", zorder=2)
        ax.scatter(nf, y, s=230, color=WITHOUT_SPEC, edgecolor=BG, linewidth=1.8, zorder=3)
        ax.scatter(wf, y, s=280, color=WITH_SPEC, edgecolor=BG, linewidth=2.2, zorder=4)

        ax.text(
            nf - 0.06,
            y - 0.20,
            f"{nf:.2f}",
            ha="right",
            va="center",
            fontsize=10,
            color=WITHOUT_SPEC,
            fontweight="bold",
            zorder=5,
        )
        ax.text(
            wf + 0.06,
            y - 0.20,
            f"{wf:.2f}",
            ha="left",
            va="center",
            fontsize=10,
            color=WITH_SPEC,
            fontweight="bold",
            zorder=5,
        )
        ax.text(
            5.16,
            y,
            f"+{gain:.0f}%  |  n={sample_size}",
            ha="right",
            va="center",
            fontsize=10.5,
            color=INK,
            fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.35", fc=HIGHLIGHT, ec="none"),
            zorder=5,
        )

    ax.set_xlim(0, 5.35)
    ax.set_ylim(-0.75, len(rows) - 0.25)
    ax.set_xticks(np.arange(0, 5.1, 1.0))
    ax.set_xticklabels([f"{x:.0f}" for x in np.arange(0, 5.1, 1.0)], fontsize=11)
    ax.set_yticks(row_positions)
    ax.set_yticklabels(labels, fontsize=13, fontweight="bold")
    ax.tick_params(axis="y", length=0)
    ax.tick_params(axis="x", length=0)

    for spine in ax.spines.values():
        spine.set_visible(False)

    ax.set_xlabel("Average final score", fontsize=12, labelpad=16)

    fig.text(0.06, 0.92, "Average Score by Category", fontsize=24, fontweight="bold", color=INK)
    fig.text(
        0.06,
        0.875,
        "ForgeMySpec stays ahead in every category, with the sharpest lift in medium-complexity work.",
        fontsize=12.5,
        color=MUTED,
    )

    fig.text(0.06, 0.82, "WITHOUT spec", fontsize=11, color=WITHOUT_SPEC, fontweight="bold")
    fig.text(0.18, 0.82, "WITH spec", fontsize=11, color=WITH_SPEC, fontweight="bold")
    fig.text(0.27, 0.82, "Each connector shows the score lift from direct implementation to spec-driven execution.", fontsize=11, color=MUTED)

    footer = "Scores use the 0–5 quality rubric across 16 benchmark projects."
    fig.text(0.06, 0.055, footer, fontsize=10, color=MUTED)

    output_dir.mkdir(parents=True, exist_ok=True)
    png_path = output_dir / "average_score_by_category.png"
    svg_path = output_dir / "average_score_by_category.svg"
    fig.savefig(png_path, dpi=220, bbox_inches="tight")
    fig.savefig(svg_path, bbox_inches="tight")
    plt.close(fig)
    return png_path, svg_path


def main() -> int:
    root = Path(__file__).resolve().parent
    png_path, svg_path = plot_category_chart(root)
    print(f"Saved PNG -> {png_path}")
    print(f"Saved SVG -> {svg_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
