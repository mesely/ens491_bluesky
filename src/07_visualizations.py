"""
PHASE 5 — Visualizations
Produces 9 figures (PNG + interactive HTML where applicable) from all pipeline outputs.
Saves everything to outputs/figures/.

Design principles (from CLAUDE.md):
  - Consistent party colours across all charts
  - Minimal chrome: no unnecessary gridlines or borders
  - Seaborn white theme + despine()
  - DPI=150, figsize=(12,6) or (10,8)
  - Turkish characters via DejaVu Sans
"""

import os
import json
import warnings
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend — safe in all environments
matplotlib.rcParams["font.family"] = "DejaVu Sans"

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns
import pandas as pd
import networkx as nx

warnings.filterwarnings("ignore")
sns.set_theme(style="white")

# Paths
FIGURES_DIR    = "outputs/figures"
SENTIMENT_CSV  = "outputs/sentiment_results.csv"
POSTS_JSONL    = "outputs/all_posts_raw.jsonl"
KEYWORDS_JSON  = "outputs/political_keywords.json"
EDGES_CSV      = "outputs/network_edges.csv"
STATS_JSON     = "outputs/weekly_distribution_stats.json"
METRICS_JSON   = "outputs/network_metrics.json"

# Consistent party colour palette used across all figures
PARTY_COLORS: dict[str, str] = {
    "Cumhuriyet Halk Partisi":                "#E63946",
    "Adalet ve Kalkınma Partisi":             "#FFC300",
    "Milliyetçi Hareket Partisi":             "#C9A84C",
    "Halkların Eşitlik ve Demokrasi Partisi": "#2ECC71",
    "İYİ Parti":                              "#3498DB",
    "Yeni Yol":                               "#9B59B6",
    "Yeniden Refah Partisi":                  "#E67E22",
    "Bağımsız":                               "#95A5A6",
}
DEFAULT_COLOR = "#CCCCCC"

# Party mention keywords for cross-party sentiment (G5)
PARTY_MENTION_KEYWORDS: dict[str, list[str]] = {
    "AKP":  ["akp", "ak parti", "erdoğan", "erdogan", "adalet ve kalkınma"],
    "CHP":  ["chp", "cumhuriyet halk", "özgür özel", "ozgur ozel", "kılıçdaroğlu"],
    "MHP":  ["mhp", "bahçeli", "bahceli", "milliyetçi hareket"],
    "DEM":  ["dem parti", "hdp", "demirtaş", "demirtas", "halkların eşitlik"],
    "İYİ": ["iyi parti", "akşener", "aksener", "meral"],
}


def party_color(party: str) -> str:
    return PARTY_COLORS.get(party, DEFAULT_COLOR)


def save(fig, name: str, tight: bool = True):
    """Save figure as PNG at DPI=150."""
    if tight:
        fig.tight_layout()
    path = os.path.join(FIGURES_DIR, name)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {path}")


# ─── G1: Account & Post Count per Party ─────────────────────────────────────

def g1_party_post_counts():
    """Horizontal bar chart: post and account count per party."""
    import json as _json

    posts_by_party: dict[str, int] = defaultdict(int)
    actors_by_party: dict[str, set] = defaultdict(set)

    with open(POSTS_JSONL, "r", encoding="utf-8") as f:
        for line in f:
            try:
                rec    = _json.loads(line.strip())
                party  = rec.get("party", "Unknown") or "Unknown"
                handle = rec.get("author_handle", "")
                posts_by_party[party]  += 1
                actors_by_party[party].add(handle)
            except Exception:
                pass

    parties   = sorted(posts_by_party, key=posts_by_party.get, reverse=True)[:8]
    post_vals = [posts_by_party[p] for p in parties]
    act_vals  = [len(actors_by_party[p]) for p in parties]
    colors    = [party_color(p) for p in parties]

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # Post counts
    bars = axes[0].barh(parties[::-1], post_vals[::-1], color=colors[::-1])
    axes[0].set_xlabel("Post Sayısı")
    axes[0].set_title("Parti Bazında Toplam Post", fontweight="bold")
    sns.despine(ax=axes[0])

    # Account counts
    axes[1].barh(parties[::-1], act_vals[::-1], color=colors[::-1])
    axes[1].set_xlabel("Hesap Sayısı")
    axes[1].set_title("Parti Bazında Doğrulanmış Hesap", fontweight="bold")
    sns.despine(ax=axes[1])

    save(fig, "G1_party_post_counts.png")


