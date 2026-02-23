"""
PHASE 5 —  Visualizations
All figures saved as PNG (300 DPI) only — no PDFs, no HTML.

Figures produced:
  G1        — Party account & post counts (dual bar)
  G2        — Weekly post volume time series (line, per party)
  G3        — Sentiment heatmap (party × sentiment, normalised)
  G4        — Hate speech rate dot-plot with Wilson 95% CI
  G5        — Cross-party sentiment matrix (heatmap)
  G6        — Party-level interaction network (spring layout, PNG)
  G7        — Party posting activity: total posts & avg per account
  G8        — Per-party word clouds (grid)
  G9        — Party interaction chord bar (PNG)
  G_LDA     — LDA topic similarity dendrogram + heatmap
  G_NET     — PageRank × Betweenness scatter (log scale, bubble chart)
  G_TEMPORAL— Bluesky-wide 7-day temporal trend from weekly search
  G_KW_SRC  — Search keyword source distribution (seed / mv / tfidf)
  G_PROTEST — İmamoğlu protest daily trend (volume + rolling average)
"""

import os
import sys
import json
import glob
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
import networkx as nx

warnings.filterwarnings("ignore")

# ─── Global Style ─────────────────────────────────────────────────────────────

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

# ─── Party Palette ────────────────────────────────────────────────────────────

# Only the parties that appear in the data as primary parties.
# Everything else → "Diğer"
MAIN_PARTIES: set[str] = {
    "Cumhuriyet Halk Partisi",
    "Adalet ve Kalkınma Partisi",
    "Milliyetçi Hareket Partisi",
    "Halkların Eşitlik ve Demokrasi Partisi",
    "İYİ Parti",
    "Yeni Yol",
    "Yeniden Refah Partisi",
    "Bağımsız",
}

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

PARTY_SHORT: dict[str, str] = {
    "Cumhuriyet Halk Partisi":                "CHP",
    "Adalet ve Kalkınma Partisi":             "AKP",
    "Milliyetçi Hareket Partisi":             "MHP",
    "Halkların Eşitlik ve Demokrasi Partisi": "DEM",
    "İYİ Parti":                              "İYİ",
    "Yeni Yol":                               "YY",
    "Yeniden Refah Partisi":                  "YRP",
    "Bağımsız":                               "BAĞ",
    "Diğer":                                  "Diğer",
}

DEFAULT_COLOR = "#BDC3C7"

# Keywords used to detect which party a post is mentioning
PARTY_MENTION_KEYWORDS: dict[str, list[str]] = {
    "CHP":  ["chp", "cumhuriyet halk", "ozgur ozel", "chp'li", "kilicdaroglu"],
    "AKP":  ["akp", "ak parti", "erdogan", "adalet ve kalkinma", "akp'li"],
    "MHP":  ["mhp", "devlet bahceli", "ulku ocak", "bozkurt", "bahceli"],
    "DEM":  ["dem parti", "hdp", "demokratik halk", "demirtas"],
    "IYI":  ["iyi parti", "aksener", "iyi'li"],
}

# ─── Paths ────────────────────────────────────────────────────────────────────

FIGURES_DIR    = "outputs/figures"
SENTIMENT_CSV  = "outputs/sentiment_results.csv"
POSTS_JSONL    = "outputs/all_posts_raw.jsonl"
KEYWORDS_JSON  = "outputs/political_keywords.json"
SEARCH_KW_CSV  = "outputs/search_keywords.csv"
EDGES_CSV      = "outputs/network_edges.csv"
STATS_JSON     = "outputs/weekly_distribution_stats.json"
METRICS_JSON   = "outputs/network_metrics.json"
NODE_CSV       = "outputs/network_node_metrics.csv"
SIM_CSV        = "outputs/party_topic_similarity.csv"
STAT_JSON      = "outputs/statistical_test_results.json"
TEMPORAL_JSON  = "outputs/temporal_analysis.json"
PROTEST_TIMELINE_JSON = "outputs/protest_timeline.json"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def pcolor(party: str) -> str:
    return PARTY_COLORS.get(str(party), DEFAULT_COLOR)


def group_party(party) -> str:
    """Map minor / unknown parties → 'Diğer'. Empty → ''."""
    p = str(party).strip()
    if not p or p in ("nan", "None", ""):
        return ""
    return p if p in MAIN_PARTIES else "Diğer"


