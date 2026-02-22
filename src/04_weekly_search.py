"""
PHASE 2 — Bluesky-wide Weekly Search + Temporal Trend Analysis
Searches Bluesky for the past 7 days using extracted political keywords.
Appends temporal analysis (rolling volume, autocorrelation, peak detection).

Outputs:
  outputs/weekly_search_results.jsonl
  outputs/weekly_distribution_stats.json
  outputs/temporal_analysis.json
"""

import os
import sys
import json
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()


# ─── Prerequisites ────────────────────────────────────────────────────────────

def require(path: str) -> None:
    if not Path(path).exists():
        print(f"[ERROR] Required file not found: {path}")
        print("Run previous pipeline steps first.")
        sys.exit(1)


# ─── Paths & Config ───────────────────────────────────────────────────────────

KEYWORDS_PATH   = "outputs/political_keywords.json"
ACCOUNTS_PATH   = "outputs/verified_accounts.csv"
RESULTS_PATH    = "outputs/weekly_search_results.jsonl"
STATS_PATH      = "outputs/weekly_distribution_stats.json"
TEMPORAL_PATH   = "outputs/temporal_analysis.json"

AUTH_URL        = "https://bsky.social/xrpc/com.atproto.server.createSession"
SEARCH_URL      = "https://bsky.social/xrpc/app.bsky.feed.searchPosts"
MAX_PER_KEYWORD = 500
TOP_KEYWORDS    = 50
SLEEP_NORMAL    = 0.5
SLEEP_429       = 30


# ─── Authentication ───────────────────────────────────────────────────────────

def get_access_token() -> str:
    """Authenticate with Bluesky and return a JWT access token."""
    identifier = os.getenv("BSKY_IDENTIFIER", "")
    password   = os.getenv("BSKY_PASSWORD", "")
    if not identifier or not password:
        print("[ERROR] BSKY_IDENTIFIER and BSKY_PASSWORD must be set in .env")
        sys.exit(1)
    resp = requests.post(AUTH_URL, json={"identifier": identifier, "password": password}, timeout=15)
    resp.raise_for_status()
    token = resp.json().get("accessJwt", "")
    if not token:
        print("[ERROR] Authentication failed — no accessJwt in response")
        sys.exit(1)
    print(f"  Authenticated as: {resp.json().get('handle', identifier)}")
    return token

# Notable political events for annotation
POLITICAL_EVENTS: dict[str, str] = {
    "2025-03-18": "Ekrem İmamoğlu gözaltına alındı; diploma iptali açıklandı",
    "2025-03-19": "İstanbul Saraçhane'de büyük protesto gösterisi başladı",
    "2025-03-20": "Üniversite öğrencileri kampüslerde yürüyüş; çok sayıda gözaltı",
    "2025-03-21": "İmamoğlu tutukluluğuna itiraz reddedildi",
    "2025-03-22": "CHP Saraçhane mitingi: 100.000+ katılımcı",
    "2025-03-23": "İddianame tamamlandı; terör ve yolsuzluk suçlamaları",
    "2025-03-25": "Marmara Üniversitesi öğrencileri ders boykotu ilan etti",
    "2025-03-26": "Çeşitli illerde polis müdahalesi; 200+ gözaltı",
    "2025-03-31": "31 Mart seçim yıldönümü anma mitingleri",
}

# Extra keywords to append to the weekly search (protest + İmamoğlu wave)
PROTEST_EXTRA_KEYWORDS = [
    "ekrem imamoğlu", "imamoğlu", "saraçhane", "protesto", "diploma",
    "marmara üniversitesi", "istanbul üniversitesi", "kent uzlaşısı",
    "cumhurbaşkanı adayı", "31 mart", "ibb", "polis müdahalesi",
    "tahliye", "yargı bağımsızlığı", "siyasi operasyon",
]


# ─── Search ───────────────────────────────────────────────────────────────────

