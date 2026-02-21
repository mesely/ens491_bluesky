"""
PHASE 5 — Paper-Quality Visualizations
Produces all figures used in the research paper + interactive supplements.
Style: IEEE/Nature compatible (vector PDF + raster PNG at 300 DPI).

Figures produced:
  G1  — Party account & post counts (bar)
  G2  — Weekly post volume time series (line, per party)
  G3  — Sentiment heatmap (party x sentiment, normalised)
  G4  — Hate speech rate dot-plot with Wilson 95% CI
  G5  — Cross-party sentiment matrix (heatmap)
  G6  — Interactive network graph (PyVis HTML)
  G7  — Top-20 most active accounts (bar)
  G8  — Per-party word clouds (grid)
  G9  — Party interaction Sankey (Plotly HTML + PNG)
  G_LDA  — LDA topic similarity dendrogram+heatmap
  G_NET  — PageRank x Betweenness scatter (bubble chart)
"""

import os
import sys
import json
import warnings
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.ticker as ticker
import seaborn as sns
import pandas as pd
import numpy as np

warnings.filterwarnings("ignore")

# Global Style (IEEE/Nature compatible)
STYLE: dict = {
    "figure.dpi":          150,
    "figure.facecolor":    "white",
    "axes.facecolor":      "white",
    "axes.spines.top":     False,
    "axes.spines.right":   False,
    "axes.linewidth":      0.8,
    "axes.labelsize":      10,
    "axes.titlesize":      11,
    "axes.titlepad":       8,
    "xtick.labelsize":     9,
    "ytick.labelsize":     9,
    "legend.fontsize":     9,
    "legend.frameon":      False,
    "lines.linewidth":     1.5,
    "font.family":         "sans-serif",
    "font.sans-serif":     ["DejaVu Sans", "Arial", "Helvetica"],
    "savefig.bbox":        "tight",
}
plt.rcParams.update(STYLE)
sns.set_theme(style="white", rc=STYLE)

# Party Palette (consistent across all figures)
PARTY_COLORS: dict[str, str] = {
    "Cumhuriyet Halk Partisi":                "#C0392B",
    "Adalet ve Kalkınma Partisi":             "#E67E22",
    "Milliyetçi Hareket Partisi":             "#D4AC0D",
    "Halkların Eşitlik ve Demokrasi Partisi": "#27AE60",
    "İYİ Parti":                              "#2980B9",
    "Yeni Yol":                               "#8E44AD",
    "Yeniden Refah Partisi":                  "#E74C3C",
    "Bağımsız":                               "#95A5A6",
    "Diğer":                                  "#BDC3C7",
}
DEFAULT_COLOR = "#BDC3C7"

# Keywords for detecting party mentions in post text
PARTY_MENTION_KEYWORDS: dict[str, list[str]] = {
    "CHP":  ["chp", "cumhuriyet halk", "ozgur ozel", "chp'li", "chp'nin", "kilicdaroglu"],
    "AKP":  ["akp", "ak parti", "erdogan", "adalet ve kalkinma", "akp'li"],
    "MHP":  ["mhp", "devlet bahceli", "ulku ocak", "bozkurt", "bahceli"],
    "DEM":  ["dem parti", "hdp", "demokratik halk", "es genel baskan", "demirtas"],
    "IYI":  ["iyi parti", "aksener", "iyi'li"],
}

# Paths
FIGURES_DIR   = "outputs/figures"
SENTIMENT_CSV = "outputs/sentiment_results.csv"
POSTS_JSONL   = "outputs/all_posts_raw.jsonl"
KEYWORDS_JSON = "outputs/political_keywords.json"
EDGES_CSV     = "outputs/network_edges.csv"
STATS_JSON    = "outputs/weekly_distribution_stats.json"
METRICS_JSON  = "outputs/network_metrics.json"
NODE_CSV      = "outputs/network_node_metrics.csv"
SIM_CSV       = "outputs/party_topic_similarity.csv"
STAT_JSON     = "outputs/statistical_test_results.json"


# --- Helpers ------------------------------------------------------------------

def pcolor(party: str) -> str:
    return PARTY_COLORS.get(str(party), DEFAULT_COLOR)