# ─── G2: Weekly Post Volume Time Series ─────────────────────────────────────

def g2_weekly_post_volume():
    """Line chart: daily post volume per party over collected timespan."""
    import json as _json

    day_party: dict[tuple, int] = defaultdict(int)

    with open(POSTS_JSONL, "r", encoding="utf-8") as f:
        for line in f:
            try:
                rec   = _json.loads(line.strip())
                party = rec.get("party", "Unknown") or "Unknown"
                day   = str(rec.get("created_at", ""))[:10]
                if len(day) == 10:
                    day_party[(day, party)] += 1
            except Exception:
                pass

    if not day_party:
        print("  G2: no data, skipping.")
        return

    rows = [{"day": k[0], "party": k[1], "count": v} for k, v in day_party.items()]
    df   = pd.DataFrame(rows)
    df["day"] = pd.to_datetime(df["day"])

    # Keep top 6 parties by total posts
    top_parties = df.groupby("party")["count"].sum().nlargest(6).index.tolist()
    df_top      = df[df["party"].isin(top_parties)]

    fig, ax = plt.subplots(figsize=(14, 6))
    for party in top_parties:
        sub = df_top[df_top["party"] == party].sort_values("day")
        ax.plot(sub["day"], sub["count"], label=party,
                color=party_color(party), linewidth=2, marker="o", markersize=3)

    ax.set_xlabel("Tarih")
    ax.set_ylabel("Günlük Post Sayısı")
    ax.set_title("Haftalık Post Hacmi — Parti Bazında", fontweight="bold")
    ax.legend(loc="upper left", fontsize=8, frameon=False)
    sns.despine(ax=ax)
    fig.autofmt_xdate()

    save(fig, "G2_weekly_post_volume.png")


# ─── G3: Sentiment Distribution per Party ───────────────────────────────────

def g3_sentiment_distribution():
    """Stacked horizontal bar chart: sentiment ratios per party."""
    df = pd.read_csv(SENTIMENT_CSV, encoding="utf-8-sig")
    df = df[df["party"].notna() & (df["party"] != "")]
    df = df[df["source"] == "actor_post"]  # actor posts only for cleaner signal

    pivot = (
        df.groupby(["party", "sentiment"])
        .size()
        .unstack(fill_value=0)
    )
    # Ensure all three sentiment columns exist
    for col in ["positive", "neutral", "negative"]:
        if col not in pivot.columns:
            pivot[col] = 0

    pivot["total"] = pivot.sum(axis=1)
    # Filter parties with at least 10 posts
    pivot = pivot[pivot["total"] >= 10]
    ratios = pivot[["positive", "neutral", "negative"]].div(pivot["total"], axis=0)
    ratios = ratios.sort_values("positive", ascending=True)

    fig, ax = plt.subplots(figsize=(12, max(6, len(ratios) * 0.5)))
    lefts   = [0] * len(ratios)

    for sentiment, color in [("positive", "#27AE60"), ("neutral", "#BDC3C7"), ("negative", "#E74C3C")]:
        vals = ratios[sentiment].values
        bars = ax.barh(ratios.index, vals, left=lefts,
                       color=color, label=sentiment.capitalize())
        # Label inside each segment if wide enough
        for bar, left, val in zip(bars, lefts, vals):
            if val > 0.05:
                ax.text(left + val / 2, bar.get_y() + bar.get_height() / 2,
                        f"{val:.0%}", ha="center", va="center",
                        fontsize=7, color="white", fontweight="bold")
        lefts = [l + v for l, v in zip(lefts, vals)]

    ax.set_xlim(0, 1)
    ax.set_xlabel("Oran")
    ax.set_title("Parti Bazında Sentiment Dağılımı", fontweight="bold")
    ax.legend(loc="lower right", frameon=False)
    sns.despine(ax=ax)

    save(fig, "G3_sentiment_distribution.png")


# ─── G4: Hate Speech Rate per Party ─────────────────────────────────────────

