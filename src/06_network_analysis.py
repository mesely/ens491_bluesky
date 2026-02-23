"""
PHASE 4 — Interaction Network Analysis (Enhanced)
Builds a directed graph from reply + quote edges.
Computes: PageRank, betweenness, Louvain communities,
          assortativity (echo-chamber test), bridge nodes.

Outputs:
  outputs/network_edges.csv
  outputs/network_node_metrics.csv
  outputs/network_party_flow.csv
  outputs/network_community_summary.csv
  outputs/network_metrics.json      (legacy compact format)
  outputs/network_summary.json      (paper-ready summary)
"""

import os
import sys
import json
from collections import defaultdict, Counter
from pathlib import Path

import numpy as np
import pandas as pd
import networkx as nx


# ─── Prerequisites ────────────────────────────────────────────────────────────

def require(path: str) -> None:
    if not Path(path).exists():
        print(f"[ERROR] Required file not found: {path}")
        print("Run previous pipeline steps first.")
        sys.exit(1)


# ─── Paths & Palette ──────────────────────────────────────────────────────────

POSTS_PATH    = "outputs/all_posts_raw.jsonl"
ACCOUNTS_PATH = "outputs/verified_accounts.csv"
EDGES_PATH    = "outputs/network_edges.csv"
NODE_PATH     = "outputs/network_node_metrics.csv"
PARTY_FLOW_PATH = "outputs/network_party_flow.csv"
COMMUNITY_SUMMARY_PATH = "outputs/network_community_summary.csv"
METRICS_PATH  = "outputs/network_metrics.json"
SUMMARY_PATH  = "outputs/network_summary.json"

PARTY_COLORS = {
    "Cumhuriyet Halk Partisi":                "#C0392B",
    "Adalet ve Kalkınma Partisi":             "#E67E22",
    "Milliyetçi Hareket Partisi":             "#D4AC0D",
    "Halkların Eşitlik ve Demokrasi Partisi": "#27AE60",
    "İYİ Parti":                              "#2980B9",
    "Yeni Yol":                               "#8E44AD",
    "Bağımsız":                               "#95A5A6",
}
DEFAULT_COLOR = "#BDC3C7"


# ─── I/O Helpers ──────────────────────────────────────────────────────────────

def load_posts(path: str) -> list[dict]:
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


def uri_to_handle(uri: str, did_to_handle: dict) -> str | None:
    """Extract DID from an AT-URI and look up the handle."""
    if not uri or not uri.startswith("at://"):
        return None
    did = uri[5:].split("/", 1)[0]
    return did_to_handle.get(did)


# ─── Edge Building ────────────────────────────────────────────────────────────

def build_edges(posts: list[dict],
                handle_to_party: dict,
                did_to_handle: dict) -> list[dict]:
    """Extract directed edges from reply and quote relationships."""
    edges: list[dict] = []
    for post in posts:
        source_handle = post.get("author_handle", "")
        source_party  = handle_to_party.get(source_handle, "")

        for field, edge_type in [("reply_to_uri", "reply"), ("quote_uri", "quote")]:
            target_uri    = post.get(field)
            if not target_uri:
                continue
            target_handle = uri_to_handle(target_uri, did_to_handle)
            if target_handle and target_handle != source_handle:
                edges.append({
                    "source_handle": source_handle,
                    "source_party":  source_party,
                    "target_handle": target_handle,
                    "target_party":  handle_to_party.get(target_handle, ""),
                    "edge_type":     edge_type,
                })
    return edges


def aggregate_edges(edges: list[dict]) -> pd.DataFrame:
    """Collapse duplicate (source, target, type) into weighted edges."""
    df = pd.DataFrame(edges)
    if df.empty:
        return df
    return (
        df.groupby(["source_handle", "source_party",
                    "target_handle", "target_party", "edge_type"])
        .size()
        .reset_index(name="weight")
        .sort_values("weight", ascending=False)
    )


def build_graph(edges_df: pd.DataFrame) -> nx.DiGraph:
    """Build a weighted directed graph from the aggregated edge DataFrame."""
    G = nx.DiGraph()
    for _, row in edges_df.iterrows():
        src, tgt, wt = row["source_handle"], row["target_handle"], row["weight"]
        for handle, party in [(src, row["source_party"]), (tgt, row["target_party"])]:
            if handle not in G:
                G.add_node(handle, party=party,
                           color=PARTY_COLORS.get(party, DEFAULT_COLOR))
        if G.has_edge(src, tgt):
            G[src][tgt]["weight"] += wt
        else:
            G.add_edge(src, tgt, weight=int(wt), edge_type=row["edge_type"])
    return G


# ─── Metrics ──────────────────────────────────────────────────────────────────

