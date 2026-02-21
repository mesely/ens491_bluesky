"""
PHASE 1c — Political Keyword Extraction + LDA Topic Modeling
Combines TF-IDF + curated seed list for keyword ranking, then runs
LDA topic modeling per party to uncover latent discourse themes.

Outputs:
  outputs/political_keywords.json
  outputs/lda_topics.json
  outputs/party_topic_similarity.csv
  outputs/figures/lda_<party>.html  (pyLDAvis interactive)
"""

import os
import re
import sys
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


# ─── Prerequisites ────────────────────────────────────────────────────────────

def require(path: str) -> None:
    if not Path(path).exists():
        print(f"[ERROR] Required file not found: {path}")
        print("Run previous pipeline steps first.")
        sys.exit(1)


# ─── Paths ────────────────────────────────────────────────────────────────────

POSTS_PATH      = "outputs/all_posts_raw.jsonl"
OUTPUT_KEYWORDS = "outputs/political_keywords.json"
OUTPUT_LDA      = "outputs/lda_topics.json"
OUTPUT_SIM      = "outputs/party_topic_similarity.csv"
FIGURES_DIR     = "outputs/figures"

TOP_N_TFIDF = 300
TOP_N_FINAL = 200
MIN_DOCS_FOR_LDA = 50   # party needs at least this many posts for LDA

# ─── Stopwords ────────────────────────────────────────────────────────────────

STOPWORDS = {
    "bir", "bu", "ve", "ile", "de", "da", "ki", "için",
    "olan", "var", "çok", "daha", "ben", "sen", "biz", "o",
    "ama", "ya", "mi", "mı", "mu", "mü", "ne", "en",
    "şu", "bunu", "şunu", "ona", "bunun", "şunun",
    "siz", "onlar", "bizim", "sizin", "onların",
    "hem", "ise", "bile", "artık", "oldu", "olarak", "kadar",
    "sonra", "önce", "gibi", "göre", "karşı", "aynı", "her",
    "bazı", "tüm", "hiç", "çünkü", "eğer", "ancak", "fakat",
    "lakin", "yoksa", "yani", "zaten", "sadece", "hiçbir",
    "veya", "yada", "değil", "olacak", "olmak", "olmuş", "olması",
    "edildi", "edilen", "eden", "etmek", "yapılan", "yapıldı",
    "yapılacak", "hep", "az", "tam", "diye", "dendi", "denildi",
    "rt", "via", "re", "bu", "şu",
}

# ─── Curated seed keywords ────────────────────────────────────────────────────

SEED_POLITICAL_KEYWORDS = [
    # Institutions & roles
    "meclis", "tbmm", "milletvekili", "seçim", "oy", "iktidar", "muhalefet",
    "hükümet", "cumhurbaşkanı", "başbakan", "bakan", "kanun", "yasa", "komisyon",
    "anayasa", "demokrasi", "özgürlük", "adalet", "yargı", "mahkeme",
    "cumhurbaşkanlığı", "belediye", "vali", "kaymakam",
    "parti", "genel kurul", "seçmen", "referandum",
    # Parties & alliances
    "akp", "chp", "mhp", "hdp", "dem parti", "iyi parti", "yeni yol",
    "cumhur ittifakı", "millet ittifakı", "saadet", "yeniden refah",
    "hüda par", "yeşil sol", "tgna",
    # Economy
    "enflasyon", "döviz", "dolar", "euro", "ekonomi", "faiz", "bütçe",
    "vergi", "zam", "işsizlik", "asgari ücret", "emekli", "esnaf",
    "kira", "konut", "fiyat", "alım gücü", "gelir", "borç", "kredi",
    "merkez bankası", "hazine", "ihracat", "ithalat", "büyüme",
    # Social
    "deprem", "afet", "sığınmacı", "göç", "eğitim", "sağlık", "çevre",
    "iklim", "emniyet", "terör", "kürt", "laiklik",
    "kadın", "şiddet", "çocuk", "aile", "din", "üniversite",
    "öğrenci", "öğretmen", "doktor", "hastane",
    # Civil liberties & protests
    "gözaltı", "tutuklama", "baskı", "sansür", "medya", "sosyal medya",
    "protesto", "eylem", "yürüyüş", "grev", "işçi", "sendika",
    "basın özgürlüğü", "ifade özgürlüğü", "insan hakları",
    # Key political figures
    "erdoğan", "özel", "kılıçdaroğlu", "akşener", "bahçeli", "demirtaş",
    "imamoğlu", "yavaş", "şimşek", "kurum", "yerlikaya",
]