def g4_hate_speech_rate():
    """Dot plot: hate speech rate per party."""
    df = pd.read_csv(SENTIMENT_CSV, encoding="utf-8-sig")
    df = df[df["party"].notna() & (df["party"] != "")]

    hs       = df.assign(hs_yes=(df["hate_speech"] == "Yes").astype(int))
    by_party = (
        hs.groupby("party")["hs_yes"]
        .agg(["mean", "std", "count"])
        .rename(columns={"mean": "rate", "std": "err", "count": "n"})
    )
    by_party = by_party[by_party["n"] >= 10].sort_values("rate", ascending=True)

    fig, ax = plt.subplots(figsize=(10, max(6, len(by_party) * 0.55)))

    for i, (party, row) in enumerate(by_party.iterrows()):
        color = party_color(party)
        ax.scatter(row["rate"], i, color=color, s=120, zorder=3)
        # Error bar (±1 std / sqrt(n))
        se = row["err"] / (row["n"] ** 0.5) if row["n"] > 1 else 0
        ax.errorbar(row["rate"], i, xerr=se, fmt="none", ecolor=color, capsize=4)

    ax.set_yticks(range(len(by_party)))
    ax.set_yticklabels(by_party.index)
    ax.set_xlabel("Nefret Söylemi Oranı")
    ax.set_title("Parti Bazında Nefret Söylemi Oranı (±SE)", fontweight="bold")
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0%}"))
    sns.despine(ax=ax)

    save(fig, "G4_hate_speech_rate.png")


# ─── G5: Cross-party Sentiment Heatmap ──────────────────────────────────────

def g5_cross_party_sentiment():
    """Heatmap: average positivity score of speaker-party about target-party."""
    df = pd.read_csv(SENTIMENT_CSV, encoding="utf-8-sig")
    df = df[df["party"].notna() & (df["party"] != "")]

    # Parse positive probability from sentiment_scores string
    def pos_score(scores_str: str) -> float:
        try:
            parts = str(scores_str).split("|")
            # Scores order: negative|neutral|positive
            return float(parts[2]) if len(parts) == 3 else 0.5
        except Exception:
            return 0.5

    df["pos_prob"] = df["sentiment_scores"].apply(pos_score)

    # Detect which party a post mentions
    tracked_parties = list(PARTY_MENTION_KEYWORDS.keys())
    heat: dict[tuple, list] = defaultdict(list)

    for _, row in df.iterrows():
        speaker_party = row["party"]
        text          = str(row.get("text_preview", "")).lower()
        score         = row["pos_prob"]

        for target_abbr, keywords in PARTY_MENTION_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                heat[(speaker_party, target_abbr)].append(score)

    # Build matrix
    all_speakers = sorted(df["party"].dropna().unique())
    matrix       = pd.DataFrame(index=all_speakers, columns=tracked_parties, dtype=float)

    for (speaker, target), scores in heat.items():
        if speaker in all_speakers and target in tracked_parties:
            matrix.loc[speaker, target] = sum(scores) / len(scores)

    matrix = matrix.dropna(how="all").dropna(axis=1, how="all")

    if matrix.empty:
        print("  G5: not enough cross-party mention data, skipping.")
        return

    fig, ax = plt.subplots(figsize=(10, max(6, len(matrix) * 0.7)))
    sns.heatmap(
        matrix.astype(float),
        annot=True, fmt=".2f", linewidths=0.5,
        cmap="RdYlGn", center=0.5, vmin=0.0, vmax=1.0,
        ax=ax, cbar_kws={"label": "Ortalama Pozitiflik Skoru"},
    )
    ax.set_title("Partiler Arası Sentiment (Konuşan → Bahsedilen)", fontweight="bold")
    ax.set_xlabel("Bahsedilen Parti")
    ax.set_ylabel("Konuşan Parti")
    ax.tick_params(axis="x", rotation=30)
    ax.tick_params(axis="y", rotation=0)

    save(fig, "G5_cross_party_sentiment.png")


# ─── G6: Interactive Network Graph (PyVis) ───────────────────────────────────