def save_fig(fig: plt.Figure, name: str) -> None:
    """Save PNG only (300 DPI). No PDFs."""
    path = os.path.join(FIGURES_DIR, f"{name}.png")
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {name}.png")


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


# ─── G1: Party Post & Account Counts ─────────────────────────────────────────

def g1_party_post_counts() -> None:
    posts = load_posts_jsonl(POSTS_JSONL)

    posts_by_party:  dict[str, int] = defaultdict(int)
    actors_by_party: dict[str, set] = defaultdict(set)
    for rec in posts:
        p = group_party(rec.get("party") or "")
        if not p:
            continue
        posts_by_party[p] += 1
        actors_by_party[p].add(rec.get("author_handle", ""))

    # Sort main parties by post count; put "Diğer" last
    parties = sorted(
        [p for p in posts_by_party if p != "Diğer"],
        key=posts_by_party.get, reverse=True,
    )
    if "Diğer" in posts_by_party:
        parties.append("Diğer")

    fig, axes = plt.subplots(1, 2, figsize=(14, max(5, len(parties) * 0.6 + 1)))

    for ax, vals, title, xlabel in [
        (axes[0],
         [posts_by_party[p] for p in parties],
         "Total Posts by Party", "Post Count"),
        (axes[1],
         [len(actors_by_party[p]) for p in parties],
         "Verified Accounts by Party", "Account Count"),
    ]:
        colors = [pcolor(p) for p in parties]
        bars   = ax.barh(parties[::-1], vals[::-1], color=colors[::-1], edgecolor="white")
        for bar, val in zip(bars, vals[::-1]):
            ax.text(
                bar.get_width() + max(vals) * 0.01,
                bar.get_y() + bar.get_height() / 2,
                f"{val:,}", va="center", fontsize=8,
            )
        ax.set_xlabel(xlabel)
        ax.set_title(title, pad=8)
        ax.spines[["top", "right"]].set_visible(False)

    fig.suptitle("BlueSky Turkish Political Account Activity", fontsize=12, y=1.01)
    save_fig(fig, "G1_party_post_counts")


# ─── G2: Weekly Post Volume ────────────────────────────────────────────────────

def g2_weekly_post_volume() -> None:
    posts = load_posts_jsonl(POSTS_JSONL)
    day_party: dict[tuple, int] = defaultdict(int)
    for rec in posts:
        party = group_party(rec.get("party") or "")
        day   = str(rec.get("created_at", ""))[:10]
        if party and len(day) == 10:
            day_party[(day, party)] += 1

    if not day_party:
        print("  G2: no data.")
        return

    df = pd.DataFrame(
        [{"day": k[0], "party": k[1], "count": v} for k, v in day_party.items()]
    )
    df["day"] = pd.to_datetime(df["day"])

    # Top 6 parties by total post count (excluding "Diğer" unless dominant)
    party_totals = df.groupby("party")["count"].sum()
    top_parties  = (
        party_totals[party_totals.index != "Diğer"]
        .nlargest(6).index.tolist()
    )

    fig, ax = plt.subplots(figsize=(13, 5))
    for party in top_parties:
        sub    = df[df["party"] == party].sort_values("day")
        smooth = sub.set_index("day")["count"].rolling(3, min_periods=1).mean()
        ax.plot(
            smooth.index, smooth.values,
            label=party, color=pcolor(party),
            linewidth=1.8, marker="o", markersize=3,
        )
        ax.fill_between(smooth.index, 0, smooth.values, color=pcolor(party), alpha=0.06)

    ax.set_xlabel("Date")
    ax.set_ylabel("Daily Post Count (3-day rolling avg)")
    ax.set_title("Weekly Post Volume by Party", pad=8)
    ax.legend(loc="upper left", fontsize=8, ncol=2)
    fig.autofmt_xdate()
    save_fig(fig, "G2_weekly_post_volume")


# ─── G3: Sentiment Heatmap ────────────────────────────────────────────────────

