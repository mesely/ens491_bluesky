"""
PHASE 3c — Statistical Validation Layer
Applies rigorous statistical tests to sentiment and hate-speech distributions.
All multi-comparison p-values are corrected with FDR-BH.

Tests performed:
  1. Kruskal-Wallis H (global: do parties differ in sentiment?)
  2. Pairwise Mann-Whitney U (post-hoc, + rank-biserial effect size r)
  3. Chi-square + Cramér's V (hate speech × party independence)
  4. Wilson 95% CI for hate-speech rates per party
  5. Pearson r (like_count ~ hate speech probability)

Outputs:
  outputs/statistical_test_results.json
  outputs/figures/G_statistical_forest_plot.png
  outputs/figures/G_statistical_forest_plot.pdf
"""

import os
import sys
import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


# ─── Prerequisites ────────────────────────────────────────────────────────────

def require(path: str) -> None:
    if not Path(path).exists():
        print(f"[ERROR] Required file not found: {path}")
        print("Run 05_sentiment_analysis.py first.")
        sys.exit(1)


# ─── Paths & Config ───────────────────────────────────────────────────────────

SENTIMENT_CSV = "outputs/sentiment_results.csv"
OUTPUT_JSON   = "outputs/statistical_test_results.json"
FIGURES_DIR   = "outputs/figures"

MIN_PARTY_N  = 20        # skip parties with fewer posts
ALPHA        = 0.05      # significance threshold
SENT_MAP     = {"positive": 1, "neutral": 0, "negative": -1}


# ─── Stats Helpers ────────────────────────────────────────────────────────────

def kruskal_wallis_test(groups: list[np.ndarray]) -> dict:
    from scipy.stats import kruskal
    stat, p = kruskal(*groups)
    return {
        "statistic": round(float(stat), 4),
        "p_value":   round(float(p), 6),
        "significant": bool(p < ALPHA),
        "interpretation": (
            "Parties differ significantly in sentiment (p<0.05)"
            if p < ALPHA else
            "No significant difference across parties (p≥0.05)"
        ),
    }


def pairwise_mannwhitney(df: pd.DataFrame, parties: list[str]) -> list[dict]:
    from scipy.stats import mannwhitneyu
    from statsmodels.stats.multitest import multipletests

    pairs: list[dict] = []
    for i in range(len(parties)):
        for j in range(i + 1, len(parties)):
            a = df[df["party"] == parties[i]]["sent_num"].dropna().values
            b = df[df["party"] == parties[j]]["sent_num"].dropna().values
            if len(a) < 5 or len(b) < 5:
                continue
            u, p = mannwhitneyu(a, b, alternative="two-sided")
            n1, n2 = len(a), len(b)
            # Rank-biserial correlation (effect size)
            r = float(1 - (2 * u) / (n1 * n2))
            pairs.append({
                "party_a":       parties[i],
                "party_b":       parties[j],
                "u_stat":        round(float(u), 2),
                "p_raw":         round(float(p), 6),
                "effect_size_r": round(r, 4),
                "n_a":           n1,
                "n_b":           n2,
            })

    if not pairs:
        return []

    # FDR-BH correction
    p_vals = [row["p_raw"] for row in pairs]
    _, p_adj, _, _ = multipletests(p_vals, method="fdr_bh")
    for row, p_a in zip(pairs, p_adj):
        row["p_adjusted_fdr"] = round(float(p_a), 6)
        row["significant"]    = bool(p_a < ALPHA)

    return sorted(pairs, key=lambda x: abs(x["effect_size_r"]), reverse=True)


def chi2_hatespeech(df: pd.DataFrame) -> dict:
    from scipy.stats import chi2_contingency
    contingency = pd.crosstab(df["party"], df["hate_speech"])
    chi2, p, dof, _ = chi2_contingency(contingency)
    n          = int(contingency.sum().sum())
    cramers_v  = float(np.sqrt(chi2 / (n * (min(contingency.shape) - 1))))
    strength   = "strong" if cramers_v > 0.3 else "moderate" if cramers_v > 0.1 else "weak"
    return {
        "chi2":       round(float(chi2), 4),
        "p_value":    round(float(p), 6),
        "dof":        int(dof),
        "cramers_v":  round(cramers_v, 4),
        "n":          n,
        "interpretation": f"Cramér's V={cramers_v:.3f} → {strength} effect size",
        "significant": bool(p < ALPHA),
    }


def wilson_ci(df: pd.DataFrame) -> dict[str, dict]:
    from statsmodels.stats.proportion import proportion_confint
    result = {}
    for party, g in df.groupby("party"):
        if len(g) < MIN_PARTY_N:
            continue
        n_hate  = int(g["is_hate"].sum())
        n_total = len(g)
        lo, hi  = proportion_confint(n_hate, n_total, alpha=ALPHA, method="wilson")
        result[str(party)] = {
            "n":           n_total,
            "hate_count":  n_hate,
            "hate_rate":   round(n_hate / n_total, 4),
            "ci_95_low":   round(float(lo), 4),
            "ci_95_high":  round(float(hi), 4),
        }
    return result