def save_fig(fig: plt.Figure, name: str) -> None:
    """Save PNG (300 DPI) and PDF (vector) to outputs/figures/."""
    for ext in ("png", "pdf"):
        path = os.path.join(FIGURES_DIR, f"{name}.{ext}")
        fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {name}.png / .pdf")


def load_posts_jsonl(path: str) -> list[dict]:
    posts = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    posts.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return posts


# --- G1: Account & Post Count -------------------------------------------------

def g1_party_post_counts() -> None:
    posts = load_posts_jsonl(POSTS_JSONL)
    posts_by_party: dict[str, int]  = defaultdict(int)
    actors_by_party: dict[str, set] = defaultdict(set)
    for rec in posts:
        p = rec.get("party") or "Unknown"
        posts_by_party[p] += 1
        actors_by_party[p].add(rec.get("author_handle", ""))

    parties = sorted(posts_by_party, key=posts_by_party.get, reverse=True)[:8]
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    for ax, vals, title, xlabel in [
        (axes[0], [posts_by_party[p] for p in parties], "Total Posts by Party",    "Post Count"),
        (axes[1], [len(actors_by_party[p]) for p in parties], "Verified Accounts", "Account Count"),
    ]:
        colors = [pcolor(p) for p in parties]
        bars   = ax.barh(parties[::-1], vals[::-1], color=colors[::-1], edgecolor="white")
        for bar, val in zip(bars, vals[::-1]):
            ax.text(bar.get_width() + max(vals) * 0.01,
                    bar.get_y() + bar.get_height() / 2,
                    f"{val:,}", va="center", fontsize=8)
        ax.set_xlabel(xlabel)
        ax.set_title(title, pad=8)
        ax.spines[["top", "right"]].set_visible(False)

    fig.suptitle("BlueSky Turkish Political Account Activity", fontsize=12, y=1.01)
    save_fig(fig, "G1_party_post_counts")


# --- G2: Weekly Post Volume Time Series ----------------------------------------

def g2_weekly_post_volume() -> None:
    posts = load_posts_jsonl(POSTS_JSONL)
    day_party: dict[tuple, int] = defaultdict(int)
    for rec in posts:
        party = rec.get("party") or "Unknown"
        day   = str(rec.get("created_at", ""))[:10]
        if len(day) == 10:
            day_party[(day, party)] += 1

    if not day_party:
        print("  G2: no data.")
        return

    df = pd.DataFrame([{"day": k[0], "party": k[1], "count": v}
                       for k, v in day_party.items()])
    df["day"]  = pd.to_datetime(df["day"])
    top_parties = df.groupby("party")["count"].sum().nlargest(6).index.tolist()
    df_top      = df[df["party"].isin(top_parties)]

    fig, ax = plt.subplots(figsize=(13, 5))
    for party in top_parties:
        sub    = df_top[df_top["party"] == party].sort_values("day")
        smooth = sub.set_index("day")["count"].rolling(3, min_periods=1).mean()
        ax.plot(smooth.index, smooth.values, label=party,
                color=pcolor(party), linewidth=1.8, marker="o", markersize=3)

    ax.set_xlabel("Date")
    ax.set_ylabel("Daily Post Count (3-day rolling avg)")
    ax.set_title("Weekly Post Volume by Party", pad=8)
    ax.legend(loc="upper left", fontsize=8, ncol=2)
    fig.autofmt_xdate()
    save_fig(fig, "G2_weekly_post_volume")


# --- G3: Sentiment Heatmap -----------------------------------------------------

def g3_sentiment_heatmap() -> None:
    df = pd.read_csv(SENTIMENT_CSV, encoding="utf-8-sig")
    df = df[(df["party"].notna()) & (df["party"].str.strip() != "")]
    df = df[df["source"] == "actor_post"]

    pivot = df.groupby(["party", "sentiment"]).size().unstack(fill_value=0)
    for col in ["negative", "neutral", "positive"]:
        if col not in pivot.columns:
            pivot[col] = 0
    pivot["total"] = pivot.sum(axis=1)
    pivot = pivot[pivot["total"] >= 10]
    ratios = pivot[["negative", "neutral", "positive"]].div(pivot["total"], axis=0)
    ratios.columns = ["Negative", "Neutral", "Positive"]
    ratios = ratios.sort_values("Positive", ascending=False)

    fig, ax = plt.subplots(figsize=(7, max(4, len(ratios) * 0.55)))
    sns.heatmap(ratios, annot=True, fmt=".2f", cmap="RdYlGn",
                vmin=0, vmax=1, linewidths=0.5, ax=ax,
                cbar_kws={"shrink": 0.8, "label": "Ratio"})
    ax.set_title("Sentiment Distribution by Party", pad=8)
    ax.set_xticklabels(ax.get_xticklabels(), rotation=0, fontsize=9)
    ax.set_yticklabels(ax.get_yticklabels(), rotation=0, fontsize=8)
    save_fig(fig, "G3_sentiment_heatmap")