def g3_sentiment_heatmap() -> None:
    df = pd.read_csv(SENTIMENT_CSV, encoding="utf-8-sig")
    df = df[(df["party"].notna()) & (df["party"].str.strip() != "")]
    df = df[df["source"] == "actor_post"]
    df["party"] = df["party"].apply(group_party)
    df = df[df["party"] != ""]

    pivot = df.groupby(["party", "sentiment"]).size().unstack(fill_value=0)
    for col in ["negative", "neutral", "positive"]:
        if col not in pivot.columns:
            pivot[col] = 0
    pivot["total"] = pivot.sum(axis=1)
    pivot = pivot[pivot["total"] >= 10]
    ratios = pivot[["negative", "neutral", "positive"]].div(pivot["total"], axis=0)
    ratios.columns = ["Negative", "Neutral", "Positive"]
    ratios = ratios.sort_values("Positive", ascending=False)

    fig, ax = plt.subplots(figsize=(7, max(4, len(ratios) * 0.6)))
    sns.heatmap(ratios, annot=True, fmt=".2f", cmap="RdYlGn",
                vmin=0, vmax=1, linewidths=0.5, ax=ax,
                cbar_kws={"shrink": 0.8, "label": "Ratio"})
    ax.set_title("Sentiment Distribution by Party", pad=8)
    ax.set_xticklabels(ax.get_xticklabels(), rotation=0, fontsize=9)
    ax.set_yticklabels(ax.get_yticklabels(), rotation=0, fontsize=8)
    save_fig(fig, "G3_sentiment_heatmap")


# ─── G4: Hate Speech Dot-Plot with CI ─────────────────────────────────────────

def g4_hate_speech_rate() -> None:
    df = pd.read_csv(SENTIMENT_CSV, encoding="utf-8-sig")
    df = df[df["party"].notna() & (df["party"].str.strip() != "")]
    df["party"] = df["party"].apply(group_party)
    df = df[df["party"] != ""]

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
                ci_data[str(party)] = {
                    "hate_rate": n_h / len(g), "n": len(g),
                    "ci_95_low": float(lo), "ci_95_high": float(hi),
                }
        except ImportError:
            pass

    if not ci_data:
        print("  G4: no CI data.")
        return

    df_ci = pd.DataFrame(ci_data).T.sort_values("hate_rate", ascending=True)
    fig, ax = plt.subplots(figsize=(9, max(5, len(df_ci) * 0.6)))

    for i, (party, row) in enumerate(df_ci.iterrows()):
        c    = pcolor(str(party))
        rate = row["hate_rate"]
        lo   = row["ci_95_low"]
        hi   = row["ci_95_high"]
        ax.scatter(rate, i, color=c, s=100, zorder=3)
        ax.errorbar(rate, i, xerr=[[rate - lo], [hi - rate]],
                    fmt="none", ecolor=c, capsize=4, linewidth=1.2)
        ax.text(hi + 0.003, i, f"n={int(row['n'])}", va="center",
                fontsize=7, color="gray")

    ax.set_yticks(range(len(df_ci)))
    ax.set_yticklabels(df_ci.index, fontsize=8)
    ax.xaxis.set_major_formatter(ticker.PercentFormatter(xmax=1))
    ax.set_xlabel("Hate Speech Rate (Wilson 95% CI)")
    ax.set_title("Hate Speech Rate by Party", pad=8)
    save_fig(fig, "G4_hate_speech_rate")


# ─── G5: Cross-Party Sentiment Matrix ─────────────────────────────────────────

def g5_cross_party_sentiment() -> None:
    df = pd.read_csv(SENTIMENT_CSV, encoding="utf-8-sig")
    df = df[df["party"].notna() & (df["party"].str.strip() != "")]
    df["party"] = df["party"].apply(group_party)
    df = df[df["party"] != ""]

    def pos_score(s: str) -> float:
        try:
            parts = str(s).split("|")
            return float(parts[2]) if len(parts) == 3 else 0.5
        except Exception:
            return 0.5

    df["pos_prob"] = df["sentiment_scores"].apply(pos_score)

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
        text    = full_texts.get(
            str(row.get("uri", "")),
            str(row.get("text_preview", "")),
        ).lower()
        score = row["pos_prob"]
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

    fig, ax = plt.subplots(figsize=(9, max(5, len(matrix) * 0.7)))
    sns.heatmap(matrix.astype(float), annot=True, fmt=".2f",
                cmap="RdYlGn", center=0.5, vmin=0, vmax=1,
                linewidths=0.5, ax=ax,
                cbar_kws={"shrink": 0.8, "label": "Mean Positivity"})
    ax.set_title("Cross-Party Sentiment  (Speaker → Target)", pad=8)
    ax.set_xlabel("Mentioned Party")
    ax.set_ylabel("Speaking Party")
    ax.tick_params(axis="x", rotation=30, labelsize=8)
    ax.tick_params(axis="y", rotation=0,  labelsize=8)
    save_fig(fig, "G5_cross_party_sentiment")


