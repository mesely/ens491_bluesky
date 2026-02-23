"""
PHASE 1a — Account Verification
Reads combined_users_with_bsky_final.csv and verifies each bsky_handle
against the AT Protocol public API. Saves verified results to outputs/verified_accounts.csv.
"""

import os
import time
import requests
import pandas as pd
from dotenv import load_dotenv
from political_filters import is_milletvekili_flag, should_exclude_actor

load_dotenv()

# Paths
DATA_PATH   = "data/combined_users_with_bsky_final.csv"
OUTPUT_PATH = "outputs/verified_accounts.csv"
BASE_URL    = "https://public.api.bsky.app/xrpc"

# Columns to keep in output (original CSV uses 'id', not 'blueskyid')
OUTPUT_COLS = [
    "id", "name", "surname", "party", "alliance",
    "political_stance", "isMilletvekili", "bsky_handle",
    "did", "verified", "displayName",
]


def resolve_handle(handle: str) -> dict | None:
    """Call getProfile on the public API. Returns profile dict or None."""
    url    = f"{BASE_URL}/app.bsky.actor.getProfile"
    params = {"actor": handle}

    for attempt in range(3):
        try:
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 429:
                # Rate-limited — back off and retry
                print(f"  [429] Rate limited on {handle}, sleeping 10 s …")
                time.sleep(10)
                continue
            # 400/404 means handle does not exist
            return None
        except requests.RequestException as e:
            print(f"  [error] {handle}: {e}")
            time.sleep(2)

    return None


def clean_handle(raw) -> str | None:
    """Return None if the value is NaN or the literal string 'nan'."""
    if pd.isna(raw):
        return None
    s = str(raw).strip()
    return None if s.lower() == "nan" else s


def dedupe_candidates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Keep one row per handle. Prefer milletvekili rows when duplicates exist.
    """
    if df.empty:
        return df
    tmp = df.copy()
    tmp["_mv"] = tmp["isMilletvekili"].apply(is_milletvekili_flag)
    tmp = tmp.sort_values(by=["_mv"], ascending=False)
    tmp = tmp.drop_duplicates(subset=["bsky_handle"], keep="first")
    return tmp.drop(columns=["_mv"])


def main():
    os.makedirs("outputs", exist_ok=True)

    df = pd.read_csv(DATA_PATH, encoding="utf-8-sig")

    # Normalise NaN values in handle column
    df["bsky_handle"] = df["bsky_handle"].apply(clean_handle)

    # Only attempt verification for rows that have a handle
    candidates = df[df["bsky_handle"].notna()].copy()
    candidates = candidates[
        ~candidates["bsky_handle"].astype(str).str.strip().str.lower().apply(should_exclude_actor)
    ].copy()
    candidates = dedupe_candidates(candidates)
    print(f"Total rows: {len(df)} | Rows with handle: {len(candidates)}")

    # Result containers
    dids, verified_flags, display_names = [], [], []

    for i, (_, row) in enumerate(candidates.iterrows(), 1):
        handle = row["bsky_handle"]
        profile = resolve_handle(handle)

        if profile:
            dids.append(profile.get("did", ""))
            verified_flags.append(True)
            display_names.append(profile.get("displayName", ""))
            status = "OK"
        else:
            dids.append("")
            verified_flags.append(False)
            display_names.append("")
            status = "FAIL"

        print(f"  [{i}/{len(candidates)}] {handle} → {status}")
        time.sleep(0.3)  # Respect public API rate limits

    candidates = candidates.copy()
    candidates["did"]         = dids
    candidates["verified"]    = verified_flags
    candidates["displayName"] = display_names

    # Keep only the defined output columns (drop any that don't exist)
    existing_cols = [c for c in OUTPUT_COLS if c in candidates.columns]
    result = candidates[existing_cols]

    result.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")

    n_ok   = result["verified"].sum()
    n_fail = len(result) - n_ok
    print(f"\nDone. Verified: {n_ok} | Failed: {n_fail}")
    print(f"Saved → {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
