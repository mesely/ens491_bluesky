"""
PHASE 2 — Bluesky-wide Weekly Search & Distribution Analysis
Uses the top political keywords to search Bluesky for the past 7 days.
Saves raw results to outputs/weekly_search_results.jsonl and
summary statistics to outputs/weekly_distribution_stats.json.
"""

import os
import json
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests

# Paths
KEYWORDS_PATH   = "outputs/political_keywords.json"
ACCOUNTS_PATH   = "outputs/verified_accounts.csv"
RESULTS_PATH    = "outputs/weekly_search_results.jsonl"
STATS_PATH      = "outputs/weekly_distribution_stats.json"

SEARCH_URL      = "https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts"
MAX_PER_KEYWORD = 500   # cap per keyword to avoid overwhelming storage
TOP_KEYWORDS    = 50    # use only top-50 from the list
SLEEP_NORMAL    = 0.5   # seconds between requests (search is stricter on rate limits)
SLEEP_429       = 30    # seconds on 429


def search_posts(keyword: str, since: str, until: str) -> list[dict]:
    """Paginate search results for one keyword within the time window."""
    all_results = []
    cursor      = None

    while len(all_results) < MAX_PER_KEYWORD:
        params: dict = {
            "q":     keyword,
            "limit": 100,
            "since": since,
            "until": until,
        }
        if cursor:
            params["cursor"] = cursor

        for attempt in range(3):
            try:
                resp = requests.get(SEARCH_URL, params=params, timeout=15)
                if resp.status_code == 429:
                    print(f"  [429] sleeping {SLEEP_429} s …")
                    time.sleep(SLEEP_429)
                    continue
                resp.raise_for_status()
                data = resp.json()
                break
            except requests.RequestException as e:
                print(f"  [error] attempt {attempt + 1}: {e}")
                time.sleep(3)
        else:
            break  # Give up after 3 failures

        posts  = data.get("posts", [])
        if not posts:
            break

        all_results.extend(posts)
        cursor = data.get("cursor")
        if not cursor:
            break

        time.sleep(SLEEP_NORMAL)

    return all_results[:MAX_PER_KEYWORD]


def extract_search_record(post: dict, keyword: str, handle_to_actor: dict) -> dict:
    """
    Flatten a search-result post into a flat record.
    Adds party/alliance info if the author is a known political actor.
    """
    record = post.get("record", {})
    author = post.get("author", {})
    handle = author.get("handle", "")

    actor  = handle_to_actor.get(handle, {})

    return {
        "uri":           post.get("uri", ""),
        "text":          record.get("text", ""),
        "author_handle": handle,
        "author_did":    author.get("did", ""),
        "author_name":   author.get("displayName", ""),
        "created_at":    record.get("createdAt", ""),
        "like_count":    post.get("likeCount", 0),
        "reply_count":   post.get("replyCount", 0),
        "repost_count":  post.get("repostCount", 0),
        "keyword":       keyword,
        # Actor metadata if the author is in our verified list
        "party":         actor.get("party", ""),
        "alliance":      actor.get("alliance", ""),
        "political_stance": actor.get("political_stance", ""),
        "is_tracked_actor": bool(actor),
    }


def compute_stats(records: list[dict]) -> dict:
    """Compute distribution statistics over the collected results."""
    # Keyword → post count
    kw_counts: dict[str, int] = defaultdict(int)
    # Date → post count
    day_counts: dict[str, int] = defaultdict(int)
    # Party → post count
    party_counts: dict[str, int] = defaultdict(int)
    # Handle → post count (top authors)
    handle_counts: dict[str, int] = defaultdict(int)

    for rec in records:
        kw_counts[rec["keyword"]] += 1
        day = rec["created_at"][:10]  # YYYY-MM-DD
        day_counts[day] += 1
        party = rec.get("party", "Unknown") or "Unknown"
        party_counts[party] += 1
        handle_counts[rec["author_handle"]] += 1

    # Top 20 most active authors
    top_handles = sorted(handle_counts.items(), key=lambda t: t[1], reverse=True)[:20]

    return {
        "total_posts":       len(records),
        "unique_authors":    len(handle_counts),
        "by_keyword":        dict(sorted(kw_counts.items(), key=lambda t: t[1], reverse=True)),
        "by_day":            dict(sorted(day_counts.items())),
        "by_party":          dict(sorted(party_counts.items(), key=lambda t: t[1], reverse=True)),
        "top_20_handles":    [{"handle": h, "count": c} for h, c in top_handles],
    }


def main():
    os.makedirs("outputs", exist_ok=True)

    # Load keyword list
    with open(KEYWORDS_PATH, "r", encoding="utf-8") as f:
        kw_data = json.load(f)
    keywords = kw_data["keywords"][:TOP_KEYWORDS]
    print(f"Using {len(keywords)} keywords for search.")

    # Build handle → actor lookup for tagging known politicians
    accounts_df      = pd.read_csv(ACCOUNTS_PATH, encoding="utf-8-sig")
    handle_to_actor  = {
        str(row["bsky_handle"]).strip(): row.to_dict()
        for _, row in accounts_df.iterrows()
        if pd.notna(row.get("bsky_handle"))
    }
    print(f"Known actors in lookup: {len(handle_to_actor)}")

    # Time window: last 7 days in UTC
    now   = datetime.now(timezone.utc)
    since = (now - timedelta(days=7)).isoformat()
    until = now.isoformat()
    print(f"Search window: {since[:10]} → {until[:10]}")

    # Collect results, deduplicate by URI
    seen_uris: set[str] = set()

    # Resume if partial results exist
    all_records: list[dict] = []
    if os.path.exists(RESULTS_PATH):
        with open(RESULTS_PATH, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line.strip())
                    if rec.get("uri") not in seen_uris:
                        seen_uris.add(rec["uri"])
                        all_records.append(rec)
                except json.JSONDecodeError:
                    pass
        print(f"Resuming — {len(all_records)} records already loaded.")

    already_searched: set[str] = {rec["keyword"] for rec in all_records}

    with open(RESULTS_PATH, "a", encoding="utf-8") as out:
        for i, kw in enumerate(keywords, 1):
            if kw in already_searched:
                print(f"  [{i}/{len(keywords)}] '{kw}' — already done, skipping.")
                continue

            print(f"  [{i}/{len(keywords)}] Searching: '{kw}' …")
            posts = search_posts(kw, since, until)

            new_count = 0
            for post in posts:
                rec = extract_search_record(post, kw, handle_to_actor)
                if rec["uri"] in seen_uris:
                    continue
                seen_uris.add(rec["uri"])
                all_records.append(rec)
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                new_count += 1

            out.flush()
            print(f"    → {new_count} new posts (total: {len(all_records)})")
            time.sleep(SLEEP_NORMAL)

    # Compute and save distribution statistics
    stats = compute_stats(all_records)
    with open(STATS_PATH, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    print(f"\nDone. Total posts: {stats['total_posts']} | Unique authors: {stats['unique_authors']}")
    print(f"Saved results → {RESULTS_PATH}")
    print(f"Saved stats   → {STATS_PATH}")


if __name__ == "__main__":
    main()