# ─── G6: Party-Level Interaction Network (PNG, spring layout) ─────────────────

def g6_party_interaction_network() -> None:
    """
    Party-level interaction network.
    Nodes = parties (size ∝ total outgoing weight).
    Edges = total reply+quote volume between parties.
    Spring layout: heavily interacting parties drawn closer ("spray" effect).
    """
    edges_df = pd.read_csv(EDGES_CSV, encoding="utf-8-sig")
    if edges_df.empty:
        print("  G6: empty edge list.")
        return

    # Group small parties and filter unknowns
    df = edges_df.copy()
    for col in ("source_party", "target_party"):
        df[col] = df[col].fillna("").apply(group_party)
    df = df[(df["source_party"] != "") & (df["target_party"] != "")]

    # Aggregate both directions → symmetric weight (total interactions between pair)
    pair_weights: dict[tuple, int] = defaultdict(int)
    node_total:   dict[str, int]   = defaultdict(int)
    for _, row in df.iterrows():
        src, tgt, w = row["source_party"], row["target_party"], int(row["weight"])
        node_total[src] += w
        node_total[tgt] += w
        if src != tgt:
            key = tuple(sorted([src, tgt]))
            pair_weights[key] += w

    if not pair_weights:
        print("  G6: no cross-party edges found.")
        return

    # Build undirected weighted graph
    G = nx.Graph()
    for (p1, p2), w in pair_weights.items():
        G.add_edge(p1, p2, weight=w)

    nodes = list(G.nodes())
    max_total = max(node_total.values(), default=1)
    max_edge  = max(d["weight"] for _, _, d in G.edges(data=True))

    # Spring layout: weight parameter attracts heavily interacting parties
    pos = nx.spring_layout(G, weight="weight", seed=42, k=1.8, iterations=150)

    fig, ax = plt.subplots(figsize=(12, 10))
    ax.set_aspect("equal")
    ax.axis("off")

    # Draw edges with width and alpha proportional to interaction count
    for u, v, data in G.edges(data=True):
        w     = data["weight"]
        width = 0.8 + (w / max_edge) * 10
        alpha = 0.25 + (w / max_edge) * 0.65
        nx.draw_networkx_edges(
            G, pos, ax=ax, edgelist=[(u, v)],
            width=width, alpha=alpha, edge_color="#888888",
        )
        # Print edge count near midpoint
        if w >= max_edge * 0.15:   # label only prominent edges
            mid_x = (pos[u][0] + pos[v][0]) / 2
            mid_y = (pos[u][1] + pos[v][1]) / 2
            ax.text(mid_x, mid_y, str(w), fontsize=7, ha="center",
                    va="center", color="#555555",
                    bbox=dict(facecolor="white", alpha=0.6, edgecolor="none", pad=1))

    # Draw nodes
    node_sizes  = [max(600, node_total.get(n, 0) / max_total * 5000) for n in nodes]
    node_colors = [pcolor(n) for n in nodes]
    nx.draw_networkx_nodes(
        G, pos, ax=ax, nodelist=nodes,
        node_color=node_colors, node_size=node_sizes,
        alpha=0.92, edgecolors="white", linewidths=2,
    )

    # Party abbreviation labels
    labels = {n: PARTY_SHORT.get(n, n[:4]) for n in nodes}
    nx.draw_networkx_labels(
        G, pos, ax=ax, labels=labels,
        font_size=10, font_weight="bold", font_color="white",
    )

    # Legend
    legend_handles = [
        mpatches.Patch(color=pcolor(p), label=f"{PARTY_SHORT.get(p, p)} — {p}")
        for p in nodes if p in PARTY_COLORS
    ]
    ax.legend(handles=legend_handles, loc="lower left", fontsize=8,
              frameon=True, framealpha=0.85, edgecolor="gray")

    ax.set_title(
        "Party-Level Interaction Network  (reply + quote)\n"
        "Node size = total interactions · Edge width = interaction count · "
        "Proximity = interaction strength",
        fontsize=11, pad=15,
    )
    save_fig(fig, "G6_party_interaction_network")


# ─── G7: Party Posting Activity ───────────────────────────────────────────────