def search_posts(keyword: str, since: str, until: str, headers: dict) -> list[dict]:
    """Paginate AT Protocol search for one keyword within the time window."""
    all_results: list[dict] = []
    cursor: str | None = None

    while len(all_results) < MAX_PER_KEYWORD:
        params: dict = {"q": keyword, "limit": 100, "since": since, "until": until, "lang": "tr"}
        if cursor:
            params["cursor"] = cursor

        for attempt in range(3):
            try:
                resp = requests.get(SEARCH_URL, params=params, headers=headers, timeout=15)
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
            break

        posts = data.get("posts", [])
        if not posts:
            break
        all_results.extend(posts)
        cursor = data.get("cursor")
        if not cursor:
            break
        time.sleep(SLEEP_NORMAL)

    return all_results[:MAX_PER_KEYWORD]


def extract_search_record(post: dict, keyword: str, handle_to_actor: dict) -> dict:
    """Flatten a search-result post; tag with political actor metadata if known."""
    record = post.get("record", {})
    author = post.get("author", {})
    handle = author.get("handle", "")
    actor  = handle_to_actor.get(handle, {})

    protest_kws = set(PROTEST_EXTRA_KEYWORDS)
    feed_cat = "protest" if keyword in protest_kws else "keyword"

    return {
        "uri":              post.get("uri", ""),
        "text":             record.get("text", ""),
        "author_handle":    handle,
        "author_did":       author.get("did", ""),
        "author_name":      author.get("displayName", ""),
        "created_at":       record.get("createdAt", ""),
        "like_count":       post.get("likeCount", 0),
        "reply_count":      post.get("replyCount", 0),
        "repost_count":     post.get("repostCount", 0),
        "keyword":          keyword,
        "feed_category":    feed_cat,
        "party":            actor.get("party", ""),
        "alliance":         actor.get("alliance", ""),
        "political_stance": actor.get("political_stance", ""),
        "isMilletvekili":   actor.get("isMilletvekili", False),
        "is_tracked_actor": bool(actor),
    }


# ─── Distribution Stats ───────────────────────────────────────────────────────

def compute_stats(records: list[dict]) -> dict:
    """Compute keyword/day/party/author distributions."""
    kw_counts: dict[str, int]     = defaultdict(int)
    day_counts: dict[str, int]    = defaultdict(int)
    party_counts: dict[str, int]  = defaultdict(int)
    handle_counts: dict[str, int] = defaultdict(int)
    hour_counts: dict[str, int]   = defaultdict(int)

    for rec in records:
        kw_counts[rec["keyword"]] += 1
        created = rec.get("created_at", "")
        if len(created) >= 10:
            day_counts[created[:10]] += 1
        if len(created) >= 13:
            hour_counts[created[:13]] += 1   # YYYY-MM-DDTHH
        party = rec.get("party", "Unknown") or "Unknown"
        party_counts[party] += 1
        handle_counts[rec["author_handle"]] += 1

    top_handles = sorted(handle_counts.items(), key=lambda t: t[1], reverse=True)[:20]
    zero_result_kws = [kw for kw in kw_counts if kw_counts[kw] == 0]

    return {
        "total_posts":        len(records),
        "unique_authors":     len(handle_counts),
        "by_keyword":         dict(sorted(kw_counts.items(), key=lambda t: t[1], reverse=True)),
        "by_day":             dict(sorted(day_counts.items())),
        "by_hour":            dict(sorted(hour_counts.items())),
        "by_party":           dict(sorted(party_counts.items(), key=lambda t: t[1], reverse=True)),
        "top_20_handles":     [{"handle": h, "count": c} for h, c in top_handles],
        "zero_result_kws":    zero_result_kws,
    }


# ─── Temporal Analysis ────────────────────────────────────────────────────────