# --- G4: Hate Speech Dot-Plot with CI -----------------------------------------

def g4_hate_speech_rate() -> None:
    df = pd.read_csv(SENTIMENT_CSV, encoding="utf-8-sig")
    df = df[df["party"].notna() & (df["party"].str.strip() != "")]

    # Use pre-computed Wilson CIs when available
    ci_data: dict[str, dict] = {}
    if os.path.exists(STAT_JSON):
        with open(STAT_JSON, "r", encoding="utf-8") as f:
            ci_data = json.load(f).get("hate_speech_confidence_intervals", {})

    if not ci_data:
        try:
            from statsmodels.stats.proportion import proportion_confint
            for party, g in df.groupby("party"):
                if len(g) < 10:
                    continue
                n_h = (g["hate_speech"] == "Yes").sum()
                lo, hi = proportion_confint(n_h, len(g), alpha=0.05, method="wilson")
                ci_data[str(party)] = {"hate_rate": n_h / len(g), "n": len(g),
                                       "ci_95_low": float(lo), "ci_95_high": float(hi)}
        except ImportError:
            pass

    if not ci_data:
        print("  G4: no CI data.")
        return

    df_ci = pd.DataFrame(ci_data).T.sort_values("hate_rate", ascending=True)
    fig, ax = plt.subplots(figsize=(9, max(5, len(df_ci) * 0.55)))

    for i, (party, row) in enumerate(df_ci.iterrows()):
        c    = pcolor(str(party))
        rate, lo, hi = row["hate_rate"], row["ci_95_low"], row["ci_95_high"]
        ax.scatter(rate, i, color=c, s=100, zorder=3)
        ax.errorbar(rate, i, xerr=[[rate - lo], [hi - rate]],
                    fmt="none", ecolor=c, capsize=4, linewidth=1.2)
        ax.text(hi + 0.002, i, f"n={int(row['n'])}", va="center", fontsize=7, color="gray")

    ax.set_yticks(range(len(df_ci)))
    ax.set_yticklabels(df_ci.index, fontsize=8)
    ax.xaxis.set_major_formatter(ticker.PercentFormatter(xmax=1))
    ax.set_xlabel("Hate Speech Rate (Wilson 95% CI)")
    ax.set_title("Hate Speech Rate by Party", pad=8)
    save_fig(fig, "G4_hate_speech_rate")


# --- G5: Cross-Party Sentiment Matrix ------------------------------------------