def g7_party_activity() -> None:
    """
    Dual panel:
      Left  — total posts per party
      Right — avg posts per tracked account per party (posting intensity)
    """
    posts = load_posts_jsonl(POSTS_JSONL)

    party_posts:  dict[str, int] = defaultdict(int)
    party_actors: dict[str, set] = defaultdict(set)
    for rec in posts:
        p = group_party(rec.get("party") or "")
        if not p:
            continue
        party_posts[p] += 1
        party_actors[p].add(rec.get("author_handle", ""))

    # Order: main parties by post count, "Diğer" last
    parties = sorted(
        [p for p in party_posts if p != "Diğer"],
        key=party_posts.get, reverse=True,
    )
    if "Diğer" in party_posts:
        parties.append("Diğer")

    total_posts    = [party_posts[p] for p in parties]
    avg_per_actor  = [party_posts[p] / max(1, len(party_actors[p])) for p in parties]
    n_actors       = [len(party_actors[p]) for p in parties]
    colors         = [pcolor(p) for p in parties]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, max(5, len(parties) * 0.65 + 1)))

    # Left: total posts
    bars1 = ax1.barh(parties[::-1], total_posts[::-1], color=colors[::-1], edgecolor="white")
    for bar, val, n in zip(bars1, total_posts[::-1], n_actors[::-1]):
        ax1.text(
            bar.get_width() + max(total_posts) * 0.01,
            bar.get_y() + bar.get_height() / 2,
            f"{val:,}  ({n} accts)", va="center", fontsize=7.5,
        )
    ax1.set_xlabel("Total Post Count")
    ax1.set_title("Total Posts by Party", pad=8)
    ax1.spines[["top", "right"]].set_visible(False)

    # Right: avg posts per account (posting intensity)
    bars2 = ax2.barh(parties[::-1], avg_per_actor[::-1], color=colors[::-1], edgecolor="white")
    for bar, val in zip(bars2, avg_per_actor[::-1]):
        ax2.text(
            bar.get_width() + max(avg_per_actor) * 0.01,
            bar.get_y() + bar.get_height() / 2,
            f"{val:.1f}", va="center", fontsize=8,
        )
    ax2.set_xlabel("Avg Posts per Account")
    ax2.set_title("Posting Intensity by Party", pad=8)
    ax2.spines[["top", "right"]].set_visible(False)

    fig.suptitle("Party Posting Activity — BlueSky Turkish Political Accounts",
                 fontsize=12, y=1.02)
    save_fig(fig, "G7_party_activity")


# ─── G8: Per-Party WordClouds ─────────────────────────────────────────────────

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

    # Show main parties only (skip minor ones)
    parties = [p for p in by_party if p in MAIN_PARTIES][:6]
    if not parties:
        parties = list(by_party.keys())[:6]

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

        wc = WordCloud(
            width=700, height=320, background_color="white",
            max_words=60, color_func=color_func, prefer_horizontal=0.8,
        )
        wc.generate_from_frequencies(freq)
        axes[i].imshow(wc, interpolation="bilinear")
        axes[i].axis("off")
        axes[i].set_title(party, fontsize=10, fontweight="bold")

    for j in range(len(parties), len(axes)):
        axes[j].axis("off")

    fig.suptitle("Per-Party Keyword WordCloud", fontsize=13, fontweight="bold", y=1.01)
    save_fig(fig, "G8_wordclouds")


# ─── G9: Party Interaction — Chord Bar (PNG) ──────────────────────────────────

