"""
PHASE 1b — Post Collection
Reads verified_accounts.csv and fetches every post for each verified account
using cursor-based pagination. Saves raw posts as JSONL to outputs/all_posts_raw.jsonl.
"""

import os
import json
import time
import requests
import pandas as pd
from tqdm import tqdm
from political_filters import (
    is_milletvekili_flag,
    is_political_text,
    is_turkish_text,
    should_exclude_actor,
)

# Paths
ACCOUNTS_PATH = "outputs/verified_accounts.csv"
OUTPUT_PATH   = "outputs/all_posts_raw.jsonl"
BASE_URL      = "https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed"

MAX_RETRIES       = 3
SLEEP_NORMAL      = 0.3   # seconds between requests
SLEEP_RATE_LIMIT  = 30    # seconds on 429
CHECKPOINT_EVERY  = 500   # flush file every N posts

# Minimum ratio of political posts to flag an account as likely valid
POLITICAL_CONTENT_THRESHOLD = 0.15   # stricter for quality

# Keywords that indicate a post is political
POLITICAL_SIGNAL_WORDS = {
    "akp", "chp", "mhp", "hdp", "dem", "iyi parti", "yeni yol",
    "meclis", "tbmm", "milletvekili", "seçim", "oy", "iktidar",
    "muhalefet", "hükümet", "cumhurbaşkan", "erdoğan", "özel",
    "kılıçdaroğlu", "akşener", "bahçeli", "demirtaş", "imamoğlu",
    "yavaş", "siyasi", "parti", "muhalif", "iktidar", "anayasa",
    "protesto", "eylem", "gözaltı", "tutuklama",
}


def political_score(posts: list[dict]) -> float:
    """
    Returns the fraction of posts that contain at least one political keyword.
    A low score (< POLITICAL_CONTENT_THRESHOLD) suggests the account may be
    incorrectly matched and warrants manual review.
    """
    if not posts:
        return 0.0
    political_count = 0
    for post in posts:
        text = (post.get("text") or "").lower()
        if is_political_text(text) or any(kw in text for kw in POLITICAL_SIGNAL_WORDS):
            political_count += 1
    return political_count / len(posts)


def fetch_author_feed(actor: str) -> list[dict]:
    """
    Fetch all posts for one actor using cursor-based pagination.
    Returns a flat list of raw feed-item dicts from the API.
    """
    all_items = []
    cursor    = None

    while True:
        params: dict = {"actor": actor, "limit": 100}
        if cursor:
            params["cursor"] = cursor

        for attempt in range(MAX_RETRIES):
            try:
                resp = requests.get(BASE_URL, params=params, timeout=15)
                if resp.status_code == 429:
                    print(f"    [429] Rate limited, sleeping {SLEEP_RATE_LIMIT} s …")
                    time.sleep(SLEEP_RATE_LIMIT)
                    continue
                resp.raise_for_status()
                data = resp.json()
                break
            except requests.RequestException as e:
                print(f"    [error] attempt {attempt + 1}: {e}")
                time.sleep(2)
        else:
            # All retries exhausted for this page — stop fetching this actor
            break

        items = data.get("feed", [])
        if not items:
            break

        all_items.extend(items)
        cursor = data.get("cursor")
        if not cursor:
            break

        time.sleep(SLEEP_NORMAL)

    return all_items