def g6_network_graph():
    """Interactive HTML network graph using PyVis."""
    try:
        from pyvis.network import Network as PvNetwork
    except ImportError:
        print("  G6: pyvis not installed — skipping interactive graph.")
        return

    edges_df = pd.read_csv(EDGES_CSV, encoding="utf-8-sig")
    if edges_df.empty:
        print("  G6: empty edge list, skipping.")
        return

    # Keep only top edges by weight for readability
    edges_df = edges_df.nlargest(300, "weight")

    net = PvNetwork(height="750px", width="100%", directed=True,
                    bgcolor="#1a1a2e", font_color="white")
    net.barnes_hut(gravity=-6000, spring_length=120)

    # Track node in-degree for sizing
    in_deg: dict[str, int] = defaultdict(int)
    for _, row in edges_df.iterrows():
        in_deg[row["target_handle"]] += row["weight"]

    added_nodes: set[str] = set()
    for _, row in edges_df.iterrows():
        for handle, party in [(row["source_handle"], row["source_party"]),
                               (row["target_handle"], row["target_party"])]:
            if handle not in added_nodes:
                size  = max(10, min(50, 10 + in_deg.get(handle, 0) * 0.5))
                color = party_color(party)
                net.add_node(handle, label=handle, title=f"{handle}\n{party}",
                             size=size, color=color)
                added_nodes.add(handle)

        edge_width = max(1, min(10, row["weight"]))
        net.add_edge(row["source_handle"], row["target_handle"],
                     value=edge_width,
                     title=f"{row['edge_type']} (×{row['weight']})",
                     color={"color": "#aaaaaa", "opacity": 0.6})

    out_path = os.path.join(FIGURES_DIR, "G6_network_interactive.html")
    net.write_html(out_path)
    print(f"  Saved: {out_path}")


# ─── G7: Top 20 Most Active Accounts ─────────────────────────────────────────

def g7_top_active_accounts():
    """Horizontal bar chart: top 20 accounts by post count, coloured by party."""
    import json as _json

    counts: dict[str, dict] = defaultdict(lambda: {"count": 0, "party": ""})

    with open(POSTS_JSONL, "r", encoding="utf-8") as f:
        for line in f:
            try:
                rec    = _json.loads(line.strip())
                handle = rec.get("author_handle", "")
                party  = rec.get("party", "") or ""
                counts[handle]["count"] += 1
                counts[handle]["party"]  = party
            except Exception:
                pass

    top20 = sorted(counts.items(), key=lambda t: t[1]["count"], reverse=True)[:20]
    labels = [h for h, _ in top20]
    values = [d["count"] for _, d in top20]
    colors = [party_color(d["party"]) for _, d in top20]

    fig, ax = plt.subplots(figsize=(12, 8))
    ax.barh(labels[::-1], values[::-1], color=colors[::-1])
    ax.set_xlabel("Post Sayısı")
    ax.set_title("En Aktif 20 Hesap", fontweight="bold")

    # Party legend
    seen_parties: set[str] = set()
    handles_legend = []
    for _, d in top20:
        p = d["party"]
        if p and p not in seen_parties:
            seen_parties.add(p)
            handles_legend.append(mpatches.Patch(color=party_color(p), label=p))
    ax.legend(handles=handles_legend, loc="lower right", fontsize=7, frameon=False)
    sns.despine(ax=ax)

    save(fig, "G7_top_active_accounts.png")


# ─── G8: Per-Party WordClouds ─────────────────────────────────────────────────

def g8_wordclouds():
    """2×3 grid of party word clouds from political_keywords.json."""
    try:
        from wordcloud import WordCloud
    except ImportError:
        print("  G8: wordcloud not installed — skipping.")
        return

    with open(KEYWORDS_JSON, "r", encoding="utf-8") as f:
        kw_data = json.load(f)

    by_party  = kw_data.get("by_party", {})
    if not by_party:
        print("  G8: no per-party keyword data.")
        return

    parties = list(by_party.keys())[:6]
    rows    = (len(parties) + 1) // 2

    fig, axes = plt.subplots(rows, 2, figsize=(14, rows * 4))
    axes      = axes.flatten()

    for i, party in enumerate(parties):
        words = by_party[party]
        if not words:
            axes[i].axis("off")
            continue
        # Build frequency dict: give higher rank to earlier-listed keywords
        freq = {w: max(1, len(words) - j) for j, w in enumerate(words)}
        color = party_color(party).lstrip("#")
        r     = int(color[0:2], 16)
        g     = int(color[2:4], 16)
        b     = int(color[4:6], 16)

        def make_color_func(r=r, g=g, b=b):
            def color_func(*args, **kwargs):
                # Vary brightness slightly for visual depth
                import random
                factor = random.uniform(0.6, 1.2)
                return f"rgb({min(255,int(r*factor))},{min(255,int(g*factor))},{min(255,int(b*factor))})"
            return color_func

        wc = WordCloud(
            width=600, height=300,
            background_color="white",
            max_words=60,
            color_func=make_color_func(),
            prefer_horizontal=0.8,
            font_path=None,
        ).generate_from_frequencies(freq)

        axes[i].imshow(wc, interpolation="bilinear")
        axes[i].axis("off")
        axes[i].set_title(party, fontsize=10, fontweight="bold")

    # Hide any unused subplots
    for j in range(len(parties), len(axes)):
        axes[j].axis("off")

    fig.suptitle("Parti Bazında Anahtar Kelime WordCloud", fontsize=14, fontweight="bold", y=1.01)
    save(fig, "G8_wordclouds.png")


