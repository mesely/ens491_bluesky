"""
PHASE 1c — Political Keyword Extraction
Combines TF-IDF over collected posts with a curated seed list
to produce a ranked set of Turkish political keywords.
Saves results to outputs/political_keywords.json.
"""

import os
import re
import json
from collections import defaultdict

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

# Paths
POSTS_PATH  = "outputs/all_posts_raw.jsonl"
OUTPUT_PATH = "outputs/political_keywords.json"

# Top-N keywords to keep from TF-IDF
TOP_N_TFIDF = 300

# Final keyword list size
TOP_N_FINAL = 200

# Turkish stopwords (expanded beyond CLAUDE.md base set)
STOPWORDS = {
    "bir", "bu", "ve", "ile", "de", "da", "ki", "için",
    "olan", "var", "çok", "daha", "ben", "sen", "biz", "o",
    "ama", "ya", "da", "mi", "mı", "mu", "mü", "ne", "en",
    "bu", "şu", "o", "bunu", "şunu", "ona", "bunun", "şunun",
    "biz", "siz", "onlar", "bizim", "sizin", "onların",
    "hem", "ise", "bile", "artık", "oldu", "olarak", "kadar",
    "sonra", "önce", "gibi", "göre", "karşı", "aynı", "her",
    "bazı", "tüm", "hiç", "çünkü", "eğer", "ancak", "fakat",
    "lakin", "yoksa", "yani", "zaten", "sadece", "bile", "hiçbir",
    "ile", "veya", "yada", "değil", "olarak", "oldu", "olacak",
    "olmak", "olmuş", "olması", "edildi", "edilen", "eden", "etmek",
    "yapılan", "yapıldı", "yapılacak", "hep", "çok", "az", "tam",
    "diye", "dendi", "denildi", "rt", "via", "re",
}

# Curated political seed keywords — ground truth signal
SEED_POLITICAL_KEYWORDS = [
    # Institutions & roles
    "meclis", "tbmm", "milletvekili", "seçim", "oy", "iktidar", "muhalefet",
    "hükümet", "cumhurbaşkanı", "başbakan", "bakan", "kanun", "yasa", "komisyon",
    "anayasa", "demokrasi", "özgürlük", "adalet", "yargı", "mahkeme",
    "cumhurbaşkanlığı", "belediye", "belediye başkanı", "vali", "kaymakam",
    "parti", "genel kurul", "oy kullanma", "seçmen", "referandum",

    # Parties & alliances
    "akp", "chp", "mhp", "hdp", "dem parti", "iyi parti", "yeni yol",
    "cumhur ittifakı", "millet ittifakı", "dip", "saadet", "yeniden refah",
    "hüda par", "yeşil sol", "tgna",

    # Economy
    "enflasyon", "döviz", "dolar", "euro", "ekonomi", "faiz", "bütçe",
    "vergi", "zam", "zamm", "işsizlik", "asgari ücret", "emekli", "esnaf",
    "kira", "konut", "fiyat", "alım gücü", "gelir", "borç", "kredi",
    "merkez bankası", "hazine", "ihracat", "ithalat", "büyüme", "durgunluk",

    # Social issues
    "deprem", "afet", "sığınmacı", "göç", "eğitim", "sağlık", "çevre",
    "iklim", "emniyet", "terör", "kürt", "alevileri", "laiklik",
    "kadın", "şiddet", "çocuk", "aile", "din", "imam", "camii",
    "üniversite", "öğrenci", "öğretmen", "doktor", "hastane",

    # Current affairs & protests
    "gözaltı", "tutuklama", "baskı", "sansür", "medya", "sosyal medya",
    "protesto", "eylem", "yürüyüş", "grev", "işçi", "sendika",
    "basın özgürlüğü", "ifade özgürlüğü", "insan hakları",

    # Key figures (common surnames used in political discourse)
    "erdoğan", "özel", "kılıçdaroğlu", "akşener", "bahçeli", "demirtaş",
    "imamoğlu", "yavaş", "şimşek", "kurum", "yerlikaya",
]


