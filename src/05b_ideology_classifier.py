"""
PHASE 3b — Ideology Classification
Trains a text classifier to predict party from post content.
If the model accurately predicts party from language alone,
the party labels carry real ideological signal.

Preprocessing improvements:
  - Turkish-aware text cleaning (keep Turkish chars)
  - Hashtag words kept as features
  - Min word length filter, repeated char normalization

Feature engineering:
  - Word TF-IDF (1-3 grams, 30k features)
  - Char TF-IDF (2-5 grams, 15k features)
  - SelectKBest (chi2) feature selection inside CV

Class imbalance:
  - RandomOverSampler inside each CV fold (imblearn pipeline)
  - ComplementNaiveBayes handles imbalance inherently
  - class_weight='balanced' for other classifiers

Models:
  - Logistic Regression (strong baseline for text)
  - Linear SVM        (best for sparse high-dim features)
  - Random Forest     (non-linear, ensemble)
  - Decision Tree     (interpretable single tree)
  - Complement NB     (designed for multi-class text imbalance)

Evaluation: Macro-F1, MCC (both robust to class imbalance).

Outputs:
  outputs/ideology_classifier_results.json
  outputs/ideology_top_features.json
  outputs/figures/ideology_confusion_matrix.png
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
from sklearn.feature_selection import SelectKBest, chi2
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.svm import LinearSVC
from sklearn.tree import DecisionTreeClassifier
from sklearn.naive_bayes import ComplementNB
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.metrics import (
    classification_report, confusion_matrix,
    matthews_corrcoef, f1_score,
)
from sklearn.preprocessing import LabelEncoder
from sklearn.pipeline import Pipeline as SkPipeline

# Graceful fallback if imbalanced-learn is not installed
try:
    from imblearn.pipeline import Pipeline as ImbPipeline
    from imblearn.over_sampling import RandomOverSampler
    HAS_IMBLEARN = True
except ImportError:
    HAS_IMBLEARN = False
    print("[WARN] imbalanced-learn not installed — install with:")
    print("       pip install imbalanced-learn>=0.12.0")
    print("       Falling back to class_weight='balanced' only.")


# ─── Prerequisites ────────────────────────────────────────────────────────────

def require(path: str) -> None:
    if not Path(path).exists():
        print(f"[ERROR] Required file not found: {path}")
        print("Run previous pipeline steps first.")
        sys.exit(1)


# ─── Paths & Config ───────────────────────────────────────────────────────────

POSTS_PATH      = "outputs/all_posts_raw.jsonl"
OUTPUT_JSON     = "outputs/ideology_classifier_results.json"
OUTPUT_FEATS    = "outputs/ideology_top_features.json"
FIGURES_DIR     = "outputs/figures"

MIN_PARTY_POSTS = 30   # skip parties with fewer posts
N_SPLITS        = 5    # stratified k-fold
RANDOM_STATE    = 42
TOP_K_FEATURES  = 20_000   # SelectKBest keeps this many features


# ─── Text Cleaning ────────────────────────────────────────────────────────────

# Turkish characters to keep: ş ç ğ ü ö ı İ Ş Ç Ğ Ü Ö
_KEEP_PATTERN = re.compile(r"[^\w\s]", re.UNICODE)
_REPEAT_PATTERN = re.compile(r"(.)\1{3,}")   # "aaaaa" → "aaa"
_DIGIT_PATTERN  = re.compile(r"\d+")
_SPACE_PATTERN  = re.compile(r"\s+")

def clean_text(text: str) -> str:
    """
    Turkish-aware cleaning:
    - Remove URLs and @mentions
    - Strip # from hashtags but keep the word (politicaly meaningful)
    - Normalize repeated characters (aaaa → aaa)
    - Remove standalone digits
    - Lowercase, strip, collapse whitespace
    - Keep Turkish characters (ş, ç, ğ, ü, ö, ı)
    """
    t = str(text)
    t = re.sub(r"http\S+|www\.\S+", " ", t)   # remove URLs
    t = re.sub(r"@\w+", " ", t)               # remove mentions
    t = re.sub(r"#(\w+)", r" \1 ", t)         # hashtag → word
    t = re.sub(r"&[a-z]+;", " ", t)           # HTML entities (&amp; etc.)
    t = _KEEP_PATTERN.sub(" ", t)             # strip non-word chars (keeps Turkish)
    t = _REPEAT_PATTERN.sub(r"\1\1\1", t)    # normalize repeats
    t = _DIGIT_PATTERN.sub(" ", t)            # remove digits
    t = t.lower().strip()
    # Remove very short tokens (single chars that aren't Turkish connectives)
    tokens = [w for w in t.split() if len(w) >= 2]
    return _SPACE_PATTERN.sub(" ", " ".join(tokens))


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
    Two-stream TF-IDF:
      - Word (1-3 gram): captures phrases like 'merkez bankasi', 'insan haklari'
      - Char (2-5 gram): captures Turkish morphology, partial words
    Combined via horizontal stack → SelectKBest inside each CV pipeline.
    """
    tfidf_word = TfidfVectorizer(
        ngram_range=(1, 3),
        max_features=30_000,
        min_df=2,            # keep words that appear in at least 2 posts
        sublinear_tf=True,
        analyzer="word",
    )
    tfidf_char = TfidfVectorizer(
        ngram_range=(2, 5),
        max_features=15_000,
        min_df=2,
        sublinear_tf=True,
        analyzer="char_wb",  # char_wb pads word boundaries → cleaner than "char"
    )
    X_word = tfidf_word.fit_transform(texts)
    X_char = tfidf_char.fit_transform(texts)
    X      = hstack([X_word, X_char])
    return X, tfidf_word, tfidf_char