def pearson_likes_hate(df: pd.DataFrame) -> dict:
    from scipy.stats import pearsonr
    mask = df["like_count"].notna() & df["is_hate"].notna()
    r, p = pearsonr(df.loc[mask, "like_count"], df.loc[mask, "is_hate"])
    return {
        "pearson_r": round(float(r), 4),
        "p_value":   round(float(p), 6),
         "significant": bool(p < ALPHA),
    }


# ─── Forest Plot ──────────────────────────────────────────────────────────────

def plot_forest_plot(pairwise_results: list[dict]) -> None:
    """
    Horizontal bar chart of rank-biserial effect sizes for significant pairs.
    Negative r → party_a more negative; positive r → party_b more negative.
    """
    sig = [row for row in pairwise_results if row.get("significant")]
    if not sig:
        print("  No significant pairs — skipping forest plot.")
        return

    sig = sorted(sig, key=lambda x: x["effect_size_r"])
    labels  = [f"{r['party_a']}\nvs {r['party_b']}" for r in sig]
    effects = [r["effect_size_r"] for r in sig]
    colors  = ["#E74C3C" if e < 0 else "#27AE60" for e in effects]

    fig_height = max(4, len(sig) * 0.55 + 1.5)
    fig, ax = plt.subplots(figsize=(9, fig_height))
    ax.barh(labels, effects, color=colors, height=0.55, edgecolor="white")
    ax.axvline(0, color="black", linewidth=0.8, linestyle="--")
    ax.set_xlabel("Rank-Biserial Correlation (Effect Size r)", fontsize=10)
    ax.set_title(
        "Pairwise Sentiment Differences (FDR-corrected)\n"
        "Negative r → left party more negative",
        fontsize=11, pad=8,
    )
    ax.tick_params(axis="y", labelsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()

    for ext in ("png", "pdf"):
        path = os.path.join(FIGURES_DIR, f"G_statistical_forest_plot.{ext}")
        fig.savefig(path, dpi=300, bbox_inches="tight")
        print(f"  Saved: {path}")
    plt.close(fig)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    require(SENTIMENT_CSV)
    os.makedirs("outputs", exist_ok=True)
    os.makedirs(FIGURES_DIR, exist_ok=True)

    df = pd.read_csv(SENTIMENT_CSV, encoding="utf-8-sig")
    df = df[df["party"].notna() & (df["party"].str.strip() != "")]
    df["sent_num"] = df["sentiment"].map(SENT_MAP)
    df["is_hate"]  = (df["hate_speech"] == "Yes").astype(int)
    print(f"Loaded {len(df)} posts for statistical testing.")

    # Parties with enough data
    party_counts  = df["party"].value_counts()
    valid_parties = party_counts[party_counts >= MIN_PARTY_N].index.tolist()
    df_valid      = df[df["party"].isin(valid_parties)]
    print(f"Parties with ≥{MIN_PARTY_N} posts: {len(valid_parties)}")

    results: dict = {}

    # 1. Kruskal-Wallis
    print("\n[1] Kruskal-Wallis (global sentiment difference) …")
    groups = [g["sent_num"].dropna().values
              for _, g in df_valid.groupby("party")]
    results["kruskal_wallis_sentiment"] = kruskal_wallis_test(groups)
    print(f"  {results['kruskal_wallis_sentiment']['interpretation']}")

    # 2. Pairwise Mann-Whitney U
    print("\n[2] Pairwise Mann-Whitney U + FDR correction …")
    pairwise = pairwise_mannwhitney(df_valid, valid_parties)
    results["pairwise_mannwhitney"] = pairwise
    n_sig = sum(1 for r in pairwise if r.get("significant"))
    print(f"  {n_sig} / {len(pairwise)} pairs significant (FDR-BH α={ALPHA})")

    # 3. Chi-square: hate speech × party
    print("\n[3] Chi-square: hate speech × party …")
    results["chi2_hatespeech_party"] = chi2_hatespeech(df_valid)
    print(f"  {results['chi2_hatespeech_party']['interpretation']}")

    # 4. Wilson 95% CI for hate speech rates
    print("\n[4] Wilson 95% CI for hate speech rates …")
    results["hate_speech_confidence_intervals"] = wilson_ci(df_valid)
    for party, info in list(results["hate_speech_confidence_intervals"].items())[:3]:
        print(f"  {party}: {info['hate_rate']:.1%} "
              f"[{info['ci_95_low']:.1%}, {info['ci_95_high']:.1%}]")

    # 5. Pearson: likes ~ hate speech
    print("\n[5] Pearson r: like_count ~ hate_speech …")
    results["correlation_likes_hate"] = pearson_likes_hate(df_valid)
    print(f"  r={results['correlation_likes_hate']['pearson_r']}, "
          f"p={results['correlation_likes_hate']['p_value']}")

    # Save JSON
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nSaved → {OUTPUT_JSON}")

    # Forest plot
    plot_forest_plot(pairwise)

    print("Done.")


if __name__ == "__main__":
    main()