# ─── G9: Party Interaction Sankey ─────────────────────────────────────────────

def g9_party_interaction_sankey():
    """Sankey diagram: party→party interaction flows using Plotly."""
    try:
        import plotly.graph_objects as go
    except ImportError:
        print("  G9: plotly not installed — skipping Sankey.")
        return

    edges_df = pd.read_csv(EDGES_CSV, encoding="utf-8-sig")
    if edges_df.empty:
        print("  G9: empty edge list, skipping.")
        return

    flow = (
        edges_df[edges_df["source_party"].notna() & edges_df["target_party"].notna()]
        .groupby(["source_party", "target_party"])["weight"]
        .sum()
        .reset_index()
    )
    flow = flow[flow["weight"] >= 2]  # Remove negligible flows

    # Encode party names to integer indices for Sankey
    all_parties = sorted(set(flow["source_party"]) | set(flow["target_party"]))
    idx         = {p: i for i, p in enumerate(all_parties)}
    node_colors = [party_color(p) for p in all_parties]

    fig = go.Figure(go.Sankey(
        node=dict(
            pad=15, thickness=20,
            line=dict(color="black", width=0.5),
            label=all_parties,
            color=node_colors,
        ),
        link=dict(
            source=[idx[r["source_party"]] for _, r in flow.iterrows()],
            target=[idx[r["target_party"]] for _, r in flow.iterrows()],
            value=flow["weight"].tolist(),
        ),
    ))
    fig.update_layout(
        title_text="Partiler Arası Etkileşim Akışı (reply + quote)",
        font_size=12,
        height=600,
    )

    out_path = os.path.join(FIGURES_DIR, "G9_party_interaction_sankey.html")
    fig.write_html(out_path)
    print(f"  Saved: {out_path}")

    # Static PNG fallback (requires kaleido)
    try:
        png_path = os.path.join(FIGURES_DIR, "G9_party_interaction_sankey.png")
        fig.write_image(png_path, scale=2)
        print(f"  Saved: {png_path}")
    except Exception:
        pass


# ─── Main ─────────────────────────────────────────────────────────────────────

FIGURE_FUNCS = [
    ("G1", g1_party_post_counts,       [POSTS_JSONL]),
    ("G2", g2_weekly_post_volume,      [POSTS_JSONL]),
    ("G3", g3_sentiment_distribution,  [SENTIMENT_CSV]),
    ("G4", g4_hate_speech_rate,        [SENTIMENT_CSV]),
    ("G5", g5_cross_party_sentiment,   [SENTIMENT_CSV]),
    ("G6", g6_network_graph,           [EDGES_CSV]),
    ("G7", g7_top_active_accounts,     [POSTS_JSONL]),
    ("G8", g8_wordclouds,             [KEYWORDS_JSON]),
    ("G9", g9_party_interaction_sankey,[EDGES_CSV]),
]


def main():
    os.makedirs(FIGURES_DIR, exist_ok=True)

    for label, func, required_files in FIGURE_FUNCS:
        missing = [f for f in required_files if not os.path.exists(f)]
        if missing:
            print(f"[{label}] Skipping — missing files: {missing}")
            continue
        print(f"[{label}] Generating …")
        try:
            func()
        except Exception as e:
            print(f"  ERROR in {label}: {e}")

    print(f"\nAll figures saved to {FIGURES_DIR}/")


if __name__ == "__main__":
    main()