def clean_text(text: str) -> str:
    """Remove URLs, mentions, strip hashtag #, lowercase."""
    text = re.sub(r"http\S+", " ", text)          # remove URLs
    text = re.sub(r"@\w+", " ", text)             # remove @mentions
    text = re.sub(r"#(\w+)", r"\1", text)         # keep hashtag word
    text = re.sub(r"[^\w\s]", " ", text)          # remove punctuation
    text = re.sub(r"\d+", " ", text)              # remove standalone numbers
    text = re.sub(r"\s+", " ", text)              # collapse whitespace
    return text.strip().lower()


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


def run_tfidf(texts: list[str], top_n: int) -> list[str]:
    """Return top-N unigram + bigram terms by mean TF-IDF score."""
    vec = TfidfVectorizer(
        ngram_range=(1, 2),
        max_features=5000,
        stop_words=list(STOPWORDS),
        min_df=3,       # term must appear in at least 3 documents
        sublinear_tf=True,
    )
    X        = vec.fit_transform(texts)
    # Mean TF-IDF score across all documents
    scores   = X.mean(axis=0).A1
    features = vec.get_feature_names_out()

    ranked   = sorted(zip(features, scores), key=lambda t: t[1], reverse=True)
    return [term for term, _ in ranked[:top_n]]


def build_party_keywords(posts: list[dict], final_kws: list[str]) -> dict[str, list[str]]:
    """
    For each party, find which final keywords appear most in that party's posts.
    Returns a dict {party: [top keywords]}.
    """
    party_texts: dict[str, list[str]] = defaultdict(list)
    for p in posts:
        party = p.get("party", "").strip()
        text  = clean_text(p.get("text", ""))
        if party and text:
            party_texts[party].append(text)

    party_keywords: dict[str, list[str]] = {}
    for party, texts in party_texts.items():
        combined = " ".join(texts)
        # Count how many times each final keyword appears in this party's corpus
        counts   = {kw: combined.count(kw) for kw in final_kws}
        ranked   = sorted(counts.items(), key=lambda t: t[1], reverse=True)
        party_keywords[party] = [kw for kw, cnt in ranked if cnt > 0][:50]

    return party_keywords


def main():
    os.makedirs("outputs", exist_ok=True)

    posts = load_posts(POSTS_PATH)
    print(f"Loaded {len(posts)} posts.")

    # Build clean corpus (one string per post)
    texts = [clean_text(p.get("text", "")) for p in posts]
    texts = [t for t in texts if len(t.split()) >= 3]  # skip very short posts
    print(f"Usable texts after filtering: {len(texts)}")

    # TF-IDF keywords
    print("Running TF-IDF …")
    tfidf_kws = run_tfidf(texts, TOP_N_TFIDF)
    print(f"TF-IDF extracted: {len(tfidf_kws)} terms")

    # Merge: seed keywords always included, then fill up with TF-IDF
    seed_set  = set(SEED_POLITICAL_KEYWORDS)
    merged    = list(SEED_POLITICAL_KEYWORDS)

    for kw in tfidf_kws:
        if kw not in seed_set:
            merged.append(kw)
        if len(merged) >= TOP_N_FINAL:
            break

    final_keywords = merged[:TOP_N_FINAL]
    print(f"Final keyword list size: {len(final_keywords)}")

    # Per-party breakdown
    party_kws = build_party_keywords(posts, final_keywords)

    output = {
        "keywords":       final_keywords,
        "by_party":       party_kws,
        "seed_keywords":  SEED_POLITICAL_KEYWORDS,
        "tfidf_keywords": tfidf_kws[:100],
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Saved → {OUTPUT_PATH}")
    print(f"Sample keywords: {final_keywords[:10]}")


if __name__ == "__main__":
    main()
