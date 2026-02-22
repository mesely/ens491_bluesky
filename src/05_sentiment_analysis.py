"""
PHASE 3 — Sentiment & Hate Speech Analysis (TurkishBERTweet)
Runs two LoRA-adapted models over all collected posts:
  - VRLLab/TurkishBERTweet-Lora-SA  → negative / neutral / positive
  - VRLLab/TurkishBERTweet-Lora-HS  → hate speech Yes / No

Saves per-post results to outputs/sentiment_results.csv
and summary statistics to outputs/sentiment_stats.json.

NOTE: Requires TurkishBERTweet repo cloned to ./TurkishBERTweet/
  git clone https://github.com/ViralLab/TurkishBERTweet.git
"""

import os
import sys
import json
from collections import defaultdict

import pandas as pd
import torch

# Add TurkishBERTweet's Preprocessor to the import path
sys.path.insert(0, "./TurkishBERTweet")

try:
    from Preprocessor import preprocess  # TurkishBERTweet normaliser
except ImportError:
    raise ImportError(
        "Cannot import Preprocessor. Make sure you cloned TurkishBERTweet:\n"
        "  git clone https://github.com/ViralLab/TurkishBERTweet.git"
    )

from peft import PeftModel, PeftConfig
from transformers import AutoModelForSequenceClassification, AutoTokenizer

# Paths
ACTOR_POSTS_PATH   = "outputs/all_posts_raw.jsonl"
WEEKLY_POSTS_PATH  = "outputs/weekly_search_results.jsonl"
OUTPUT_CSV         = "outputs/sentiment_results.csv"
OUTPUT_STATS       = "outputs/sentiment_stats.json"

# Model identifiers on HuggingFace Hub
SA_MODEL = "VRLLab/TurkishBERTweet-Lora-SA"
HS_MODEL = "VRLLab/TurkishBERTweet-Lora-HS"

if torch.backends.mps.is_available():
    DEVICE = "mps"
elif torch.cuda.is_available():
    DEVICE = "cuda"
else:
    DEVICE = "cpu"

BATCH_SIZE = 16 if DEVICE == "mps" else 32 if DEVICE == "cuda" else 8
MAX_LEN    = 128  # TurkishBERTweet max token length


# ─── Model Loading ──────────────────────────────────────────────────────────

def load_model(peft_model_id: str, num_labels: int, id2label: dict):
    """
    Load a PEFT/LoRA classification model from HuggingFace Hub.
    Returns (model, tokenizer, id2label).
    """
    config    = PeftConfig.from_pretrained(peft_model_id)
    tokenizer = AutoTokenizer.from_pretrained(
        config.base_model_name_or_path, padding_side="right"
    )
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.eos_token_id

    base = AutoModelForSequenceClassification.from_pretrained(
        config.base_model_name_or_path,
        return_dict=True,
        num_labels=num_labels,
        id2label=id2label,
    )
    model = PeftModel.from_pretrained(base, peft_model_id)
    model.eval()
    model.to(DEVICE)
    return model, tokenizer, id2label


# ─── Inference ──────────────────────────────────────────────────────────────

def predict_batch(texts: list[str], model, tokenizer, id2label: dict) -> list[tuple[str, list[float]]]:
    """
    Run inference on a batch of texts.
    Returns list of (label_string, softmax_scores) tuples.
    """
    preprocessed = [preprocess(t) for t in texts]

    encoded = tokenizer(
        preprocessed,
        return_tensors="pt",
        max_length=MAX_LEN,
        truncation=True,
        padding="max_length",
    )
    encoded = {k: v.to(DEVICE) for k, v in encoded.items()}

    with torch.no_grad():
        logits = model(**encoded).logits  # (batch, num_labels)

    probs   = torch.softmax(logits, dim=-1).cpu().tolist()
    labels  = logits.argmax(dim=-1).cpu().tolist()

    return [(id2label[lbl], scores) for lbl, scores in zip(labels, probs)]


