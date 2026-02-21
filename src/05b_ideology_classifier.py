"""
PHASE 3b — Ideology Classification
Trains a text classifier to predict party from post content.
Serves as a validation layer: if the model can accurately predict party
from language alone, the party labels carry meaningful ideological signal.

Models compared via Stratified 5-Fold CV:
  - Logistic Regression (interpretable baseline)
  - LinearSVC            (sparse high-dimensional favourite)
  - Random Forest        (non-linear, no feature engineering)

Features: TF-IDF (word unigram+bigram) + char n-gram (3-5) concatenated.
Evaluation: Macro-F1, MCC (robust to class imbalance).

Outputs:
  outputs/ideology_classifier_results.json
  outputs/ideology_top_features.json
  outputs/figures/ideology_confusion_matrix.png
  outputs/figures/ideology_confusion_matrix.pdf
"""

import os
import sys
import re
import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

from scipy.sparse import hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.svm import LinearSVC
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.metrics import (
    classification_report, confusion_matrix,
    matthews_corrcoef, f1_score,
)
from sklearn.preprocessing import LabelEncoder


# ─── Prerequisites ────────────────────────────────────────────────────────────

def require(path: str) -> None:
    if not Path(path).exists():
        print(f"[ERROR] Required file not found: {path}")
        print("Run previous pipeline steps first.")
        sys.exit(1)


# ─── Paths ────────────────────────────────────────────────────────────────────

POSTS_PATH   = "outputs/all_posts_raw.jsonl"
OUTPUT_JSON  = "outputs/ideology_classifier_results.json"
OUTPUT_FEATS = "outputs/ideology_top_features.json"
FIGURES_DIR  = "outputs/figures"

MIN_PARTY_POSTS = 30   # Discard parties with fewer posts
N_SPLITS        = 5    # Stratified K-fold
RANDOM_STATE    = 42


# ─── Text Cleaning ────────────────────────────────────────────────────────────

def clean_text(text: str) -> str:
    text = re.sub(r"http\S+", " ", str(text))
    text = re.sub(r"@\w+", " ", text)
    text = re.sub(r"#", " ", text)
    return text.lower().strip()


# ─── Data Loading ─────────────────────────────────────────────────────────────

def load_posts(path: str) -> pd.DataFrame:
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return pd.DataFrame(records)


# ─── Feature Engineering ──────────────────────────────────────────────────────

def build_features(texts: pd.Series):
    """
    Concatenate word TF-IDF (unigram+bigram) and char TF-IDF (3-5 gram).
    Returns sparse matrix X and fitted vectorizers (for inspection).
    """
    tfidf_word = TfidfVectorizer(
        ngram_range=(1, 2), max_features=20_000,
        min_df=3, sublinear_tf=True, analyzer="word",
    )
    tfidf_char = TfidfVectorizer(
        ngram_range=(3, 5), max_features=10_000,
        min_df=3, sublinear_tf=True, analyzer="char_wb",
    )
    X_word = tfidf_word.fit_transform(texts)
    X_char = tfidf_char.fit_transform(texts)
    return hstack([X_word, X_char]), tfidf_word, tfidf_char


# ─── Training & Evaluation ────────────────────────────────────────────────────

def evaluate_models(X, y, label_names: list[str]) -> dict:
    """
    Run Stratified K-fold CV for each classifier.
    Returns dict {model_name: {macro_f1, mcc, per_class_report}}.
    """
    classifiers = {
        "Logistic Regression": LogisticRegression(
            max_iter=1000, C=1.0, class_weight="balanced",
            random_state=RANDOM_STATE,
        ),
        "Linear SVM": LinearSVC(
            max_iter=2000, C=0.5, class_weight="balanced",
        ),
        "Random Forest": RandomForestClassifier(
            n_estimators=200, n_jobs=-1,
            class_weight="balanced", random_state=RANDOM_STATE,
        ),
    }

    cv      = StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_STATE)
    results = {}

    for name, clf in classifiers.items():
        print(f"  Training {name} …")
        y_pred  = cross_val_predict(clf, X, y, cv=cv, n_jobs=-1)
        macro_f1 = f1_score(y, y_pred, average="macro")
        mcc      = matthews_corrcoef(y, y_pred)
        report   = classification_report(y, y_pred,
                                         target_names=label_names,
                                         output_dict=True,
                                         zero_division=0)
        results[name] = {
            "macro_f1":  round(macro_f1, 4),
            "mcc":       round(mcc, 4),
            "per_class": report,
        }
        print(f"    macro-F1={macro_f1:.4f}  MCC={mcc:.4f}")

    return results


