"""
PHASE 4 — Interaction Network Analysis
Builds a directed graph from reply and quote relationships in the post data.
Computes centrality metrics and community structure.
Saves edge list to outputs/network_edges.csv and
metrics to outputs/network_metrics.json.
"""

import os
import json
from collections import defaultdict

import pandas as pd
import networkx as nx

# Paths
POSTS_PATH   = "outputs/all_posts_raw.jsonl"
ACCOUNTS_PATH = "outputs/verified_accounts.csv"
EDGES_PATH   = "outputs/network_edges.csv"
METRICS_PATH = "outputs/network_metrics.json"

# Party colour palette (consistent with 07_visualizations.py)
PARTY_COLORS = {
    "Cumhuriyet Halk Partisi":                "#E63946",
    "Adalet ve Kalkınma Partisi":             "#FFC300",
    "Milliyetçi Hareket Partisi":             "#C9A84C",
    "Halkların Eşitlik ve Demokrasi Partisi": "#2ECC71",
    "İYİ Parti":                              "#3498DB",
    "Yeni Yol":                               "#9B59B6",
    "Bağımsız":                               "#95A5A6",
}
DEFAULT_COLOR = "#CCCCCC"


def load_posts(path: str) -> list[dict]:
    """Read JSONL file and return list of post dicts."""
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
    """
    Extract DID from an AT-URI ('at://did:plc:xxx/…') and map it to a handle.
    Returns None if the DID cannot be found.
    """
    if not uri or not uri.startswith("at://"):
        return None
    parts = uri[5:].split("/", 1)
    did   = parts[0] if parts else ""
    return did_to_handle.get(did)


def build_edges(posts: list[dict], handle_to_party: dict, did_to_handle: dict) -> list[dict]:
    """
    Extract directed edges from reply and quote relationships.
    Each edge = {source_handle, source_party, target_handle, target_party, edge_type}.
    """
    edges: list[dict] = []

    for post in posts:
        source_handle = post.get("author_handle", "")
        source_party  = handle_to_party.get(source_handle, "")

        # ── Reply edges ──────────────────────────────────────
        reply_uri = post.get("reply_to_uri")
        if reply_uri:
            target_handle = uri_to_handle(reply_uri, did_to_handle)
            if target_handle and target_handle != source_handle:
                edges.append({
                    "source_handle": source_handle,
                    "source_party":  source_party,
                    "target_handle": target_handle,
                    "target_party":  handle_to_party.get(target_handle, ""),
                    "edge_type":     "reply",
                })

        # ── Quote edges ───────────────────────────────────────
        quote_uri = post.get("quote_uri")
        if quote_uri:
            target_handle = uri_to_handle(quote_uri, did_to_handle)
            if target_handle and target_handle != source_handle:
                edges.append({
                    "source_handle": source_handle,
                    "source_party":  source_party,
                    "target_handle": target_handle,
                    "target_party":  handle_to_party.get(target_handle, ""),
                    "edge_type":     "quote",
                })

    return edges


def aggregate_edges(edges: list[dict]) -> pd.DataFrame:
    """
    Aggregate duplicate (source, target, type) edges into weighted edges.
    """
    df = pd.DataFrame(edges)
    if df.empty:
        return df

    agg = (
        df.groupby(["source_handle", "source_party", "target_handle", "target_party", "edge_type"])
        .size()
        .reset_index(name="weight")
        .sort_values("weight", ascending=False)
    )
    return agg


def build_networkx_graph(edges_df: pd.DataFrame) -> nx.DiGraph:
    """Build a weighted directed graph from the edge dataframe."""
    G = nx.DiGraph()

    for _, row in edges_df.iterrows():
        src   = row["source_handle"]
        tgt   = row["target_handle"]
        wt    = row["weight"]

        # Node attributes (party colour for visualisation)
        for handle, party in [(src, row["source_party"]), (tgt, row["target_party"])]:
            if handle not in G:
                G.add_node(handle,
                           party=party,
                           color=PARTY_COLORS.get(party, DEFAULT_COLOR))

        # Add or update edge weight
        if G.has_edge(src, tgt):
            G[src][tgt]["weight"] += wt
        else:
            G.add_edge(src, tgt, weight=wt, edge_type=row["edge_type"])

    return G