# ─── Pipeline Factory ─────────────────────────────────────────────────────────

def make_pipeline(clf, k_features: int, use_oversample: bool = True):
    """
    Build an imblearn (or sklearn) Pipeline:
      SelectKBest → [RandomOverSampler] → Classifier
    SelectKBest is inside the pipeline → no data leakage during CV.
    RandomOverSampler duplicates minority class samples inside each training fold.
    """
    select = SelectKBest(chi2, k=min(k_features, 44_000))  # cap at total features

    if use_oversample and HAS_IMBLEARN:
        return ImbPipeline([
            ("select", select),
            ("ros",    RandomOverSampler(random_state=RANDOM_STATE, shrinkage=None)),
            ("clf",    clf),
        ])
    # Fallback: sklearn Pipeline without oversampling
    return SkPipeline([
        ("select", select),
        ("clf",    clf),
    ])


# ─── Model Evaluation ─────────────────────────────────────────────────────────

def evaluate_models(X, y, label_names: list[str], k_features: int) -> dict:
    """
    Stratified K-fold CV for each classifier.
    Returns {model_name: {macro_f1, mcc, per_class_report}}.
    """
    # Logistic Regression: saga solver handles large sparse matrices + ElasticNet
    lr = LogisticRegression(
        max_iter=2000, C=5.0, solver="saga",
        multi_class="multinomial",
        class_weight="balanced",
        random_state=RANDOM_STATE,
    )
    # LinearSVC: fast and effective on sparse TF-IDF
    svm = LinearSVC(
        max_iter=3000, C=0.5,
        class_weight="balanced",
        dual=True,
    )
    # Random Forest: handles high-dim well with max_features='sqrt'
    rf = RandomForestClassifier(
        n_estimators=300, max_features="sqrt",
        min_samples_leaf=2, n_jobs=-1,
        class_weight="balanced", random_state=RANDOM_STATE,
    )
    # Decision Tree: interpretable; usually weaker on text but shows feature splits
    dt = DecisionTreeClassifier(
        max_depth=30, min_samples_leaf=5,
        class_weight="balanced", random_state=RANDOM_STATE,
    )
    # Complement NB: specifically designed for imbalanced multi-class text
    # No oversampling needed — CNB handles imbalance inherently
    cnb = ComplementNB(alpha=0.3)

    classifiers = {
        "Logistic Regression": make_pipeline(lr,  k_features, use_oversample=True),
        "Linear SVM":          make_pipeline(svm, k_features, use_oversample=True),
        "Random Forest":       make_pipeline(rf,  k_features, use_oversample=False),
        "Decision Tree":       make_pipeline(dt,  k_features, use_oversample=True),
        "Complement NB":       make_pipeline(cnb, k_features, use_oversample=False),
    }

    cv      = StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_STATE)
    results = {}

    for name, pipe in classifiers.items():
        print(f"  Training {name} …")
        try:
            # n_jobs=1 to avoid pickling issues with imblearn + sparse matrices
            y_pred   = cross_val_predict(pipe, X, y, cv=cv, n_jobs=1)
            macro_f1 = f1_score(y, y_pred, average="macro", zero_division=0)
            mcc      = matthews_corrcoef(y, y_pred)
            report   = classification_report(
                y, y_pred, target_names=label_names,
                output_dict=True, zero_division=0,
            )
            results[name] = {
                "macro_f1":  round(macro_f1, 4),
                "mcc":       round(mcc, 4),
                "per_class": report,
            }
            print(f"    macro-F1={macro_f1:.4f}  MCC={mcc:.4f}")
        except Exception as e:
            print(f"    ERROR: {e}")
            results[name] = {"macro_f1": 0.0, "mcc": 0.0, "error": str(e)}

    return results