def compute_pagerank(G: nx.DiGraph) -> dict[str, float]:
    """PageRank with damping α=0.85, weighted by edge weight."""
    return nx.pagerank(G, alpha=0.85, weight="weight")


def compute_betweenness(G: nx.DiGraph, max_nodes: int = 500) -> dict[str, float]:
    """Betweenness centrality on the top-N subgraph for computational efficiency."""
    top_nodes = [n for n, _ in
                 sorted(G.degree(weight="weight"), key=lambda t: t[1], reverse=True)[:max_nodes]]
    subG = G.subgraph(top_nodes).to_undirected()
    return nx.betweenness_centrality(subG, weight="weight", normalized=True)


def detect_communities_louvain(G: nx.DiGraph) -> tuple[dict, float]:
    """
    Louvain community detection on the undirected projection.
    Falls back to networkx's greedy modularity communities if python-louvain
    is unavailable.

    Returns: (partition dict {node: community_id}, modularity score).
    """
    G_und = G.to_undirected()

    # Try python-louvain (more accurate)
    try:
        import community as community_louvain
        partition  = community_louvain.best_partition(G_und, weight="weight", random_state=42)
        modularity = community_louvain.modularity(partition, G_und)
        print(f"  Louvain: {len(set(partition.values()))} communities, "
              f"modularity={modularity:.4f}")
        return partition, modularity
    except ImportError:
        pass

    # Fallback: networkx greedy modularity
    communities = list(nx.community.greedy_modularity_communities(G_und, weight="weight"))
    partition   = {}
    for comm_id, comm in enumerate(communities):
        for node in comm:
            partition[node] = comm_id
    try:
        modularity = nx.community.modularity(G_und, communities)
    except Exception:
        modularity = 0.0
    print(f"  Greedy modularity: {len(communities)} communities, "
          f"modularity={modularity:.4f}")
    return partition, modularity


def compute_assortativity(G: nx.DiGraph, handle_to_party: dict) -> float:
    """
    Attribute assortativity coefficient for the 'party' attribute.
    > 0 → same-party nodes connect preferentially (echo chamber signal).
    ≈ 0 → random mixing.
    < 0 → cross-party connections dominate.
    """
    try:
        return round(nx.attribute_assortativity_coefficient(G, "party"), 4)
    except Exception:
        return 0.0


def find_bridge_nodes(G: nx.DiGraph, betweenness: dict,
                      percentile: float = 90.0) -> list[str]:
    """
    Nodes with betweenness in the top percentile — likely cross-community bridges.
    """
    if not betweenness:
        return []
    threshold = np.percentile(list(betweenness.values()), percentile)
    return [n for n, bc in betweenness.items() if bc >= threshold]


# ─── Node Metrics DataFrame ───────────────────────────────────────────────────

def build_node_metrics(G: nx.DiGraph,
                       pagerank: dict,
                       betweenness: dict,
                       partition: dict) -> pd.DataFrame:
    """Combine all per-node metrics into one DataFrame."""
    in_deg  = dict(G.in_degree(weight="weight"))
    out_deg = dict(G.out_degree(weight="weight"))
    und = G.to_undirected()
    try:
        core_num = nx.core_number(und)
    except Exception:
        core_num = {n: 0 for n in G.nodes()}
    try:
        largest_cc = max(nx.connected_components(und), key=len)
        sub = und.subgraph(largest_cc)
        eig = nx.eigenvector_centrality_numpy(sub, weight="weight")
    except Exception:
        eig = {}

    rows = []
    for node in G.nodes():
        rows.append({
            "handle":      node,
            "party":       G.nodes[node].get("party", ""),
            "in_degree":   in_deg.get(node, 0),
            "out_degree":  out_deg.get(node, 0),
            "pagerank":    round(pagerank.get(node, 0), 8),
            "betweenness": round(betweenness.get(node, 0), 8),
            "core_number": int(core_num.get(node, 0)),
            "eigenvector": round(float(eig.get(node, 0.0)), 8),
            "community":   partition.get(node, -1),
        })
    return pd.DataFrame(rows).sort_values("pagerank", ascending=False)


# ─── Intra/Inter Party Ratio ─────────────────────────────────────────────────

def party_interaction_ratio(G: nx.DiGraph) -> dict:
    intra, inter = 0, 0
    for src, tgt, data in G.edges(data=True):
        w = data.get("weight", 1)
        if G.nodes[src].get("party") == G.nodes[tgt].get("party"):
            intra += w
        else:
            inter += w
    total = intra + inter
    return {
        "intra": intra, "inter": inter,
        "ratio": round(intra / total, 4) if total else 0,
    }


# ─── Community Party Mapping ─────────────────────────────────────────────────

