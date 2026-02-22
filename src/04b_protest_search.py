"""
PHASE 2b — Ekrem İmamoğlu Protest Search & Timeline Analysis

Research Question:
  Ekrem İmamoğlu protestoları sürecinde, sosyal medyada üretilen hedef odaklı
  toksisite ve duygu kutuplaşması, fiziksel dünyadaki güvenlik olaylarıyla
  (gözaltı, tutuklama ve polis müdahalesi sayıları) zamansal ve nedensel
  olarak nasıl bir etkileşim içindedir?

Date range: 2025-03-18 (arrest of İmamoğlu) through end of protest wave.
Outputs:
  outputs/protest_posts.jsonl        — raw posts
  outputs/protest_timeline.json      — daily volume + event annotations
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


# ─── Prerequisites ─────────────────────────────────────────────────────────────

def require(path: str) -> None:
    if not Path(path).exists():
        print(f"[ERROR] Required file not found: {path}")
        print("Run previous pipeline steps first.")
        sys.exit(1)


# ─── Paths & Config ────────────────────────────────────────────────────────────

ACCOUNTS_PATH  = "outputs/verified_accounts.csv"
RESULTS_PATH   = "outputs/protest_posts.jsonl"
TIMELINE_PATH  = "outputs/protest_timeline.json"

AUTH_URL       = "https://bsky.social/xrpc/com.atproto.server.createSession"
SEARCH_URL     = "https://bsky.social/xrpc/app.bsky.feed.searchPosts"
MAX_PER_KEYWORD = 500
SLEEP_NORMAL   = 0.5
SLEEP_429      = 30

# Protest window: İmamoğlu gözaltı → tutuklu süreci
PROTEST_SINCE  = "2025-03-18T00:00:00Z"
# No hard until — fetch up to now
PROTEST_UNTIL  = None   # will be set to datetime.now() in main()

# ─── Protest Keywords ─────────────────────────────────────────────────────────
# Grouped for reference; all used in search.

PROTEST_KEYWORDS = [
    # Ana figür
    "ekrem imamoğlu",
    "imamoğlu",
    "imamoglu",

    # Suçlama / hukuki süreç
    "diploma",
    "diploma iptali",
    "marmara üniversitesi diploma",
    "siyasi operasyon",
    "tutuklama",
    "gözaltı",
    "tahliye",
    "iddianame",
    "savcı",
    "terör suçlaması",
    "yargı bağımsızlığı",
    "hukuk dışı",
    "siyasi yargı",

    # Protesto / eylem mekânları
    "saraçhane",
    "protesto",
    "yürüyüş",
    "eylem",
    "miting",
    "istanbul üniversitesi protesto",
    "marmara üniversitesi protesto",
    "boğaziçi protesto",
    "odtü protesto",
    "galatasaray lisesi",

    # Sosyal hareketler
    "kent uzlaşısı",
    "cumhurbaşkanı adayı",
    "31 mart",
    "seçim iptali",
    "ibb",
    "istanbul büyükşehir belediyesi",
    "belediye başkanı tutuklandı",

    # Güvenlik / polis
    "polis müdahalesi",
    "biber gazı",
    "tazyikli su",
    "plastik mermi",
    "gözaltı sayısı",
    "öğrenci gözaltı",

    # CHP / siyasi bağlam
    "chp",
    "cumhuriyet halk partisi imamoğlu",
    "özgür özel imamoğlu",

    # Uluslararası tepkiler
    "ab türkiye demokrasi",
    "avrupa konseyi türkiye",
    "venedik komisyonu",
]

# ─── Physical World Events (for temporal correlation) ─────────────────────────
# Format: "YYYY-MM-DD": {"event": "...", "type": "arrest|protest|police|legal|political"}

PHYSICAL_EVENTS: dict[str, dict] = {
    "2025-03-18": {
        "event": "Ekrem İmamoğlu gözaltına alındı; diploma iptali kararı açıklandı",
        "type": "arrest",
    },
    "2025-03-19": {
        "event": "İstanbul'da ilk büyük protesto gösterileri; Saraçhane'de binlerce kişi",
        "type": "protest",
    },
    "2025-03-20": {
        "event": "Üniversite öğrencileri kampüslerde yürüyüş başlattı; çok sayıda gözaltı",
        "type": "police",
    },
    "2025-03-21": {
        "event": "İmamoğlu tutukluluğuna itiraz reddedildi; davası Ağır Ceza'ya sevk",
        "type": "legal",
    },
    "2025-03-22": {
        "event": "CHP Saraçhane mitingi: 100.000+ katılımcı; İzmir, Ankara, Bursa'da destek eylemleri",
        "type": "protest",
    },
    "2025-03-23": {
        "event": "İddianame tamamlandı; terör ve yolsuzluk suçlamaları eklendi",
        "type": "legal",
    },
    "2025-03-24": {
        "event": "Avrupa Konseyi Türkiye'deki gelişmeleri kınadı; AB büyükelçileri CHP'yi ziyaret etti",
        "type": "political",
    },
    "2025-03-25": {
        "event": "Marmara Üniversitesi öğrencileri ders boykotu ilan etti",
        "type": "protest",
    },
    "2025-03-26": {
        "event": "Çeşitli illerde polis biber gazı ve tazyikli su kullandı; 200+ gözaltı",
        "type": "police",
    },
    "2025-03-28": {
        "event": "İmamoğlu: 'Teslim olmayacağım' — avukatları basın açıklaması yaptı",
        "type": "legal",
    },
    "2025-03-31": {
        "event": "31 Mart seçim yıldönümü anma mitingleri; gösterilerde gerginlik",
        "type": "protest",
    },
    "2025-04-04": {
        "event": "CHP grup toplantısı; partinin genel strateji açıklaması",
        "type": "political",
    },
}


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


# ─── Search ────────────────────────────────────────────────────────────────────

def search_posts(keyword: str, since: str, until: str, headers: dict = {}) -> list[dict]:
    """Paginate AT Protocol search for one keyword within the protest window."""
    all_results: list[dict] = []
    cursor: str | None = None

    while len(all_results) < MAX_PER_KEYWORD:
        params: dict = {"q": keyword, "limit": 100, "since": since, "until": until}
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


def extract_protest_record(post: dict, keyword: str, handle_to_actor: dict) -> dict:
    """Flatten a protest search-result post; tag with actor metadata if known."""
    record = post.get("record", {})
    author = post.get("author", {})
    handle = author.get("handle", "")
    actor  = handle_to_actor.get(handle, {})

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
        "feed_category":    "protest",
        "party":            actor.get("party", ""),
        "alliance":         actor.get("alliance", ""),
        "political_stance": actor.get("political_stance", ""),
        "isMilletvekili":   actor.get("isMilletvekili", False),
        "is_tracked_actor": bool(actor),
    }


# ─── Timeline Analysis ─────────────────────────────────────────────────────────

def build_timeline(records: list[dict]) -> dict:
    """
    Build daily volume counts and correlate with PHYSICAL_EVENTS.
    Returns a dict ready for JSON serialisation.
    """
    df = pd.DataFrame(records)
    if df.empty or "created_at" not in df.columns:
        return {"daily_volume": {}, "physical_events": PHYSICAL_EVENTS, "keyword_daily": {}}

    df["date"] = pd.to_datetime(df["created_at"], errors="coerce", utc=True).dt.date
    df = df.dropna(subset=["date"])
    df["date_str"] = df["date"].astype(str)

    # Overall daily volume
    daily_total = df.groupby("date_str").size().to_dict()

    # Per-keyword daily volume (top 15 keywords)
    top_keywords = df["keyword"].value_counts().head(15).index.tolist()
    keyword_daily: dict[str, dict] = {}
    for kw in top_keywords:
        kdf = df[df["keyword"] == kw]
        keyword_daily[kw] = kdf.groupby("date_str").size().to_dict()

    # 3-day rolling average for overall volume
    dates_sorted = sorted(daily_total.keys())
    volumes = [daily_total.get(d, 0) for d in dates_sorted]
    if len(volumes) >= 3:
        rolling = pd.Series(volumes).rolling(3, min_periods=1).mean().tolist()
    else:
        rolling = volumes
    rolling_dict = {d: round(v, 2) for d, v in zip(dates_sorted, rolling)}

    # Peak day
    peak_date = max(daily_total, key=lambda d: daily_total[d]) if daily_total else None

    # Annotate which days fall within our dataset
    event_coverage = {
        date: info
        for date, info in PHYSICAL_EVENTS.items()
        if date in daily_total
    }

    # Unique authors per day
    authors_daily = df.groupby("date_str")["author_handle"].nunique().to_dict()

    # Is-tracked-actor ratio per day
    tracked_daily = (
        df[df["is_tracked_actor"] == True]
        .groupby("date_str")
        .size()
        .to_dict()
    )

    return {
        "total_posts":        len(records),
        "unique_authors":     df["author_handle"].nunique(),
        "date_range":         {
            "since": PROTEST_SINCE,
            "first_post": min(daily_total) if daily_total else None,
            "last_post":  max(daily_total) if daily_total else None,
        },
        "daily_volume":       daily_total,
        "rolling_3day":       rolling_dict,
        "peak_date":          {"date": peak_date, "count": daily_total.get(peak_date, 0)},
        "unique_authors_daily": authors_daily,
        "tracked_actor_daily":  tracked_daily,
        "keyword_daily":      keyword_daily,
        "physical_events":    PHYSICAL_EVENTS,
        "event_coverage":     event_coverage,
        "events_without_posts": [
            d for d in PHYSICAL_EVENTS if d not in daily_total
        ],
    }


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    require(ACCOUNTS_PATH)
    os.makedirs("outputs", exist_ok=True)

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

    now   = datetime.now(timezone.utc)
    until = now.isoformat()
    print(f"Protest search window: {PROTEST_SINCE[:10]} → {until[:10]}")
    print(f"Keywords to search: {len(PROTEST_KEYWORDS)}")

    # Resume support
    seen_uris: set[str]     = set()
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
        print(f"Resuming — {len(all_records)} protest records already loaded.")

    already_searched: set[str] = {rec["keyword"] for rec in all_records}

    with open(RESULTS_PATH, "a", encoding="utf-8") as out:
        for i, kw in enumerate(PROTEST_KEYWORDS, 1):
            if kw in already_searched:
                print(f"  [{i}/{len(PROTEST_KEYWORDS)}] '{kw}' — already done, skipping.")
                continue

            print(f"  [{i}/{len(PROTEST_KEYWORDS)}] Searching: '{kw}' …")
            posts = search_posts(kw, PROTEST_SINCE, until, headers)

            new_count = 0
            for post in posts:
                rec = extract_protest_record(post, kw, handle_to_actor)
                if rec["uri"] in seen_uris:
                    continue
                seen_uris.add(rec["uri"])
                all_records.append(rec)
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                new_count += 1

            out.flush()
            print(f"    → {new_count} new (total: {len(all_records)})")
            time.sleep(SLEEP_NORMAL)

    print(f"\nTotal protest posts collected: {len(all_records)}")

    # Build timeline
    print("\nBuilding protest timeline …")
    timeline = build_timeline(all_records)
    with open(TIMELINE_PATH, "w", encoding="utf-8") as f:
        json.dump(timeline, f, ensure_ascii=False, indent=2)
    print(f"Saved timeline → {TIMELINE_PATH}")

    if timeline.get("peak_date"):
        pd_info = timeline["peak_date"]
        print(f"  Peak day: {pd_info['date']} ({pd_info['count']} posts)")
    if timeline.get("event_coverage"):
        print(f"  Physical events with post data: {len(timeline['event_coverage'])}")
        print(f"  Physical events without post data: {len(timeline.get('events_without_posts', []))}")

    print(f"\nSaved posts → {RESULTS_PATH}")


if __name__ == "__main__":
    main()