def compute_metrics(G: nx.DiGraph, handle_to_party: dict) -> dict:
    """
    Compute key network metrics:
      - degree centrality
      - betweenness centrality (on undirected projection)
      - in-degree / out-degree top nodes
      - intra-party vs inter-party interaction ratio
    """
    metrics: dict = {}

    # Degree stats
    in_deg  = dict(G.in_degree(weight="weight"))
    out_deg = dict(G.out_degree(weight="weight"))

    top_in  = sorted(in_deg.items(),  key=lambda t: t[1], reverse=True)[:20]
    top_out = sorted(out_deg.items(), key=lambda t: t[1], reverse=True)[:20]

    metrics["top_20_by_in_degree"]  = [{"handle": h, "in_degree": d}  for h, d in top_in]
    metrics["top_20_by_out_degree"] = [{"handle": h, "out_degree": d} for h, d in top_out]

    # Betweenness centrality (computationally expensive on large graphs — limit to top 500 nodes)
    top_nodes = [n for n, _ in sorted(G.degree(weight="weight"), key=lambda t: t[1], reverse=True)[:500]]
    subG      = G.subgraph(top_nodes).to_undirected()
    bc        = nx.betweenness_centrality(subG, weight="weight", normalized=True)
    top_bc    = sorted(bc.items(), key=lambda t: t[1], reverse=True)[:20]
    metrics["top_20_betweenness"] = [{"handle": h, "betweenness": round(v, 6)} for h, v in top_bc]

    # Intra vs inter-party edge ratio
    intra = 0
    inter = 0
    for src, tgt, data in G.edges(data=True):
        src_party = G.nodes[src].get("party", "")
        tgt_party = G.nodes[tgt].get("party", "")
        w = data.get("weight", 1)
        if src_party and tgt_party and src_party == tgt_party:
            intra += w
        else:
            inter += w
    total = intra + inter
    metrics["intra_party_edges"]       = intra
    metrics["inter_party_edges"]       = inter
    metrics["intra_party_ratio"]       = round(intra / total, 3) if total else 0

    # Community detection (on undirected graph, requires networkx 2.6+)
    G_und      = G.to_undirected()
    communities = list(nx.community.greedy_modularity_communities(G_und, weight="weight"))
    metrics["num_communities"] = len(communities)
    # Label each node with its community index
    community_map: dict[str, int] = {}
    for idx, comm in enumerate(communities):
        for node in comm:
            community_map[node] = idx
    metrics["community_sizes"] = [len(c) for c in communities]

    # Party → community mapping (majority vote per party)
    party_community: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for node, comm_id in community_map.items():
        party = handle_to_party.get(node, "Unknown")
        party_community[party][comm_id] += 1
    metrics["party_main_community"] = {
        party: max(comm_counts, key=comm_counts.get)
        for party, comm_counts in party_community.items()
    }

    metrics["total_nodes"] = G.number_of_nodes()
    metrics["total_edges"] = G.number_of_edges()

    return metrics


def main():
    os.makedirs("outputs", exist_ok=True)

    # Build lookup maps from verified accounts
    accounts_df      = pd.read_csv(ACCOUNTS_PATH, encoding="utf-8-sig")
    handle_to_party  = dict(zip(accounts_df["bsky_handle"].astype(str),
                                accounts_df["party"].astype(str)))
    did_to_handle    = dict(zip(accounts_df["did"].astype(str),
                                accounts_df["bsky_handle"].astype(str)))
    did_to_handle    = {k: v for k, v in did_to_handle.items() if k and k != "nan"}

    # Load posts
    posts = load_posts(POSTS_PATH)
    print(f"Loaded {len(posts)} posts.")

    # Build raw edges
    raw_edges = build_edges(posts, handle_to_party, did_to_handle)
    print(f"Raw edge events: {len(raw_edges)}")

    # Aggregate edges (collapse duplicates → weight)
    edges_df = aggregate_edges(raw_edges)
    edges_df.to_csv(EDGES_PATH, index=False, encoding="utf-8-sig")
    print(f"Aggregated edges: {len(edges_df)}")
    print(f"Saved → {EDGES_PATH}")

    if edges_df.empty:
        print("No edges found — skipping metric computation.")
        return

    # Build graph and compute metrics
    G       = build_networkx_graph(edges_df)
    metrics = compute_metrics(G, handle_to_party)

    with open(METRICS_PATH, "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)

    print(f"Saved → {METRICS_PATH}")
    print(f"Graph: {metrics['total_nodes']} nodes, {metrics['total_edges']} edges")
    print(f"Communities detected: {metrics['num_communities']}")
    print(f"Intra-party ratio: {metrics['intra_party_ratio']:.1%}")


if __name__ == "__main__":
    main()