def g9_party_sankey() -> None:
    """
    Grouped bar chart showing how many times each source party interacted
    with each target party.  PNG only (no HTML).
    Falls back to matplotlib if plotly/kaleido are unavailable.
    """
    edges_df = pd.read_csv(EDGES_CSV, encoding="utf-8-sig")
    if edges_df.empty:
        return

    df = edges_df.copy()
    for col in ("source_party", "target_party"):
        df[col] = df[col].fillna("").apply(group_party)
    df = df[(df["source_party"] != "") & (df["target_party"] != "")
            & (df["source_party"] != df["target_party"])]

    flow = df.groupby(["source_party", "target_party"])["weight"].sum().reset_index()
    flow = flow[flow["weight"] >= 2]
    if flow.empty:
        return

    # Try Plotly PNG via kaleido
    try:
        import plotly.graph_objects as go
        parties     = sorted(set(flow["source_party"]) | set(flow["target_party"]))
        idx         = {p: i for i, p in enumerate(parties)}
        node_colors = [pcolor(p) for p in parties]
        fig_px = go.Figure(go.Sankey(
            node=dict(
                pad=15, thickness=18,
                line=dict(color="black", width=0.5),
                label=parties, color=node_colors,
            ),
            link=dict(
                source=[idx[r["source_party"]] for _, r in flow.iterrows()],
                target=[idx[r["target_party"]] for _, r in flow.iterrows()],
                value=flow["weight"].tolist(),
            ),
        ))
        fig_px.update_layout(
            title_text="Party Interaction Flow  (reply + quote)",
            font_size=11, height=600,
        )
        png_out = os.path.join(FIGURES_DIR, "G9_party_interaction_sankey.png")
        fig_px.write_image(png_out, scale=2)
        print(f"  Saved: G9_party_interaction_sankey.png")
        return
    except Exception:
        pass  # fall through to matplotlib

    # Matplotlib fallback: grouped bar chart of cross-party interaction counts
    pivot = flow.pivot(index="source_party", columns="target_party", values="weight").fillna(0)
    fig, ax = plt.subplots(figsize=(12, max(5, len(pivot) * 0.8)))
    bottom = np.zeros(len(pivot))
    for col in pivot.columns:
        vals   = pivot[col].values
        bars   = ax.bar(pivot.index, vals, bottom=bottom, label=col,
                        color=pcolor(col), edgecolor="white", width=0.65)
        bottom += vals

    ax.set_xlabel("Source Party (sender)")
    ax.set_ylabel("Total Interactions (reply + quote)")
    ax.set_title("Cross-Party Interaction Volume", pad=8)
    ax.legend(title="Target Party", loc="upper right", fontsize=7)
    ax.spines[["top", "right"]].set_visible(False)
    plt.xticks(rotation=35, ha="right", fontsize=8)
    save_fig(fig, "G9_party_interaction_sankey")


# ─── G_LDA: Topic Similarity Heatmap + Dendrogram ─────────────────────────────

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
    sns.heatmap(
        sim_df.astype(float), annot=True, fmt=".3f",
        cmap="YlOrRd", ax=ax_heat, square=True,
        linewidths=0.3, cbar_kws={"label": "Jensen-Shannon Divergence"},
    )
    ax_heat.set_title(
        "Party Discourse Similarity\n(lower JSD = more similar topics)", fontsize=11,
    )
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


# ─── G_NET: PageRank × Betweenness Scatter ────────────────────────────────────

def g_network_scatter() -> None:
    df = pd.read_csv(NODE_CSV, encoding="utf-8-sig")
    if df.empty or "pagerank" not in df.columns:
        print("  G_NET: empty node metrics.")
        return

    df = df[df["betweenness"].notna() & df["pagerank"].notna()].copy()
    if len(df) < 2:
        print("  G_NET: not enough nodes for scatter.")
        return

    # Log-transform betweenness to spread the mass of near-zero values
    df["btwn_log"]  = np.log1p(df["betweenness"] * 1e5)
    df["pr_scaled"] = df["pagerank"] * 1000    # scale up for readability
    df["bubble"]    = np.clip(df["in_degree"], 1, 200) * 1.5 + 20

    fig, ax = plt.subplots(figsize=(11, 8))

    plotted_parties: set[str] = set()
    for party, grp in df.groupby("party"):
        party_label = group_party(str(party))
        plotted_parties.add(party_label)
        ax.scatter(
            grp["btwn_log"], grp["pr_scaled"],
            s=grp["bubble"],
            color=pcolor(party_label),
            alpha=0.72, edgecolors="white", linewidths=0.4,
            zorder=2,
        )

    # Label top 12 accounts by PageRank
    top12 = df.nlargest(12, "pagerank")
    try:
        from adjustText import adjust_text
        texts = [
            ax.text(row["btwn_log"], row["pr_scaled"], row["handle"], fontsize=7)
            for _, row in top12.iterrows()
        ]
        adjust_text(texts, arrowprops=dict(arrowstyle="->", color="gray", lw=0.5))
    except ImportError:
        for _, row in top12.iterrows():
            ax.annotate(
                row["handle"], (row["btwn_log"], row["pr_scaled"]),
                fontsize=7, xytext=(4, 4), textcoords="offset points", color="#333333",
            )

    # Party legend
    legend_handles = [
        mpatches.Patch(color=pcolor(p), label=p)
        for p in PARTY_COLORS if p in plotted_parties
    ]
    ax.legend(handles=legend_handles, loc="upper right", fontsize=7, ncol=2,
              title="Party", title_fontsize=8)

    ax.set_xlabel("Betweenness Centrality  (log₁₀ scale)", fontsize=10)
    ax.set_ylabel("PageRank × 1000", fontsize=10)
    ax.set_title(
        "Network Influence Map: PageRank × Betweenness\n"
        "(bubble size = weighted in-degree; top-12 labeled)",
        pad=8,
    )
    ax.spines[["top", "right"]].set_visible(False)
    save_fig(fig, "G_network_scatter")