def temporal_analysis(records: list[dict]) -> dict:
    """
    Rolling volume, autocorrelation (Durbin-Watson), peak detection per party.
    Returns a dict that can be serialised to JSON directly.
    """
    try:
        from statsmodels.stats.stattools import durbin_watson
        has_statsmodels = True
    except ImportError:
        has_statsmodels = False

    df = pd.DataFrame(records)
    if df.empty or "created_at" not in df.columns:
        return {}

    df["date"] = pd.to_datetime(df["created_at"], errors="coerce", utc=True).dt.date

    # Daily party × count pivot
    daily = (
        df.groupby(["date", "party"])
        .size()
        .reset_index(name="count")
    )
    daily["date"] = pd.to_datetime(daily["date"])
    pivot = (
        daily.pivot(index="date", columns="party", values="count")
        .fillna(0)
        .sort_index()
    )

    # 3-day rolling average for smoothing
    pivot_smooth = pivot.rolling(3, min_periods=1).mean()

    # Peak detection per party
    peak_days: dict[str, dict] = {}
    for party in pivot.columns:
        if party.strip() in ("", "Unknown"):
            continue
        series = pivot[party]
        if series.max() == 0:
            continue
        peak_date = series.idxmax()
        peak_days[str(party)] = {
            "peak_date":  str(peak_date.date()) if hasattr(peak_date, "date") else str(peak_date),
            "peak_count": int(series.max()),
        }

    # Durbin-Watson autocorrelation test per party
    dw_results: dict[str, float] = {}
    if has_statsmodels:
        for party in pivot.columns:
            series = pivot[party].values
            if len(series) >= 5 and series.std() > 0:
                try:
                    dw_results[str(party)] = round(durbin_watson(series), 4)
                except Exception:
                    pass

    # Named political events (dates that fall within our window)
    window_events = {
        date: label
        for date, label in POLITICAL_EVENTS.items()
        if date in [str(d.date()) for d in pivot.index]
    }

    # Convert smoothed pivot to JSON-serialisable dict
    smooth_dict: dict[str, dict] = {}
    for party in pivot_smooth.columns:
        smooth_dict[str(party)] = {
            str(d.date()): round(float(v), 2)
            for d, v in zip(pivot_smooth.index, pivot_smooth[party])
        }

    return {
        "daily_smooth_by_party": smooth_dict,
        "peak_days":             peak_days,
        "durbin_watson":         dw_results,
        "political_events":      window_events,
    }


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    require(KEYWORDS_PATH)
    require(ACCOUNTS_PATH)
    os.makedirs("outputs", exist_ok=True)

    # Load keywords and actor lookup
    with open(KEYWORDS_PATH, "r", encoding="utf-8") as f:
        kw_data = json.load(f)
    keywords = kw_data["keywords"][:TOP_KEYWORDS]
    # Merge protest extra keywords (deduplicated)
    kw_set = set(keywords)
    for pk in PROTEST_EXTRA_KEYWORDS:
        if pk not in kw_set:
            keywords.append(pk)
            kw_set.add(pk)
    print(f"Using {len(keywords)} keywords for search (incl. {len(PROTEST_EXTRA_KEYWORDS)} protest extras).")

    # Authenticate
    token   = get_access_token()
    headers = {"Authorization": f"Bearer {token}"}

    import pandas as _pd
    accounts_df     = _pd.read_csv(ACCOUNTS_PATH, encoding="utf-8-sig")
    handle_to_actor = {
        str(row["bsky_handle"]).strip(): row.to_dict()
        for _, row in accounts_df.iterrows()
        if _pd.notna(row.get("bsky_handle"))
    }
    print(f"Known actors in lookup: {len(handle_to_actor)}")

    # Time window: last 7 days UTC
    now   = datetime.now(timezone.utc)
    since = (now - timedelta(days=7)).isoformat()
    until = now.isoformat()
    print(f"Search window: {since[:10]} → {until[:10]}")

    # Resume support — load already-fetched records
    seen_uris: set[str]       = set()
    all_records: list[dict]   = []

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
            posts = search_posts(kw, since, until, headers)

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
            print(f"    → {new_count} new (total: {len(all_records)})")
            time.sleep(SLEEP_NORMAL)

    # Distribution stats
    stats = compute_stats(all_records)
    with open(STATS_PATH, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(f"\nSaved stats   → {STATS_PATH}")
    print(f"  Total posts: {stats['total_posts']} | Unique authors: {stats['unique_authors']}")

    # Temporal analysis
    print("\nRunning temporal analysis …")
    temporal = temporal_analysis(all_records)
    with open(TEMPORAL_PATH, "w", encoding="utf-8") as f:
        json.dump(temporal, f, ensure_ascii=False, indent=2)
    print(f"Saved temporal → {TEMPORAL_PATH}")
    if temporal.get("peak_days"):
        print("Peak days per party:")
        for party, info in temporal["peak_days"].items():
            print(f"  {party}: {info['peak_date']} ({info['peak_count']} posts)")

    print(f"\nSaved results → {RESULTS_PATH}")


if __name__ == "__main__":
    main()