# ─── Feature Inspection (LR) ──────────────────────────────────────────────────

def top_features_lr(fitted_pipeline, label_names: list[str], top_n: int = 20) -> dict:
    """
    Extract the most discriminative features per class from a fitted LR pipeline.
    Works on SelectKBest → LR pipelines.
    """
    try:
        selector = fitted_pipeline.named_steps["select"]
        clf      = fitted_pipeline.named_steps["clf"]
        if not hasattr(clf, "coef_"):
            return {}
        # Recover feature names that SelectKBest kept
        support = selector.get_support()
        # We don't have the original vectorizers here, so use indices
        selected_indices = np.where(support)[0]
        top_feats = {}
        for i, party in enumerate(label_names):
            coef    = clf.coef_[i]
            top_idx = np.argsort(coef)[-top_n:][::-1]
            top_feats[party] = [f"feat_{selected_indices[j]}" for j in top_idx]
        return top_feats
    except Exception:
        return {}


def top_features_lr_named(tfidf_word, tfidf_char, fitted_lr, label_names, top_n=20):
    """
    Named feature extraction: requires separately fitted vectorizers.
    Used when LR is the best model and re-fitted on full data.
    """
    feature_names = (
        list(tfidf_word.get_feature_names_out())
        + list(tfidf_char.get_feature_names_out())
    )
    top_feats = {}
    for i, party in enumerate(label_names):
        coef    = fitted_lr.coef_[i]
        top_idx = np.argsort(coef)[-top_n:][::-1]
        top_feats[party] = [feature_names[j] for j in top_idx]
    return top_feats


# ─── Confusion Matrix Plot ─────────────────────────────────────────────────────

def plot_confusion_matrix(pipeline, X, y, label_names: list[str], model_name: str) -> None:
    """Save normalised confusion matrix as PNG."""
    cv     = StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_STATE)
    y_pred = cross_val_predict(pipeline, X, y, cv=cv, n_jobs=1)
    cm     = confusion_matrix(y, y_pred, normalize="true")

    short = [lb.split()[0] if len(lb) > 12 else lb for lb in label_names]

    fig, ax = plt.subplots(figsize=(max(7, len(label_names)), max(6, len(label_names) - 1)))
    sns.heatmap(cm, annot=True, fmt=".2f", cmap="Blues",
                xticklabels=short, yticklabels=short,
                linewidths=0.4, ax=ax,
                cbar_kws={"shrink": 0.8, "label": "Normalised Accuracy"})
    ax.set_xlabel("Predicted Party", fontsize=10)
    ax.set_ylabel("True Party", fontsize=10)
    ax.set_title(f"Confusion Matrix — {model_name}", fontsize=11, pad=8)
    ax.set_xticklabels(ax.get_xticklabels(), rotation=40, ha="right", fontsize=8)
    ax.set_yticklabels(ax.get_yticklabels(), rotation=0, fontsize=8)
    plt.tight_layout()

    path = os.path.join(FIGURES_DIR, "ideology_confusion_matrix.png")
    fig.savefig(path, dpi=300, bbox_inches="tight")
    print(f"  Saved: {path}")
    plt.close(fig)


# ─── F1 Comparison Bar Chart ─────────────────────────────────────────────────