def g5_cross_party_sentiment() -> None:
    df = pd.read_csv(SENTIMENT_CSV, encoding="utf-8-sig")
    df = df[df["party"].notna() & (df["party"].str.strip() != "")]

    def pos_score(s: str) -> float:
        try:
            parts = str(s).split("|")
            return float(parts[2]) if len(parts) == 3 else 0.5
        except Exception:
            return 0.5

    df["pos_prob"] = df["sentiment_scores"].apply(pos_score)

    # Build full-text lookup from JSONL for more accurate mention detection
    full_texts: dict[str, str] = {}
    if os.path.exists(POSTS_JSONL):
        for rec in load_posts_jsonl(POSTS_JSONL):
            uri = rec.get("uri", "")
            if uri:
                full_texts[uri] = rec.get("text", "")

    tracked = list(PARTY_MENTION_KEYWORDS.keys())
    heat: dict[tuple, list] = defaultdict(list)

    for _, row in df.iterrows():
        speaker = str(row["party"])
        text    = full_texts.get(str(row.get("uri", "")),
                                 str(row.get("text_preview", ""))).lower()
        score   = row["pos_prob"]
        for target, keywords in PARTY_MENTION_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                heat[(speaker, target)].append(score)

    all_speakers = sorted(df["party"].dropna().unique())
    matrix = pd.DataFrame(index=all_speakers, columns=tracked, dtype=float)
    for (speaker, target), scores in heat.items():
        if speaker in all_speakers and target in tracked:
            matrix.loc[speaker, target] = round(sum(scores) / len(scores), 3)

    matrix = matrix.dropna(how="all").dropna(axis=1, how="all")
    if matrix.empty:
        print("  G5: insufficient cross-party mention data.")
        return

    fig, ax = plt.subplots(figsize=(9, max(5, len(matrix) * 0.65)))
    sns.heatmap(matrix.astype(float), annot=True, fmt=".2f",
                cmap="RdYlGn", center=0.5, vmin=0, vmax=1,
                linewidths=0.5, ax=ax,
                cbar_kws={"shrink": 0.8, "label": "Mean Positivity"})
    ax.set_title("Cross-Party Sentiment (Speaker -> Target)", pad=8)
    ax.set_xlabel("Mentioned Party")
    ax.set_ylabel("Speaking Party")
    ax.tick_params(axis="x", rotation=30, labelsize=8)
    ax.tick_params(axis="y", rotation=0,  labelsize=8)
    save_fig(fig, "G5_cross_party_sentiment")


# --- G6: Interactive Network (PyVis) -------------------------------------------

def g6_network_graph() -> None:
    try:
        from pyvis.network import Network as PvNet
    except ImportError:
        print("  G6: pyvis not installed — skipping.")
        return

    edges_df = pd.read_csv(EDGES_CSV, encoding="utf-8-sig")
    if edges_df.empty:
        print("  G6: empty edge list.")
        return

    top_edges = edges_df.nlargest(400, "weight")
    in_deg: dict[str, int] = defaultdict(int)
    for _, row in top_edges.iterrows():
        in_deg[row["target_handle"]] += row["weight"]

    net = PvNet(height="750px", width="100%", directed=True,
                bgcolor="#1a1a2e", font_color="white")
    net.barnes_hut(gravity=-6000, spring_length=120)

    added: set[str] = set()
    for _, row in top_edges.iterrows():
        for handle, party in [(row["source_handle"], row["source_party"]),
                               (row["target_handle"], row["target_party"])]:
            if handle not in added:
                size = max(10, min(55, 10 + in_deg.get(handle, 0) * 0.5))
                net.add_node(handle, label=handle, title=f"{handle}\n{party}",
                             size=size, color=pcolor(str(party)))
                added.add(handle)
        net.add_edge(row["source_handle"], row["target_handle"],
                     value=max(1, min(10, row["weight"])),
                     title=f"{row['edge_type']} (x{row['weight']})",
                     color={"color": "#aaaaaa", "opacity": 0.55})

    out = os.path.join(FIGURES_DIR, "G6_network_interactive.html")
    net.write_html(out)
    print(f"  Saved: {out}")


# --- G7: Top-20 Active Accounts ------------------------------------------------

def g7_top_active_accounts() -> None:
    posts  = load_posts_jsonl(POSTS_JSONL)
    counts: dict[str, dict] = defaultdict(lambda: {"count": 0, "party": ""})
    for rec in posts:
        h = rec.get("author_handle", "")
        counts[h]["count"] += 1
        counts[h]["party"] = rec.get("party", "") or ""

    top20  = sorted(counts.items(), key=lambda t: t[1]["count"], reverse=True)[:20]
    labels = [h for h, _ in top20]
    values = [d["count"] for _, d in top20]
    colors = [pcolor(d["party"]) for _, d in top20]

    fig, ax = plt.subplots(figsize=(11, 7))
    bars = ax.barh(labels[::-1], values[::-1], color=colors[::-1], edgecolor="white")
    for bar, val in zip(bars, values[::-1]):
        ax.text(bar.get_width() + max(values) * 0.01,
                bar.get_y() + bar.get_height() / 2,
                f"{val:,}", va="center", fontsize=8)
    ax.set_xlabel("Post Count")
    ax.set_title("Top 20 Most Active Accounts", pad=8)

    legend_handles, seen = [], set()
    for _, d in top20:
        p = d["party"]
        if p and p not in seen:
            seen.add(p)
            legend_handles.append(mpatches.Patch(color=pcolor(p), label=p))
    ax.legend(handles=legend_handles, loc="lower right", fontsize=7)
    save_fig(fig, "G7_top_active_accounts")