def extract_post_record(item: dict, actor_row: dict) -> dict:
    """
    Flatten one feed item into a flat dict with all fields we care about.
    """
    post   = item.get("post", {})
    record = post.get("record", {})

    # Reply info: extract URI of the parent post
    reply_to_uri = None
    reply_ref    = record.get("reply")
    if reply_ref and isinstance(reply_ref, dict):
        parent = reply_ref.get("parent", {})
        reply_to_uri = parent.get("uri")

    # Quote / embed info
    quote_uri = None
    embed     = record.get("embed", {})
    if embed:
        e_type = embed.get("$type", "")
        if "record" in e_type:
            # Both plain record-embeds and record+media-embeds share a 'record' key
            inner = embed.get("record", {})
            # record+media wraps an additional 'record' level
            if "record" in inner:
                inner = inner.get("record", {})
            quote_uri = inner.get("uri")

    author = post.get("author", {})

    return {
        "uri":           post.get("uri", ""),
        "cid":           post.get("cid", ""),
        "author_did":    author.get("did", actor_row.get("did", "")),
        "author_handle": author.get("handle", actor_row.get("bsky_handle", "")),
        "author_name":   author.get("displayName", actor_row.get("displayName", "")),
        "party":         actor_row.get("party", ""),
        "alliance":      actor_row.get("alliance", ""),
        "political_stance": actor_row.get("political_stance", ""),
        "isMilletvekili":   actor_row.get("isMilletvekili", False),
        "text":          record.get("text", ""),
        "created_at":    record.get("createdAt", ""),
        "like_count":    post.get("likeCount", 0),
        "reply_count":   post.get("replyCount", 0),
        "repost_count":  post.get("repostCount", 0),
        "reply_to_uri":  reply_to_uri,
        "quote_uri":     quote_uri,
    }


def main():
    os.makedirs("outputs", exist_ok=True)

    accounts = pd.read_csv(ACCOUNTS_PATH, encoding="utf-8-sig")
    # Only process accounts that were successfully verified
    verified_df = accounts[accounts["verified"] == True].copy()
    verified_df = verified_df.drop_duplicates(subset=["bsky_handle"], keep="first")
    verified_df = verified_df[
        ~verified_df["bsky_handle"].astype(str).str.strip().str.lower().apply(should_exclude_actor)
    ]
    verified = verified_df.to_dict("records")
    print(f"Verified accounts to process: {len(verified)}")

    # Track already-seen URIs to avoid duplicates across accounts
    seen_uris: set[str] = set()

    # Load already-fetched URIs if we're resuming a previous run
    if os.path.exists(OUTPUT_PATH):
        with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    uri = json.loads(line).get("uri", "")
                    if uri:
                        seen_uris.add(uri)
                except json.JSONDecodeError:
                    pass
        print(f"Resuming — {len(seen_uris)} posts already saved.")

    out_file  = open(OUTPUT_PATH, "a", encoding="utf-8")
    total_new = 0

    for actor_row in tqdm(verified, desc="Accounts"):
        handle = actor_row.get("bsky_handle") or actor_row.get("did", "")
        if not handle:
            continue

        items = fetch_author_feed(handle)
        is_mv = is_milletvekili_flag(actor_row.get("isMilletvekili", False))

        batch = []
        raw_texts = []
        for item in items:
            post_rec = extract_post_record(item, actor_row)
            raw_texts.append(post_rec.get("text", ""))

            # Keep only Turkish + political posts in the final dataset.
            if not is_turkish_text(post_rec.get("text", "")):
                continue
            if not is_political_text(post_rec.get("text", "")):
                continue

            uri      = post_rec["uri"]
            if uri in seen_uris:
                continue
            seen_uris.add(uri)
            batch.append(post_rec)

        raw_political_ratio = (
            sum(1 for t in raw_texts if is_political_text(t)) / len(raw_texts)
            if raw_texts else 0.0
        )

        if is_mv and raw_political_ratio < POLITICAL_CONTENT_THRESHOLD:
            tqdm.write(
                f"  {handle}: milletvekili hesabı politik değil görünüyor "
                f"(raw_political_score={raw_political_ratio:.1%}) — kayıtlar atlandı."
            )
            continue

        # Write batch to file
        for rec in batch:
            out_file.write(json.dumps(rec, ensure_ascii=False) + "\n")
            total_new += 1

        # Periodic flush so data isn't lost on crash
        if total_new % CHECKPOINT_EVERY < len(batch):
            out_file.flush()

        # Political content quality check
        score = political_score(batch) if batch else 0.0
        flag  = " ⚠ LOW POLITICAL CONTENT — manual review recommended" if (
            score < POLITICAL_CONTENT_THRESHOLD and len(batch) >= 10
        ) else ""
        tqdm.write(
            f"  {handle}: {len(batch)} new posts | "
            f"political_score={score:.1%} raw_political_score={raw_political_ratio:.1%}{flag}"
            f" (total so far: {total_new})"
        )

    out_file.close()
    print(f"\nDone. Total new posts saved: {total_new}")
    print(f"Saved → {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