def top_features_lr(clf: LogisticRegression,
                    tfidf_word: TfidfVectorizer,
                    tfidf_char: TfidfVectorizer,
                    label_names: list[str],
                    top_n: int = 15) -> dict[str, list[str]]:
    """Extract most discriminative words per class from a fitted LR model."""
    feature_names = (
        list(tfidf_word.get_feature_names_out())
        + list(tfidf_char.get_feature_names_out())
    )
    top_feats: dict[str, list[str]] = {}
    for i, party in enumerate(label_names):
        coef    = clf.coef_[i]
        top_idx = np.argsort(coef)[-top_n:][::-1]
        top_feats[party] = [feature_names[j] for j in top_idx]
    return top_feats


def plot_confusion_matrix(clf, X, y, label_names: list[str], model_name: str) -> None:
    """Save normalised confusion matrix as PNG + PDF."""
    cv    = StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_STATE)
    y_pred = cross_val_predict(clf, X, y, cv=cv)
    cm     = confusion_matrix(y, y_pred, normalize="true")

    # Shorten party labels for readability
    short_labels = [lb.split()[0] if len(lb) > 15 else lb for lb in label_names]

    fig, ax = plt.subplots(figsize=(max(7, len(label_names)), max(6, len(label_names) - 1)))
    sns.heatmap(cm, annot=True, fmt=".2f", cmap="Blues",
                xticklabels=short_labels, yticklabels=short_labels,
                linewidths=0.4, ax=ax,
                cbar_kws={"shrink": 0.8, "label": "Oransal Doğruluk"})
    ax.set_xlabel("Tahmin Edilen Parti", fontsize=10)
    ax.set_ylabel("Gerçek Parti", fontsize=10)
    ax.set_title(f"Normalized Confusion Matrix — {model_name}", fontsize=11, pad=8)
    ax.set_xticklabels(ax.get_xticklabels(), rotation=40, ha="right", fontsize=8)
    ax.set_yticklabels(ax.get_yticklabels(), rotation=0, fontsize=8)
    plt.tight_layout()

    for ext in ("png", "pdf"):
        path = os.path.join(FIGURES_DIR, f"ideology_confusion_matrix.{ext}")
        fig.savefig(path, dpi=300, bbox_inches="tight")
        print(f"  Saved: {path}")
    plt.close(fig)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    require(POSTS_PATH)
    os.makedirs("outputs", exist_ok=True)
    os.makedirs(FIGURES_DIR, exist_ok=True)

    # Load and filter data
    df = load_posts(POSTS_PATH)
    df = df[df["party"].notna() & (df["party"].str.strip() != "")].copy()
    df["text_clean"] = df["text"].fillna("").apply(clean_text)
    df = df[df["text_clean"].str.len() > 5]

    # Keep parties with enough posts
    party_counts = df["party"].value_counts()
    valid_parties = party_counts[party_counts >= MIN_PARTY_POSTS].index.tolist()
    df = df[df["party"].isin(valid_parties)].copy()
    print(f"Posts after filtering: {len(df)} | Parties: {len(valid_parties)}")
    for p in valid_parties:
        print(f"  {p}: {party_counts[p]} posts")

    if len(valid_parties) < 2:
        print("Not enough parties with sufficient data — skipping.")
        return

    # Feature matrix
    print("\nBuilding TF-IDF features …")
    X, tfidf_word, tfidf_char = build_features(df["text_clean"])

    le = LabelEncoder()
    y  = le.fit_transform(df["party"])
    label_names = list(le.classes_)

    # Cross-validated evaluation
    print("\nRunning cross-validation …")
    results = evaluate_models(X, y, label_names)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nSaved → {OUTPUT_JSON}")

    # Best model confusion matrix + feature inspection
    best_name = max(results, key=lambda k: results[k]["macro_f1"])
    print(f"\nBest model: {best_name} (macro-F1={results[best_name]['macro_f1']})")

    # Re-fit best model on full data for feature extraction
    if best_name == "Logistic Regression":
        clf = LogisticRegression(max_iter=1000, C=1.0,
                                  class_weight="balanced",
                                  random_state=RANDOM_STATE)
    elif best_name == "Linear SVM":
        clf = LinearSVC(max_iter=2000, C=0.5, class_weight="balanced")
    else:
        clf = RandomForestClassifier(n_estimators=200, n_jobs=-1,
                                      class_weight="balanced",
                                      random_state=RANDOM_STATE)
    clf.fit(X, y)

    # Top features (LR only — others not easily interpretable)
    if best_name == "Logistic Regression":
        top_feats = top_features_lr(clf, tfidf_word, tfidf_char, label_names)
        with open(OUTPUT_FEATS, "w", encoding="utf-8") as f:
            json.dump(top_feats, f, ensure_ascii=False, indent=2)
        print(f"Saved features → {OUTPUT_FEATS}")

    # Confusion matrix figure
    plot_confusion_matrix(clf, X, y, label_names, best_name)

    print("\nDone. Summary:")
    for name, res in results.items():
        print(f"  {name}: macro-F1={res['macro_f1']}, MCC={res['mcc']}")


if __name__ == "__main__":
    main()