# --- G8: Per-Party WordClouds --------------------------------------------------

def g8_wordclouds() -> None:
    try:
        from wordcloud import WordCloud
    except ImportError:
        print("  G8: wordcloud not installed — skipping.")
        return

    with open(KEYWORDS_JSON, "r", encoding="utf-8") as f:
        kw_data = json.load(f)
    by_party = kw_data.get("by_party", {})
    if not by_party:
        return

    parties   = list(by_party.keys())[:6]
    rows_n    = (len(parties) + 1) // 2
    fig, axes = plt.subplots(rows_n, 2, figsize=(14, rows_n * 4))
    axes      = np.array(axes).flatten()

    for i, party in enumerate(parties):
        words = by_party[party]
        if not words:
            axes[i].axis("off")
            continue
        freq = {w: max(1, len(words) - j) for j, w in enumerate(words)}
        c    = pcolor(party).lstrip("#")
        r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)

        def color_func(word=None, font_size=None, position=None,
                       orientation=None, font_path=None, random_state=None,
                       r=r, g=g, b=b):
            import random
            f = random.uniform(0.6, 1.25)
            return f"rgb({min(255,int(r*f))},{min(255,int(g*f))},{min(255,int(b*f))})"

        wc = WordCloud(width=700, height=320, background_color="white",
                       max_words=60, color_func=color_func, prefer_horizontal=0.8)
        wc.generate_from_frequencies(freq)
        axes[i].imshow(wc, interpolation="bilinear")
        axes[i].axis("off")
        axes[i].set_title(party, fontsize=10, fontweight="bold")

    for j in range(len(parties), len(axes)):
        axes[j].axis("off")

    fig.suptitle("Per-Party Keyword WordCloud", fontsize=13, fontweight="bold", y=1.01)
    save_fig(fig, "G8_wordclouds")


# --- G9: Party Interaction Sankey ----------------------------------------------

def g9_party_sankey() -> None:
    try:
        import plotly.graph_objects as go
    except ImportError:
        print("  G9: plotly not installed — skipping.")
        return

    edges_df = pd.read_csv(EDGES_CSV, encoding="utf-8-sig")
    if edges_df.empty:
        return

    flow = (
        edges_df[edges_df["source_party"].notna() & edges_df["target_party"].notna()]
        .groupby(["source_party", "target_party"])["weight"]
        .sum().reset_index()
    )
    flow = flow[flow["weight"] >= 2]
    if flow.empty:
        return

    parties     = sorted(set(flow["source_party"]) | set(flow["target_party"]))
    idx         = {p: i for i, p in enumerate(parties)}
    node_colors = [pcolor(p) for p in parties]

    fig = go.Figure(go.Sankey(
        node=dict(pad=15, thickness=18,
                  line=dict(color="black", width=0.5),
                  label=parties, color=node_colors),
        link=dict(
            source=[idx[r["source_party"]] for _, r in flow.iterrows()],
            target=[idx[r["target_party"]] for _, r in flow.iterrows()],
            value=flow["weight"].tolist(),
        ),
    ))
    fig.update_layout(title_text="Party Interaction Flow (reply + quote)",
                      font_size=11, height=600)
    html_out = os.path.join(FIGURES_DIR, "G9_party_interaction_sankey.html")
    fig.write_html(html_out)
    print(f"  Saved: {html_out}")
    try:
        fig.write_image(os.path.join(FIGURES_DIR, "G9_party_interaction_sankey.png"), scale=2)
    except Exception:
        pass


# --- G_LDA: Topic Similarity Heatmap + Dendrogram ------------------------------

