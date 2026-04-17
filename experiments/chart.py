#!/usr/bin/env python3
"""
SpecForge Comparative Chart — 16 projetos
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# ── Palette ───────────────────────────────────────────────────────────────
WF_DARK   = "#1565C0"
NF_DARK   = "#C62828"
BG        = "#F8F9FA"
GRID_CLR  = "#E0E0E0"

TIER_WF = {"S": "#43A047", "M": "#1E88E5", "C": "#FB8C00", "H": "#7B1FA2"}
TIER_NF = {"S": "#A5D6A7", "M": "#90CAF9", "C": "#FFE0B2", "H": "#CE93D8"}

# ── Data ──────────────────────────────────────────────────────────────────
# P1–P16 quality scores (0–5 scale)
wf_all = [5, 5, 5, 5, 5,  5, 4, 5, 4, 5,  5, 5, 5, 5, 5,  4.8]
nf_all = [4, 4, 4, 3, 4,  4, 4, 3, 5, 5,  4, 5, 4, 5, 5,  4.2]

# Tiers: S=simple (no gain), M=medium, C=complex, H=security
#   Simple:   P3, P10, P12, P15  → indices 2, 9, 11, 14
#   Medium:   P1, P6, P8, P13, P14 → 0, 5, 7, 12, 13
#   Complex:  P2, P4, P5, P7, P9, P11 → 1, 3, 4, 6, 8, 10
#   Security: P16 → 15
tier_idx = ["M","C","S","C","C",  "M","C","M","C","S",  "C","S","M","M","S",  "H"]

GROUPS = {
    "S": {"idxs": [2,9,11,14],       "label": "Simples\n(P3,P10,P12,P15)"},
    "M": {"idxs": [0,5,7,12,13],     "label": "Médio\n(P1,P6,P8,P13,P14)"},
    "C": {"idxs": [1,3,4,6,8,10],    "label": "Complexo\n(P2,P4,P5,P7,P9,P11)"},
    "H": {"idxs": [15],              "label": "Segurança\n(P16)"},
}

# Pre-compute averages
for t, g in GROUPS.items():
    g["wf_avg"] = np.mean([wf_all[i] for i in g["idxs"]])
    g["nf_avg"] = np.mean([nf_all[i] for i in g["idxs"]])
    g["gain"]   = (g["wf_avg"] - g["nf_avg"]) / g["nf_avg"] * 100

# "Onde o spec protege" — non-overlapping problem categories (P1–P16)
# Crashes/bloqueios: WF=3, NF=3  (both equal — neither wins)
# Bugs silenciosos:  WF=0, NF=4  (P4-eval, P8-falsy-zero, P11-missing-field, P16-env-bypass)
# Vulns segurança:   WF=0, NF=1  (P4 eval)
# Desvios conformidade: WF=0, NF=4 (P16: nested-dict, dead-code, env-timing, interoperability)
protect_cats = ["Crashes /\nBloqueios", "Bugs\nSilenciosos", "Vulns\nSegurança", "Desvios\nConformidade"]
protect_wf   = [3, 0, 0, 0]
protect_nf   = [3, 4, 1, 4]

# ── Figure layout ─────────────────────────────────────────────────────────
fig = plt.figure(figsize=(16, 10), facecolor=BG)
fig.suptitle(
    "SpecForge vs. Implementação Direta  ·  16 Projetos",
    fontsize=16, fontweight="bold", y=0.98
)

gs = fig.add_gridspec(2, 3, hspace=0.50, wspace=0.36,
                       left=0.06, right=0.97, top=0.91, bottom=0.07)

# ─────────────────────────────────────────────────────────────────────────
# Chart 1 — top row (full width): per-project quality scores
# ─────────────────────────────────────────────────────────────────────────
ax1 = fig.add_subplot(gs[0, :])
ax1.set_facecolor(BG)

x = np.arange(16)
bw = 0.38

for i in range(16):
    t = tier_idx[i]
    ax1.bar(i - bw/2, wf_all[i], bw, color=TIER_WF[t], linewidth=0, zorder=3)
    ax1.bar(i + bw/2, nf_all[i], bw, color=TIER_NF[t], linewidth=0, zorder=3)
    # arrow from NF to WF when spec wins
    diff = wf_all[i] - nf_all[i]
    if diff > 0.1:
        ax1.annotate(
            "", xy=(i - bw/2, wf_all[i] + 0.05),
            xytext=(i + bw/2, nf_all[i] + 0.05),
            arrowprops=dict(arrowstyle="->", color="#555555", lw=0.9),
            zorder=4
        )

ax1.set_xticks(x)
ax1.set_xticklabels([f"P{i+1}" for i in range(16)], fontsize=9)
ax1.set_ylim(0, 6.4)
ax1.set_yticks([0, 1, 2, 3, 4, 5])
ax1.set_ylabel("Score (0–5)", fontsize=9)
ax1.set_title(
    "Score de qualidade final — barra esquerda = COM spec  |  barra direita = SEM spec  |  seta = spec ganhou",
    fontsize=10
)
ax1.axhline(5, color="gray", ls="--", alpha=0.25, lw=0.8, zorder=2)
ax1.yaxis.grid(True, color=GRID_CLR, zorder=1)
ax1.set_axisbelow(True)

# vertical tier separators
for sep in [4.5, 9.5, 13.5]:
    ax1.axvline(sep, color="#BDBDBD", ls=":", lw=0.8, zorder=2)

# tier labels at top
tier_labels_text = {4.5/2: "Médio", (4.5+9.5)/2: "Complexo",
                    (9.5+13.5)/2: "Simples", (13.5+15)/2: "Médio"}
ax1.text(1.0,  6.15, "MÉDIO",    ha="center", fontsize=8, color="#555", style="italic")
ax1.text(5.25, 6.15, "COMPLEXO", ha="center", fontsize=8, color="#555", style="italic")
ax1.text(11.0, 6.15, "SIMPLES",  ha="center", fontsize=8, color="#555", style="italic")
ax1.text(13.5, 6.15, "MÉD.",     ha="center", fontsize=8, color="#555", style="italic")
ax1.text(15.0, 6.15, "SEG.",     ha="center", fontsize=8, color="#555", style="italic")

legend_handles = []
for t, name in [("S","Simples"), ("M","Médio"), ("C","Complexo"), ("H","Segurança")]:
    legend_handles += [
        mpatches.Patch(color=TIER_WF[t], label=f"{name} COM"),
        mpatches.Patch(color=TIER_NF[t], label=f"{name} SEM"),
    ]
ax1.legend(handles=legend_handles, ncol=4, fontsize=7.5,
           loc="lower right", framealpha=0.85)

# ─────────────────────────────────────────────────────────────────────────
# Chart 2 — bottom left: % gain by complexity tier
# ─────────────────────────────────────────────────────────────────────────
ax2 = fig.add_subplot(gs[1, 0])
ax2.set_facecolor(BG)

tier_order = ["S", "M", "C", "H"]
gains  = [GROUPS[t]["gain"]   for t in tier_order]
colors = [TIER_WF[t]          for t in tier_order]
xlbls  = [GROUPS[t]["label"]  for t in tier_order]

bars2 = ax2.bar(xlbls, gains, color=colors, width=0.55, linewidth=0, zorder=3)
ax2.set_ylabel("Ganho médio (%)", fontsize=9)
ax2.set_title("% Ganho COM spec\npor Complexidade", fontsize=10)
ax2.axhline(0, color="black", lw=0.8, zorder=2)
ax2.yaxis.grid(True, color=GRID_CLR, zorder=1)
ax2.set_axisbelow(True)
ax2.tick_params(axis="x", labelsize=8.5)

for bar, g, t in zip(bars2, gains, tier_order):
    wa, na = GROUPS[t]["wf_avg"], GROUPS[t]["nf_avg"]
    ax2.text(bar.get_x() + bar.get_width()/2,
             g + 0.6,
             f"+{g:.0f}%\n({wa:.1f} vs {na:.1f})",
             ha="center", va="bottom", fontsize=8.5, fontweight="bold")

ax2.set_ylim(-1, max(gains) * 1.42)

# ─────────────────────────────────────────────────────────────────────────
# Chart 3 — bottom middle: average score comparison by tier
# ─────────────────────────────────────────────────────────────────────────
ax3 = fig.add_subplot(gs[1, 1])
ax3.set_facecolor(BG)

x3    = np.arange(4)
bw3   = 0.34
wf3   = [GROUPS[t]["wf_avg"] for t in tier_order]
nf3   = [GROUPS[t]["nf_avg"] for t in tier_order]
xlbl3 = ["Simples", "Médio", "Complexo", "Segurança"]

b_wf = ax3.bar(x3 - bw3/2, wf3, bw3, label="COM spec", color=WF_DARK, linewidth=0, zorder=3)
b_nf = ax3.bar(x3 + bw3/2, nf3, bw3, label="SEM spec", color=NF_DARK, linewidth=0, zorder=3)
ax3.set_xticks(x3)
ax3.set_xticklabels(xlbl3, fontsize=9)
ax3.set_ylabel("Score médio (0–5)", fontsize=9)
ax3.set_title("Score Médio\npor Categoria", fontsize=10)
ax3.set_ylim(0, 6.2)
ax3.axhline(5, color="gray", ls="--", alpha=0.25, lw=0.8, zorder=2)
ax3.yaxis.grid(True, color=GRID_CLR, zorder=1)
ax3.set_axisbelow(True)
ax3.legend(fontsize=9)

for i, (w, n) in enumerate(zip(wf3, nf3)):
    ax3.text(i - bw3/2, w + 0.07, f"{w:.2f}", ha="center", va="bottom", fontsize=8.5, color=WF_DARK, fontweight="bold")
    ax3.text(i + bw3/2, n + 0.07, f"{n:.2f}", ha="center", va="bottom", fontsize=8.5, color=NF_DARK, fontweight="bold")

# ─────────────────────────────────────────────────────────────────────────
# Chart 4 — bottom right: "onde o spec protege"
# ─────────────────────────────────────────────────────────────────────────
ax4 = fig.add_subplot(gs[1, 2])
ax4.set_facecolor(BG)

x4  = np.arange(len(protect_cats))
bw4 = 0.34
b4w = ax4.bar(x4 - bw4/2, protect_wf, bw4, label="COM spec", color=WF_DARK, linewidth=0, zorder=3)
b4n = ax4.bar(x4 + bw4/2, protect_nf, bw4, label="SEM spec", color=NF_DARK, linewidth=0, zorder=3)
ax4.set_xticks(x4)
ax4.set_xticklabels(protect_cats, fontsize=8.5)
ax4.set_ylabel("Ocorrências (P1–P16)", fontsize=9)
ax4.set_title("Onde o Spec Protege\n(P1–P16)", fontsize=10)
ax4.yaxis.grid(True, color=GRID_CLR, zorder=1)
ax4.set_axisbelow(True)
ax4.legend(fontsize=9)
ax4.set_ylim(0, max(protect_nf) * 1.38)

for i, (w, n) in enumerate(zip(protect_wf, protect_nf)):
    ax4.text(i - bw4/2, w + 0.06, str(w), ha="center", va="bottom", fontsize=9,
             color=WF_DARK, fontweight="bold")
    ax4.text(i + bw4/2, n + 0.06, str(n), ha="center", va="bottom", fontsize=9,
             color=NF_DARK, fontweight="bold")

# ── Save ──────────────────────────────────────────────────────────────────
out = "/Users/marlonferrari/Desktop/demo/experiments/specforge_chart.png"
plt.savefig(out, dpi=160, bbox_inches="tight", facecolor=fig.get_facecolor())
print(f"Saved → {out}")