def run_model_over_records(records: list[dict], model, tokenizer, id2label: dict,
                           label_col: str, score_col: str) -> list[dict]:
    """
    Iterate over records in batches, add label_col and score_col fields.
    Modifies records in-place and returns them.
    """
    texts = [r.get("text", "") or "" for r in records]

    for start in range(0, len(texts), BATCH_SIZE):
        batch_texts   = texts[start:start + BATCH_SIZE]
        batch_results = predict_batch(batch_texts, model, tokenizer, id2label)

        for i, (label, scores) in enumerate(batch_results):
            rec               = records[start + i]
            rec[label_col]    = label
            rec[score_col]    = scores

        if (start // BATCH_SIZE) % 20 == 0:
            print(f"  Processed {min(start + BATCH_SIZE, len(texts))}/{len(texts)} …")

    return records


# ─── Data Loading ───────────────────────────────────────────────────────────

def load_jsonl(path: str, source_tag: str) -> list[dict]:
    """Read a JSONL file and tag each record with its source."""
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec          = json.loads(line)
                rec["source"] = source_tag
                records.append(rec)
            except json.JSONDecodeError:
                pass
    return records


# ─── Statistics ─────────────────────────────────────────────────────────────

def compute_stats(df: pd.DataFrame) -> dict:
    """
    Compute summary statistics answering the five research questions
    defined in CLAUDE.md section 7.
    """
    stats: dict = {}

    # Q1: Sentiment distribution per party
    party_sentiment = (
        df.groupby(["party", "sentiment"])
        .size()
        .unstack(fill_value=0)
        .apply(lambda row: (row / row.sum()).round(3), axis=1)
        .to_dict(orient="index")
    )
    stats["q1_party_sentiment_ratios"] = party_sentiment

    # Q2: Which party speaks most negatively about others?
    # (approximated by highest negative-sentiment ratio)
    if "sentiment" in df.columns:
        neg_by_party = (
            df[df["sentiment"] == "negative"]
            .groupby("party")
            .size()
            .sort_values(ascending=False)
            .head(5)
            .to_dict()
        )
        stats["q2_most_negative_parties"] = neg_by_party

    # Q3: Hate speech rates per party
    if "hate_speech" in df.columns:
        hs_rate = (
            df.assign(hs_yes=df["hate_speech"] == "Yes")
            .groupby("party")["hs_yes"]
            .mean()
            .round(3)
            .sort_values(ascending=False)
            .to_dict()
        )
        stats["q3_hate_speech_rate_by_party"] = hs_rate

    # Q4: Overall sentiment distribution
    stats["q4_overall_sentiment"] = df["sentiment"].value_counts().to_dict()

    # Q5: Milletvekili vs non-milletvekili sentiment
    if "isMilletvekili" in df.columns:
        mv_sentiment = (
            df.groupby(["isMilletvekili", "sentiment"])
            .size()
            .unstack(fill_value=0)
            .to_dict(orient="index")
        )
        stats["q5_mv_vs_nonmv_sentiment"] = {str(k): v for k, v in mv_sentiment.items()}

    return stats


# ─── Main ───────────────────────────────────────────────────────────────────

def main():
    os.makedirs("outputs", exist_ok=True)

    # Load all posts from both sources
    records: list[dict] = []
    if os.path.exists(ACTOR_POSTS_PATH):
        actor_recs = load_jsonl(ACTOR_POSTS_PATH, "actor_post")
        records.extend(actor_recs)
        print(f"Actor posts loaded: {len(actor_recs)}")
    if os.path.exists(WEEKLY_POSTS_PATH):
        weekly_recs = load_jsonl(WEEKLY_POSTS_PATH, "weekly_search")
        records.extend(weekly_recs)
        print(f"Weekly search posts loaded: {len(weekly_recs)}")

    if not records:
        raise FileNotFoundError(
            "No input posts found. Run 02_fetch_posts.py and 04_weekly_search.py first."
        )

    # Deduplicate by URI
    seen: set[str] = set()
    unique_records: list[dict] = []
    for rec in records:
        uri = rec.get("uri", "")
        if uri and uri not in seen:
            seen.add(uri)
            unique_records.append(rec)

    records = unique_records
    print(f"Total unique posts to analyse: {len(records)}")

    # ── Sentiment Analysis ──────────────────────────────────
    print("\nLoading Sentiment Analysis model …")
    sa_model, sa_tok, sa_labels = load_model(
        SA_MODEL, num_labels=3, id2label={0: "negative", 1: "neutral", 2: "positive"}
    )
    print("Running SA inference …")
    records = run_model_over_records(records, sa_model, sa_tok, sa_labels,
                                     label_col="sentiment", score_col="sentiment_scores")

    # Free GPU memory before loading the next model
    del sa_model
    if DEVICE == "cuda":
        torch.cuda.empty_cache()

    # ── Hate Speech Detection ───────────────────────────────
    print("\nLoading Hate Speech model …")
    hs_model, hs_tok, hs_labels = load_model(
        HS_MODEL, num_labels=2, id2label={0: "No", 1: "Yes"}
    )
    print("Running HS inference …")
    records = run_model_over_records(records, hs_model, hs_tok, hs_labels,
                                     label_col="hate_speech", score_col="hs_scores")

    del hs_model
    if DEVICE == "cuda":
        torch.cuda.empty_cache()

    # ── Build Output DataFrame ──────────────────────────────
    rows = []
    for rec in records:
        sa_scores = rec.get("sentiment_scores", [])
        hs_scores = rec.get("hs_scores", [])
        rows.append({
            "uri":              rec.get("uri", ""),
            "author_handle":    rec.get("author_handle", ""),
            "party":            rec.get("party", ""),
            "alliance":         rec.get("alliance", ""),
            "political_stance": rec.get("political_stance", ""),
            "isMilletvekili":   rec.get("isMilletvekili", False),
            "text_preview":     str(rec.get("text", ""))[:120],
            "created_at":       rec.get("created_at", ""),
            "like_count":       rec.get("like_count", 0),
            "sentiment":        rec.get("sentiment", ""),
            # Individual softmax scores stored as pipe-separated floats
            "sentiment_scores": "|".join(f"{s:.4f}" for s in sa_scores),
            "hate_speech":      rec.get("hate_speech", ""),
            "hs_score":         hs_scores[1] if len(hs_scores) > 1 else 0.0,
            "source":           rec.get("source", ""),
        })

    df = pd.DataFrame(rows)
    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    print(f"\nSaved results → {OUTPUT_CSV}  ({len(df)} rows)")

    # ── Statistics ──────────────────────────────────────────
    stats = compute_stats(df)
    with open(OUTPUT_STATS, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(f"Saved stats   → {OUTPUT_STATS}")

    # Quick console summary
    print("\n── Sentiment Distribution ──")
    print(df["sentiment"].value_counts())
    print("\n── Hate Speech Distribution ──")
    print(df["hate_speech"].value_counts())


if __name__ == "__main__":
    main()