def g_lda_topic_similarity() -> None:
    sim_df = pd.read_csv(SIM_CSV, index_col=0, encoding="utf-8-sig")
    if sim_df.empty:
        return

    try:
        from scipy.cluster.hierarchy import linkage, dendrogram
        from scipy.spatial.distance import squareform
    except ImportError:
        print("  G_LDA: scipy not available — skipping dendrogram.")
        return

    fig, (ax_heat, ax_dend) = plt.subplots(
        1, 2, figsize=(13, 5),
        gridspec_kw={"width_ratios": [3, 1]},
    )
    sns.heatmap(sim_df.astype(float), annot=True, fmt=".3f",
                cmap="YlOrRd", ax=ax_heat, square=True,
                linewidths=0.3, cbar_kws={"label": "Jensen-Shannon Divergence"})
    ax_heat.set_title("Party Discourse Similarity\n(lower JSD = more similar)", fontsize=11)
    ax_heat.set_xticklabels(ax_heat.get_xticklabels(), rotation=40, ha="right", fontsize=8)
    ax_heat.set_yticklabels(ax_heat.get_yticklabels(), rotation=0, fontsize=8)

    try:
        dist = squareform(sim_df.values.astype(float))
        Z    = linkage(dist, method="ward")
        dendrogram(Z, labels=sim_df.index.tolist(),
                   orientation="right", ax=ax_dend, color_threshold=0.3)
        ax_dend.set_title("Hierarchical\nClustering", fontsize=10)
        ax_dend.axis("off")
    except Exception as e:
        print(f"  G_LDA: dendrogram error ({e})")
        ax_dend.axis("off")

    save_fig(fig, "G_LDA_topic_similarity")


# --- G_NET: PageRank x Betweenness Scatter ------------------------------------

def g_network_scatter() -> None:
    df = pd.read_csv(NODE_CSV, encoding="utf-8-sig")
    if df.empty or "pagerank" not in df.columns:
        return

    fig, ax = plt.subplots(figsize=(9, 6))
    for party, grp in df.groupby("party"):
        ax.scatter(
            grp["betweenness"], grp["pagerank"],
            s=grp["in_degree"].clip(upper=500) * 0.4 + 15,
            color=pcolor(str(party)), alpha=0.75,
            label=str(party), edgecolors="white", linewidths=0.3,
        )

    top5 = df.nlargest(5, "pagerank")
    try:
        from adjustText import adjust_text
        texts = [ax.text(row["betweenness"], row["pagerank"], row["handle"], fontsize=7)
                 for _, row in top5.iterrows()]
        adjust_text(texts, arrowprops=dict(arrowstyle="->", color="gray", lw=0.5))
    except ImportError:
        for _, row in top5.iterrows():
            ax.annotate(row["handle"], (row["betweenness"], row["pagerank"]),
                        fontsize=7, xytext=(3, 3), textcoords="offset points")

    ax.set_xlabel("Betweenness Centrality")
    ax.set_ylabel("PageRank (alpha=0.85)")
    ax.set_title("Network Influence Map: PageRank x Betweenness\n"
                 "(bubble size = weighted in-degree)", pad=8)
    ax.legend(loc="upper right", fontsize=7, ncol=2, markerscale=0.7)
    save_fig(fig, "G_network_scatter")


# --- Dispatch Table -----------------------------------------------------------

FIGURE_FUNCS = [
    ("G1",    g1_party_post_counts,     [POSTS_JSONL]),
    ("G2",    g2_weekly_post_volume,    [POSTS_JSONL]),
    ("G3",    g3_sentiment_heatmap,     [SENTIMENT_CSV]),
    ("G4",    g4_hate_speech_rate,      [SENTIMENT_CSV]),
    ("G5",    g5_cross_party_sentiment, [SENTIMENT_CSV]),
    ("G6",    g6_network_graph,         [EDGES_CSV]),
    ("G7",    g7_top_active_accounts,   [POSTS_JSONL]),
    ("G8",    g8_wordclouds,            [KEYWORDS_JSON]),
    ("G9",    g9_party_sankey,          [EDGES_CSV]),
    ("G_LDA", g_lda_topic_similarity,   [SIM_CSV]),
    ("G_NET", g_network_scatter,        [NODE_CSV]),
]


def main():
    os.makedirs(FIGURES_DIR, exist_ok=True)
    for label, func, required in FIGURE_FUNCS:
        missing = [f for f in required if not os.path.exists(f)]
        if missing:
            print(f"[{label}] Skipping — missing files: {missing}")
            continue
        print(f"[{label}] Generating ...")
        try:
            func()
        except Exception as e:
            print(f"  ERROR in {label}: {e}")
    print(f"\nAll figures -> {FIGURES_DIR}/")


if __name__ == "__main__":
    main()