# ─── Text Utilities ───────────────────────────────────────────────────────────

def clean_text(text: str) -> str:
    """Remove URLs, mentions, strip hashtag symbol; lowercase."""
    text = re.sub(r"http\S+", " ", text)
    text = re.sub(r"@\w+", " ", text)
    text = re.sub(r"#(\w+)", r"\1", text)
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\d+", " ", text)
    return re.sub(r"\s+", " ", text).strip().lower()


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


# ─── TF-IDF ───────────────────────────────────────────────────────────────────

def run_tfidf(texts: list[str], top_n: int) -> list[str]:
    """Return top-N unigram + bigram terms ranked by mean TF-IDF score."""
    vec = TfidfVectorizer(
        ngram_range=(1, 2),
        max_features=5000,
        stop_words=list(STOPWORDS),
        min_df=3,
        sublinear_tf=True,
    )
    X        = vec.fit_transform(texts)
    scores   = X.mean(axis=0).A1
    features = vec.get_feature_names_out()
    ranked   = sorted(zip(features, scores), key=lambda t: t[1], reverse=True)
    return [term for term, _ in ranked[:top_n]]


def build_party_keywords(posts: list[dict], final_kws: list[str]) -> dict[str, list[str]]:
    """Count keyword occurrences per party corpus; return top-50 per party."""
    party_texts: dict[str, list[str]] = defaultdict(list)
    for p in posts:
        party = (p.get("party") or "").strip()
        text  = clean_text(p.get("text", ""))
        if party and text:
            party_texts[party].append(text)

    party_keywords: dict[str, list[str]] = {}
    for party, texts in party_texts.items():
        combined = " ".join(texts)
        counts   = {kw: combined.count(kw) for kw in final_kws}
        ranked   = sorted(counts.items(), key=lambda t: t[1], reverse=True)
        party_keywords[party] = [kw for kw, cnt in ranked if cnt > 0][:50]
    return party_keywords


# ─── LDA Topic Modeling ───────────────────────────────────────────────────────

def run_lda(texts: list[str], party_label: str,
            n_topics_range: tuple = (5, 12)) -> dict | None:
    """
    Fit LDA on a party's post corpus. Selects optimal k via C_V coherence.
    Saves a pyLDAvis interactive HTML to outputs/figures/.

    Returns dict with keys: best_k, coherence, topics (list of str), topic_matrix.
    Returns None if gensim/pyLDAvis are unavailable.
    """
    try:
        from gensim import corpora, models
        from gensim.models.coherencemodel import CoherenceModel
        import pyLDAvis.gensim_models as gensimvis
        import pyLDAvis
    except ImportError:
        print("  [LDA] gensim or pyLDAvis not installed — skipping LDA.")
        return None

    tokenized  = [t.split() for t in texts]
    dictionary = corpora.Dictionary(tokenized)
    dictionary.filter_extremes(no_below=5, no_above=0.7)
    corpus = [dictionary.doc2bow(doc) for doc in tokenized]

    if not corpus or not any(corpus):
        return None

    best_model, best_score, best_k = None, -1, 5

    for k in range(*n_topics_range):
        try:
            lda = models.LdaModel(
                corpus, num_topics=k, id2word=dictionary,
                random_state=42, passes=10, alpha="auto", eta="auto",
            )
            cm    = CoherenceModel(model=lda, texts=tokenized,
                                   dictionary=dictionary, coherence="c_v")
            score = cm.get_coherence()
            if score > best_score:
                best_score, best_k, best_model = score, k, lda
        except Exception:
            continue

    if best_model is None:
        return None

    print(f"  [LDA] {party_label}: best k={best_k}, C_V coherence={best_score:.4f}")

    # Per-topic top-10 words
    topics = best_model.print_topics(num_words=10)

    # Compact topic matrix for party-similarity computation (shape: k × vocab)
    topic_matrix = best_model.get_topics()  # ndarray (k, vocab_size)

    # Save pyLDAvis interactive HTML
    try:
        vis        = gensimvis.prepare(best_model, corpus, dictionary, sort_topics=False)
        safe_label = party_label.replace(" ", "_").replace("/", "-")
        vis_path   = os.path.join(FIGURES_DIR, f"lda_{safe_label}.html")
        pyLDAvis.save_html(vis, vis_path)
        print(f"  [LDA] Interactive viz → {vis_path}")
    except Exception as e:
        print(f"  [LDA] pyLDAvis export failed: {e}")

    return {
        "best_k":    best_k,
        "coherence": round(best_score, 4),
        "topics":    [str(t) for t in topics],
        "topic_matrix": topic_matrix.tolist(),
    }