# ─── G_TEMPORAL: 7-Day Temporal Trend ────────────────────────────────────────

def g_temporal_trend() -> None:
    """
    Bluesky-wide 7-day posting trend from weekly search results.
    Uses the 3-day rolling averages stored in temporal_analysis.json.
    """
    with open(TEMPORAL_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    smooth = data.get("daily_smooth_by_party", {})
    if not smooth:
        print("  G_TEMPORAL: no smooth data in temporal_analysis.json.")
        return

    # Pick top 6 parties by total smoothed post count
    party_totals = {p: sum(v.values()) for p, v in smooth.items()}
    top_parties  = sorted(party_totals, key=party_totals.get, reverse=True)[:6]

    fig, ax = plt.subplots(figsize=(13, 5))

    for party in top_parties:
        dates  = sorted(smooth[party].keys())
        values = [smooth[party][d] for d in dates]
        xs     = pd.to_datetime(dates)
        label  = PARTY_SHORT.get(group_party(party), party[:8])
        color  = pcolor(group_party(party))
        ax.plot(xs, values, label=label, color=color,
                linewidth=2, marker="o", markersize=4)
        ax.fill_between(xs, 0, values, color=color, alpha=0.07)

    # Annotate named political events if any
    events = data.get("political_events", {})
    for date_str, ev_label in events.items():
        try:
            xv = pd.to_datetime(date_str)
            ax.axvline(xv, color="gray", linestyle="--", linewidth=0.8, alpha=0.7)
            ax.text(xv, ax.get_ylim()[1] * 0.92, ev_label,
                    fontsize=7, rotation=45, ha="right", color="#555555")
        except Exception:
            pass

    ax.set_xlabel("Date")
    ax.set_ylabel("Post Count  (3-day rolling avg)")
    ax.set_title(
        "Bluesky-wide Political Activity — 7-Day Temporal Trend\n"
        "(keyword-matched posts, grouped by author party)",
        pad=8,
    )
    ax.legend(loc="upper left", fontsize=8, ncol=2)
    fig.autofmt_xdate()
    save_fig(fig, "G_TEMPORAL_trend")


# ─── G_KW_SRC: Search Keyword Source Mix ─────────────────────────────────────

def g_keyword_source_mix() -> None:
    """
    Visualise how search keywords were built:
    seed vs milletvekili-derived TF-IDF vs global TF-IDF.
    """
    df = pd.read_csv(SEARCH_KW_CSV, encoding="utf-8-sig")
    if df.empty or "source" not in df.columns:
        print("  G_KW_SRC: no keyword-source data.")
        return

    counts = df["source"].fillna("unknown").value_counts()
    order = [s for s in ("seed", "milletvekili_tfidf", "global_tfidf", "unknown") if s in counts.index]
    if not order:
        return

    color_map = {
        "seed": "#2E86DE",
        "milletvekili_tfidf": "#E67E22",
        "global_tfidf": "#27AE60",
        "unknown": "#7F8C8D",
    }

    vals = [int(counts[s]) for s in order]
    colors = [color_map.get(s, "#95A5A6") for s in order]

    fig, ax = plt.subplots(figsize=(10, 4.6))
    bars = ax.bar(order, vals, color=colors, edgecolor="white", width=0.62)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + max(vals) * 0.02,
                f"{v}", ha="center", va="bottom", fontsize=9)

    ax.set_ylabel("Keyword Count")
    ax.set_xlabel("Keyword Source")
    ax.set_title("Search Keyword Composition", pad=8)
    ax.spines[["top", "right"]].set_visible(False)
    save_fig(fig, "G_keyword_source_mix")


# ─── G_PROTEST: İmamoğlu Protest Timeline ────────────────────────────────────