def community_party_labels(G: nx.DiGraph, partition: dict) -> dict[int, str]:
    """Majority party label per community."""
    party_votes: dict[int, Counter] = defaultdict(Counter)
    for node, comm_id in partition.items():
        party = G.nodes[node].get("party", "Unknown")
        party_votes[comm_id][party] += 1
    return {
        comm_id: votes.most_common(1)[0][0]
        for comm_id, votes in party_votes.items()
    }


def compute_degree_centralization(G: nx.DiGraph) -> float:
    """
    Freeman degree centralization on the undirected projection.
    """
    und = G.to_undirected()
    n = und.number_of_nodes()
    if n <= 2:
        return 0.0
    deg = dict(und.degree())
    max_deg = max(deg.values()) if deg else 0
    num = sum(max_deg - d for d in deg.values())
    den = (n - 1) * (n - 2)
    return round(num / den, 4) if den else 0.0


def build_party_flow_matrix(G: nx.DiGraph) -> pd.DataFrame:
    """
    Weighted source-party -> target-party interaction matrix.
    """
    flow = defaultdict(int)
    for src, tgt, data in G.edges(data=True):
        sp = G.nodes[src].get("party", "") or "Unknown"
        tp = G.nodes[tgt].get("party", "") or "Unknown"
        flow[(sp, tp)] += int(data.get("weight", 1))
    if not flow:
        return pd.DataFrame(columns=["source_party", "target_party", "weight"])
    rows = [
        {"source_party": s, "target_party": t, "weight": w}
        for (s, t), w in flow.items()
    ]
    return pd.DataFrame(rows).sort_values("weight", ascending=False)