def plot_f1_comparison(results: dict) -> None:
    """Horizontal bar chart comparing macro-F1 across classifiers."""
    names  = list(results.keys())
    f1s    = [results[n].get("macro_f1", 0) for n in names]
    mccs   = [results[n].get("mcc", 0)      for n in names]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, max(4, len(names) * 0.7)))
    colors = ["#2980B9"] * len(names)

    ax1.barh(names, f1s, color=colors, edgecolor="white")
    for i, v in enumerate(f1s):
        ax1.text(v + 0.005, i, f"{v:.3f}", va="center", fontsize=9)
    ax1.set_xlim(0, 1.05)
    ax1.set_xlabel("Macro-F1")
    ax1.set_title("Macro-F1 Score by Classifier", pad=8)
    ax1.spines[["top", "right"]].set_visible(False)

    ax2.barh(names, mccs, color=["#27AE60" if m > 0 else "#E74C3C" for m in mccs],
             edgecolor="white")
    for i, v in enumerate(mccs):
        ax2.text(v + 0.005, i, f"{v:.3f}", va="center", fontsize=9)
    ax2.set_xlabel("Matthews Correlation Coefficient")
    ax2.set_title("MCC by Classifier", pad=8)
    ax2.spines[["top", "right"]].set_visible(False)

    fig.suptitle("Ideology Classifier Performance Comparison\n"
                 "(5-fold Stratified CV, party prediction from post text)", fontsize=11)
    plt.tight_layout()
    path = os.path.join(FIGURES_DIR, "ideology_f1_comparison.png")
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
    # Keep posts with at least 5 tokens (very short posts have no discriminative content)
    df = df[df["text_clean"].apply(lambda t: len(t.split()) >= 5)]

    # Keep parties with enough posts for stratified CV
    party_counts = df["party"].value_counts()
    # Need at least N_SPLITS * 2 samples per class for stratified k-fold + oversampling
    min_required = max(MIN_PARTY_POSTS, N_SPLITS * 2)
    valid_parties = party_counts[party_counts >= min_required].index.tolist()
    df = df[df["party"].isin(valid_parties)].copy()

    print(f"Posts after filtering: {len(df)} | Parties: {len(valid_parties)}")
    for p in sorted(valid_parties):
        print(f"  {p}: {party_counts[p]} posts")

    if len(valid_parties) < 2:
        print("Not enough parties with sufficient data — skipping classifier.")
        return

    # Build TF-IDF feature matrix
    print("\nBuilding TF-IDF features …")
    X, tfidf_word, tfidf_char = build_features(df["text_clean"])
    n_features = X.shape[1]
    k_features = min(TOP_K_FEATURES, n_features)
    print(f"  Raw features: {n_features:,} → SelectKBest will keep: {k_features:,}")

    le          = LabelEncoder()
    y           = le.fit_transform(df["party"])
    label_names = list(le.classes_)

    # Cross-validated evaluation for all classifiers
    print(f"\nRunning {N_SPLITS}-fold stratified cross-validation …")
    if HAS_IMBLEARN:
        print("  RandomOverSampler active inside each fold (no data leakage).")
    results = evaluate_models(X, y, label_names, k_features)

    # Save results
    # Strip non-serialisable objects from per_class (classification_report dicts are fine)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nSaved results → {OUTPUT_JSON}")

    # Best model
    best_name = max(results, key=lambda k: results[k].get("macro_f1", 0))
    print(f"\nBest model: {best_name}  "
          f"(macro-F1={results[best_name]['macro_f1']}, "
          f"MCC={results[best_name]['mcc']})")

    # Performance comparison figure
    plot_f1_comparison(results)

    # Rebuild best pipeline and re-fit on full data for feature inspection + confusion matrix
    lr_full = LogisticRegression(
        max_iter=2000, C=5.0, solver="saga",
        multi_class="multinomial",
        class_weight="balanced",
        random_state=RANDOM_STATE,
    )
    best_pipeline = make_pipeline(lr_full, k_features, use_oversample=True)
    best_pipeline.fit(X, y)

    # Top features (from a simple LR fit on full X without SelectKBest, for naming)
    print("Extracting top discriminative features (Logistic Regression) …")
    lr_named = LogisticRegression(
        max_iter=2000, C=5.0, solver="saga",
        multi_class="multinomial", class_weight="balanced",
        random_state=RANDOM_STATE,
    )
    lr_named.fit(X, y)
    top_feats = top_features_lr_named(tfidf_word, tfidf_char, lr_named, label_names, top_n=20)
    with open(OUTPUT_FEATS, "w", encoding="utf-8") as f:
        json.dump(top_feats, f, ensure_ascii=False, indent=2)
    print(f"Saved features → {OUTPUT_FEATS}")

    # Confusion matrix from best pipeline
    print(f"Plotting confusion matrix for: {best_name}")
    plot_confusion_matrix(best_pipeline, X, y, label_names, best_name)

    # Summary
    print("\nFinal Summary:")
    print(f"{'Model':<22} {'Macro-F1':>10} {'MCC':>8}")
    print("-" * 42)
    for name, res in sorted(results.items(), key=lambda t: t[1].get("macro_f1", 0), reverse=True):
        f1  = res.get("macro_f1", 0)
        mcc = res.get("mcc", 0)
        print(f"  {name:<20} {f1:>10.4f} {mcc:>8.4f}")


if __name__ == "__main__":
    main()