def g_protest_timeline() -> None:
    with open(PROTEST_TIMELINE_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    daily = data.get("daily_volume", {})
    rolling = data.get("rolling_3day", {})
    if not daily:
        print("  G_PROTEST: no daily protest data.")
        return

    dates = sorted(daily.keys())
    xs = pd.to_datetime(dates)
    daily_vals = [daily[d] for d in dates]
    rolling_vals = [rolling.get(d, daily[d]) for d in dates]

    fig, ax = plt.subplots(figsize=(13, 5))
    ax.bar(xs, daily_vals, color="#FAD7A0", edgecolor="#E67E22", linewidth=0.8, label="Daily volume")
    ax.plot(xs, rolling_vals, color="#D35400", linewidth=2.2, marker="o", markersize=3.8,
            label="3-day rolling avg")

    peak = data.get("peak_date", {})
    peak_date = peak.get("date")
    if peak_date in daily:
        px = pd.to_datetime(peak_date)
        py = daily.get(peak_date, 0)
        ax.scatter([px], [py], color="#C0392B", s=45, zorder=4)
        ax.text(px, py * 1.03, f"Peak: {peak_date}\n{py} posts",
                fontsize=8, color="#C0392B", ha="center", va="bottom")

    for date_str, info in (data.get("event_coverage", {}) or {}).items():
        try:
            ev_x = pd.to_datetime(date_str)
            ax.axvline(ev_x, color="#7F8C8D", linestyle="--", linewidth=0.8, alpha=0.6)
            label = str(info.get("type", "event")).upper()
            ax.text(ev_x, ax.get_ylim()[1] * 0.9, label, fontsize=6.5, rotation=90,
                    color="#555555", ha="right", va="center")
        except Exception:
            pass

    ax.set_xlabel("Date")
    ax.set_ylabel("Post Count")
    ax.set_title("İmamoğlu Protest Trend (Turkish Political Posts)", pad=8)
    ax.legend(loc="upper left", fontsize=8)
    fig.autofmt_xdate()
    save_fig(fig, "G_protest_timeline")


# ─── Dispatch Table ────────────────────────────────────────────────────────────

FIGURE_FUNCS = [
    ("G1",         g1_party_post_counts,          [POSTS_JSONL]),
    ("G2",         g2_weekly_post_volume,          [POSTS_JSONL]),
    ("G3",         g3_sentiment_heatmap,           [SENTIMENT_CSV]),
    ("G4",         g4_hate_speech_rate,            [SENTIMENT_CSV]),
    ("G5",         g5_cross_party_sentiment,       [SENTIMENT_CSV]),
    ("G6",         g6_party_interaction_network,   [EDGES_CSV]),
    ("G7",         g7_party_activity,              [POSTS_JSONL]),
    ("G8",         g8_wordclouds,                  [KEYWORDS_JSON]),
    ("G9",         g9_party_sankey,                [EDGES_CSV]),
    ("G_LDA",      g_lda_topic_similarity,         [SIM_CSV]),
    ("G_NET",      g_network_scatter,              [NODE_CSV]),
    ("G_TEMPORAL", g_temporal_trend,               [TEMPORAL_JSON]),
    ("G_KW_SRC",   g_keyword_source_mix,           [SEARCH_KW_CSV]),
    ("G_PROTEST",  g_protest_timeline,             [PROTEST_TIMELINE_JSON]),
]


def _clean_old_files() -> None:
    """Delete leftover PDFs and HTML files from earlier runs."""
    removed = 0
    for pattern in ("*.pdf", "G6_network_interactive.html",
                    "G9_party_interaction_sankey.html"):
        for path in glob.glob(os.path.join(FIGURES_DIR, pattern)):
            try:
                os.remove(path)
                removed += 1
            except OSError:
                pass
    if removed:
        print(f"  Cleaned up {removed} old PDF/HTML file(s) from {FIGURES_DIR}/")


def main():
    os.makedirs(FIGURES_DIR, exist_ok=True)
    _clean_old_files()

    for label, func, required in FIGURE_FUNCS:
        missing = [f for f in required if not os.path.exists(f)]
        if missing:
            print(f"[{label}] Skipping — missing: {missing}")
            continue
        print(f"[{label}] Generating …")
        try:
            func()
        except Exception as e:
            print(f"  ERROR in {label}: {e}")

    print(f"\nAll figures → {FIGURES_DIR}/")


if __name__ == "__main__":
    main()