def build_community_summary(G: nx.DiGraph, partition: dict) -> pd.DataFrame:
    """
    Community-level size + dominant party summary.
    """
    if not partition:
        return pd.DataFrame(columns=["community", "size", "dominant_party", "party_purity"])
    communities = defaultdict(list)
    for node, cid in partition.items():
        communities[cid].append(node)

    rows = []
    for cid, nodes in communities.items():
        parties = [G.nodes[n].get("party", "Unknown") or "Unknown" for n in nodes]
        counts = Counter(parties)
        dominant_party, dominant_count = counts.most_common(1)[0]
        purity = dominant_count / len(nodes) if nodes else 0.0
        rows.append({
            "community": int(cid),
            "size": len(nodes),
            "dominant_party": dominant_party,
            "party_purity": round(purity, 4),
            "n_parties": len(counts),
        })
    return pd.DataFrame(rows).sort_values(["size", "party_purity"], ascending=[False, False])


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    require(POSTS_PATH)
    require(ACCOUNTS_PATH)
    os.makedirs("outputs", exist_ok=True)

    # Build lookup maps
    accounts_df     = pd.read_csv(ACCOUNTS_PATH, encoding="utf-8-sig")
    handle_to_party = dict(zip(accounts_df["bsky_handle"].astype(str),
                               accounts_df["party"].astype(str)))
    did_to_handle   = {k: v for k, v in
                       zip(accounts_df["did"].astype(str),
                           accounts_df["bsky_handle"].astype(str))
                       if k and k != "nan"}

    posts = load_posts(POSTS_PATH)
    print(f"Loaded {len(posts)} posts.")

    # Edges
    raw_edges = build_edges(posts, handle_to_party, did_to_handle)
    print(f"Raw edge events: {len(raw_edges)}")
    edges_df = aggregate_edges(raw_edges)
    edges_df.to_csv(EDGES_PATH, index=False, encoding="utf-8-sig")
    print(f"Aggregated edges: {len(edges_df)} — saved → {EDGES_PATH}")

    if edges_df.empty:
        print("No edges found — skipping metric computation.")
        return

    # Build graph
    G = build_graph(edges_df)
    print(f"Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

    # Core metrics
    print("Computing PageRank …")
    pagerank = compute_pagerank(G)

    print("Computing betweenness centrality (top-500 subgraph) …")
    betweenness = compute_betweenness(G)

    print("Detecting communities (Louvain / greedy fallback) …")
    partition, modularity = detect_communities_louvain(G)

    print("Computing assortativity …")
    assortativity = compute_assortativity(G, handle_to_party)
    print(f"  Assortativity (party): {assortativity:.4f}  "
          f"({'echo-chamber signal' if assortativity > 0.1 else 'mixed' if assortativity > 0 else 'cross-party mixing'})")

    bridge_nodes  = find_bridge_nodes(G, betweenness)
    party_ratio   = party_interaction_ratio(G)
    comm_labels   = community_party_labels(G, partition)
    centralization = compute_degree_centralization(G)

    # Connectivity structure
    scc_sizes = sorted((len(c) for c in nx.strongly_connected_components(G)), reverse=True)
    wcc_sizes = sorted((len(c) for c in nx.weakly_connected_components(G)), reverse=True)
    scc_top = scc_sizes[:5]
    wcc_top = wcc_sizes[:5]

    # Node metrics CSV
    df_nodes = build_node_metrics(G, pagerank, betweenness, partition)
    df_nodes.to_csv(NODE_PATH, index=False, encoding="utf-8-sig")
    print(f"Saved node metrics → {NODE_PATH}")

    # Party flow matrix CSV
    party_flow_df = build_party_flow_matrix(G)
    party_flow_df.to_csv(PARTY_FLOW_PATH, index=False, encoding="utf-8-sig")
    print(f"Saved party flow   → {PARTY_FLOW_PATH}")

    # Community summary CSV
    community_df = build_community_summary(G, partition)
    community_df.to_csv(COMMUNITY_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    print(f"Saved communities  → {COMMUNITY_SUMMARY_PATH}")

    # Summary JSON (paper-ready)
    summary = {
        "n_nodes":             G.number_of_nodes(),
        "n_edges":             G.number_of_edges(),
        "density":             round(nx.density(G), 6),
        "modularity":          round(modularity, 4),
        "n_communities":       len(set(partition.values())),
        "community_labels":    {str(k): v for k, v in comm_labels.items()},
        "assortativity_party": assortativity,
        "degree_centralization": centralization,
        "avg_clustering":      round(nx.average_clustering(G.to_undirected()), 4),
        "reciprocity":         round(nx.reciprocity(G), 4),
        "largest_scc":         scc_top[0] if scc_top else 0,
        "largest_wcc":         wcc_top[0] if wcc_top else 0,
        "top_5_scc_sizes":     scc_top,
        "top_5_wcc_sizes":     wcc_top,
        "intra_party_edges":   party_ratio["intra"],
        "inter_party_edges":   party_ratio["inter"],
        "intra_party_ratio":   party_ratio["ratio"],
        "bridge_node_count":   len(bridge_nodes),
        "bridge_nodes_top_20": bridge_nodes[:20],
        "top_10_kcore_nodes": [
            {"handle": h, "core_number": int(c)}
            for h, c in (
                df_nodes[["handle", "core_number"]]
                .sort_values("core_number", ascending=False)
                .head(10)
                .itertuples(index=False, name=None)
            )
        ],
        "top_5_pagerank":      [
            {"handle": h, "pagerank": round(pagerank.get(h, 0), 6)}
            for h in df_nodes["handle"].head(5).tolist()
        ],
        "top_5_betweenness":   sorted(
            [{"handle": h, "betweenness": round(v, 6)} for h, v in betweenness.items()],
            key=lambda x: x["betweenness"], reverse=True
        )[:5],
    }
    with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"Saved summary  → {SUMMARY_PATH}")

    # Legacy metrics JSON (used by 07_visualizations.py)
    in_deg  = dict(G.in_degree(weight="weight"))
    out_deg = dict(G.out_degree(weight="weight"))
    legacy  = {
        "total_nodes":         G.number_of_nodes(),
        "total_edges":         G.number_of_edges(),
        "num_communities":     len(set(partition.values())),
        "modularity":          round(modularity, 4),
        "degree_centralization": centralization,
        "intra_party_ratio":   party_ratio["ratio"],
        "top_20_by_in_degree": sorted(
            [{"handle": h, "in_degree": v} for h, v in in_deg.items()],
            key=lambda x: x["in_degree"], reverse=True
        )[:20],
        "top_20_by_out_degree": sorted(
            [{"handle": h, "out_degree": v} for h, v in out_deg.items()],
            key=lambda x: x["out_degree"], reverse=True
        )[:20],
        "top_20_betweenness": sorted(
            [{"handle": h, "betweenness": round(v, 6)} for h, v in betweenness.items()],
            key=lambda x: x["betweenness"], reverse=True
        )[:20],
        "top_20_core_number": [
            {"handle": h, "core_number": int(c)}
            for h, c in (
                df_nodes[["handle", "core_number"]]
                .sort_values("core_number", ascending=False)
                .head(20)
                .itertuples(index=False, name=None)
            )
        ],
    }
    with open(METRICS_PATH, "w", encoding="utf-8") as f:
        json.dump(legacy, f, ensure_ascii=False, indent=2)
    print(f"Saved metrics  → {METRICS_PATH}")

    print(f"\nModularity: {modularity:.4f} | Assortativity: {assortativity:.4f} "
          f"| Intra-party ratio: {party_ratio['ratio']:.1%}")


if __name__ == "__main__":
    main()