def compute_party_topic_similarity(lda_results: dict) -> pd.DataFrame | None:
    """
    Jensen-Shannon divergence between parties' average topic distributions.
    Lower JSD = more similar discourse.
    """
    try:
        from scipy.spatial.distance import jensenshannon
    except ImportError:
        return None

    party_vecs: dict[str, np.ndarray] = {}
    for party, res in lda_results.items():
        mat = np.array(res["topic_matrix"])  # (k, vocab)
        # Mean topic vector across all topics
        party_vecs[party] = mat.mean(axis=0)

    parties = list(party_vecs.keys())
    n       = len(parties)
    sim     = np.zeros((n, n))

    for i, p1 in enumerate(parties):
        for j, p2 in enumerate(parties):
            v1, v2 = party_vecs[p1], party_vecs[p2]
            # Align to common length (different vocab sizes possible)
            min_len = min(len(v1), len(v2))
            jsd     = jensenshannon(v1[:min_len], v2[:min_len])
            sim[i, j] = round(float(jsd), 6)

    return pd.DataFrame(sim, index=parties, columns=parties)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    require(POSTS_PATH)
    os.makedirs("outputs", exist_ok=True)
    os.makedirs(FIGURES_DIR, exist_ok=True)

    posts = load_posts(POSTS_PATH)
    print(f"Loaded {len(posts)} posts.")

    texts = [clean_text(p.get("text", "")) for p in posts]
    texts = [t for t in texts if len(t.split()) >= 3]
    print(f"Usable texts after filtering: {len(texts)}")

    # ── TF-IDF keywords ───────────────────────────────────────────────
    print("Running TF-IDF …")
    tfidf_kws = run_tfidf(texts, TOP_N_TFIDF)
    print(f"TF-IDF extracted: {len(tfidf_kws)} terms")

    seed_set = set(SEED_POLITICAL_KEYWORDS)
    merged   = list(SEED_POLITICAL_KEYWORDS)
    for kw in tfidf_kws:
        if kw not in seed_set:
            merged.append(kw)
        if len(merged) >= TOP_N_FINAL:
            break
    final_keywords = merged[:TOP_N_FINAL]
    print(f"Final keyword list: {len(final_keywords)}")

    party_kws = build_party_keywords(posts, final_keywords)

    with open(OUTPUT_KEYWORDS, "w", encoding="utf-8") as f:
        json.dump({
            "keywords":       final_keywords,
            "by_party":       party_kws,
            "seed_keywords":  SEED_POLITICAL_KEYWORDS,
            "tfidf_keywords": tfidf_kws[:100],
        }, f, ensure_ascii=False, indent=2)
    print(f"Saved → {OUTPUT_KEYWORDS}")

    # ── LDA topic modeling ────────────────────────────────────────────
    print("\nRunning LDA topic modeling per party …")
    party_texts: dict[str, list[str]] = defaultdict(list)
    for p in posts:
        party = (p.get("party") or "").strip()
        text  = clean_text(p.get("text", ""))
        if party and text:
            party_texts[party].append(text)

    lda_results: dict[str, dict] = {}
    for party, ptexts in sorted(party_texts.items()):
        if len(ptexts) < MIN_DOCS_FOR_LDA:
            print(f"  Skipping {party!r} — only {len(ptexts)} posts (min {MIN_DOCS_FOR_LDA})")
            continue
        print(f"  LDA for {party!r} ({len(ptexts)} posts) …")
        result = run_lda(ptexts, party)
        if result:
            lda_results[party] = result

    # Export LDA topics (strip heavy topic_matrix from JSON to keep file small)
    lda_export = {
        party: {k: v for k, v in res.items() if k != "topic_matrix"}
        for party, res in lda_results.items()
    }
    with open(OUTPUT_LDA, "w", encoding="utf-8") as f:
        json.dump(lda_export, f, ensure_ascii=False, indent=2)
    print(f"Saved → {OUTPUT_LDA}")

    # ── Party topic similarity ────────────────────────────────────────
    if len(lda_results) >= 2:
        sim_df = compute_party_topic_similarity(lda_results)
        if sim_df is not None:
            sim_df.to_csv(OUTPUT_SIM, encoding="utf-8-sig")
            print(f"Saved → {OUTPUT_SIM}")
            print("Party discourse similarity (JSD, lower = more similar):")
            print(sim_df.round(3).to_string())

    print(f"\nSample keywords: {final_keywords[:10]}")


if __name__ == "__main__":
    main()
