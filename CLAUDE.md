# CLAUDE.md — BlueSky Turkish Political Feed Analysis Pipeline
## ENS491 Graduation Project — Sabancı University

Bu dosya Claude Code agent'ına projeyi nasıl çalıştıracağını ve geliştireceğini anlatır.
Tüm implementation `src/` altındaki `.py` dosyalarında bulunur — burada kod tekrarlanmaz.

---

## 0. PROJE MİMARİSİ

```
PHASE 1 — Hesap Doğrulama & Veri Toplama
  └─ src/01_verify_accounts.py     AT Protocol handle doğrulama
  └─ src/02_fetch_posts.py         Pagination ile tüm postları çek
  └─ src/03_keyword_extraction.py  TF-IDF + LDA konu modelleme

PHASE 2 — Bluesky Geneli Arama
  └─ src/04_weekly_search.py       7 günlük arama + temporal analiz

PHASE 3 — Metin Analizi
  └─ src/05_sentiment_analysis.py  TurkishBERTweet SA + HS
  └─ src/05b_ideology_classifier.py  ML parti tahmini (doğrulama)
  └─ src/05c_statistical_tests.py  İstatistiksel testler + CI

PHASE 4 — Network Analizi
  └─ src/06_network_analysis.py    PageRank, Louvain, assortativity

PHASE 5 — Görselleştirme & Rapor
  └─ src/07_visualizations.py      11 figür (PNG/PDF + interaktif HTML)
  └─ analysis.ipynb                Tüm adımları sırasıyla çalıştıran notebook
```

---

## 1. HIZLI BAŞLANGIÇ

### Kurulum

```bash
git clone <repo-url>
cd ens491_bluesky

python3.12 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt

# Sentiment analizi için (GPU opsiyonel):
# CUDA: pip install torch --index-url https://download.pytorch.org/whl/cu118
# macOS MPS veya CPU: pip install torch

# TurkishBERTweet preprocessor (sadece 05_sentiment_analysis.py için):
git clone https://github.com/ViralLab/TurkishBERTweet.git
```

### Kimlik Bilgileri

```bash
cp .env.example .env
# .env içine Bluesky handle ve App Password gir
# Settings → App Passwords → Add App Password
```

### Pipeline'ı Çalıştır

```bash
# Tüm adımlar sırayla:
python run_pipeline.py

# Belirli adımdan başla:
python run_pipeline.py --from 04

# Sadece görselleştirme:
python run_pipeline.py --only 07

# Sentiment adımını atla (GPU yoksa):
python run_pipeline.py --skip 05,05c

# Notebook ile (önerilen):
jupyter notebook analysis.ipynb
```

---

## 2. DOSYA YAPISI

```
project/
├── CLAUDE.md                                # bu dosya
├── README.md                                # kullanıcıya yönelik özet
├── run_pipeline.py                          # tam pipeline orchestrator
├── requirements.txt                         # Python 3.12.9 bağımlılıkları
├── .env.example / .env                      # Bluesky kimlik bilgileri
├── analysis.ipynb                           # master notebook
│
├── data/
│   ├── combined_users_with_bsky_final.csv   # 1352 aktör (182 doğrulanmış handle)
│   └── bsky_manual_minimal.xlsx
│
├── src/
│   ├── 01_verify_accounts.py
│   ├── 02_fetch_posts.py
│   ├── 03_keyword_extraction.py             # TF-IDF + LDA + party similarity
│   ├── 04_weekly_search.py                  # arama + temporal analiz
│   ├── 05_sentiment_analysis.py             # TurkishBERTweet SA + HS
│   ├── 05b_ideology_classifier.py           # LR/SVM/RF parti tahmini
│   ├── 05c_statistical_tests.py             # Kruskal-Wallis, Mann-Whitney, CI
│   ├── 06_network_analysis.py               # PageRank, Louvain, assortativity
│   └── 07_visualizations.py                 # 11 figür
│
├── TurkishBERTweet/                         # git clone ile eklenir, gitignored
│
└── outputs/
    ├── verified_accounts.csv
    ├── all_posts_raw.jsonl                  # gitignored
    ├── political_keywords.json
    ├── lda_topics.json
    ├── party_topic_similarity.csv
    ├── weekly_search_results.jsonl          # gitignored
    ├── weekly_distribution_stats.json
    ├── temporal_analysis.json
    ├── sentiment_results.csv
    ├── sentiment_stats.json
    ├── statistical_test_results.json
    ├── ideology_classifier_results.json
    ├── ideology_top_features.json
    ├── network_edges.csv
    ├── network_node_metrics.csv
    ├── network_metrics.json
    ├── network_summary.json
    └── figures/
        ├── G1_party_post_counts.png/pdf
        ├── G2_weekly_post_volume.png/pdf
        ├── G3_sentiment_heatmap.png/pdf
        ├── G4_hate_speech_rate.png/pdf
        ├── G5_cross_party_sentiment.png/pdf
        ├── G6_network_interactive.html
        ├── G7_top_active_accounts.png/pdf
        ├── G8_wordclouds.png/pdf
        ├── G9_party_interaction_sankey.html
        ├── G_LDA_topic_similarity.png/pdf
        ├── G_network_scatter.png/pdf
        ├── G_statistical_forest_plot.png/pdf
        ├── ideology_confusion_matrix.png/pdf
        └── lda_<parti>.html                 # per-party pyLDAvis
```

---

## 3. SCRIPT REHBERİ

### 01 — Hesap Doğrulama
**Girdi:** `data/combined_users_with_bsky_final.csv`
**Çıktı:** `outputs/verified_accounts.csv`

`bsky_handle` sütunundaki her handle için AT Protocol public API çağrısı yapar.
HTTP 200 → `verified=True`, DID ve displayName kaydeder.
Rate limit: istek arası 0.3 s, 429'da 10 s bekleme + retry.

### 02 — Post Toplama
**Girdi:** `outputs/verified_accounts.csv`
**Çıktı:** `outputs/all_posts_raw.jsonl`

Doğrulanan her hesap için `app.bsky.feed.getAuthorFeed` cursor-based pagination.
Resume desteği: çöküp yeniden başlatılırsa kaldığı yerden devam eder.
Her 500 postta flush. Quote URI'lerini parse eder.

### 03 — Keyword Extraction + LDA
**Girdi:** `outputs/all_posts_raw.jsonl`
**Çıktı:** `political_keywords.json`, `lda_topics.json`, `party_topic_similarity.csv`

1. TF-IDF (unigram+bigram, min_df=3, sublinear_tf=True) → top-300 term
2. Seed keyword listesi ile birleştirilir → top-200 final liste
3. LDA (Gensim): her parti için ayrı model, C_V coherence ile optimal k seçimi
4. JSD ile partiler arası söylem benzerlik matrisi
5. pyLDAvis HTML → `outputs/figures/lda_<parti>.html`

### 04 — Haftalık Arama + Temporal Analiz
**Girdi:** `political_keywords.json`, `verified_accounts.csv`
**Çıktı:** `weekly_search_results.jsonl`, `weekly_distribution_stats.json`, `temporal_analysis.json`

Son 7 günde top-50 anahtar kelime için `app.bsky.feed.searchPosts` çağrısı.
Temporal analiz: 3 günlük rolling average, Durbin-Watson autocorrelation, peak detection.
`POLITICAL_EVENTS` dict'ine gerçek tarih-olay eşleştirmesi eklenebilir.

### 05 — Sentiment & Hate Speech
**Girdi:** `all_posts_raw.jsonl` + `weekly_search_results.jsonl`
**Çıktı:** `sentiment_results.csv`, `sentiment_stats.json`

TurkishBERTweet Lora-SA (neg/neu/pos) ve Lora-HS (Yes/No).
Batch inference: GPU'da 32, CPU'da 8. Her model sırayla yüklenir (GPU belleği).
`require()` ile TurkishBERTweet klasörü kontrol edilir.

### 05b — Ideology Classifier
**Girdi:** `all_posts_raw.jsonl`
**Çıktı:** `ideology_classifier_results.json`, `ideology_confusion_matrix.png`

TF-IDF (word n-gram + char n-gram) → LR / LinearSVC / RF karşılaştırması.
5-Fold Stratified CV, macro-F1 + MCC metrikleri.
Validation amacı: etiketlerin dilsel anlamlılığını doğrular.

### 05c — İstatistiksel Testler
**Girdi:** `sentiment_results.csv`
**Çıktı:** `statistical_test_results.json`, `G_statistical_forest_plot.png`

1. Kruskal-Wallis H (global parti farkı)
2. Pairwise Mann-Whitney U + FDR-BH düzeltme + rank-biserial r
3. Chi-square + Cramér's V (nefret söylemi × parti)
4. Wilson %95 CI (nefret söylemi oranları)
5. Pearson r (like_count ~ hate_speech)

### 06 — Network Analizi
**Girdi:** `all_posts_raw.jsonl`, `verified_accounts.csv`
**Çıktı:** `network_edges.csv`, `network_node_metrics.csv`, `network_summary.json`

Reply + quote kenarlarından directed graph. Metrikler:
- PageRank (α=0.85)
- Betweenness centrality (top-500 subgraph)
- Louvain community detection (python-louvain yoksa networkx fallback)
- Assortativity katsayısı (echo-chamber testi; >0 = aynı parti tercih ediliyor)
- Reciprocity, density, average clustering
- Bridge node detection (%90 betweenness persentili)

### 07 — Görselleştirme
**Girdi:** önceki adımların tüm çıktıları
**Çıktı:** `outputs/figures/` içinde 11 figür

Her figür eksik girdi varsa graceful skip yapar. PNG (300 DPI) + PDF (vektörel).
`FIGURE_FUNCS` listesine yeni fonksiyon ekleyerek kolayca genişletilir.

---

## 4. MODEL BİLGİLERİ

| Model | Görev | Etiketler | Notlar |
|-------|-------|-----------|--------|
| `VRLLab/TurkishBERTweet-Lora-SA` | Sentiment | negative/neutral/positive | HuggingFace'den otomatik indirilir (~600 MB) |
| `VRLLab/TurkishBERTweet-Lora-HS` | Hate Speech | No/Yes | Ayrı yüklenir, GPU belleği serbest bırakılır |

---

## 5. AT PROTOCOL NOTLARI

- **Public API:** `https://public.api.bsky.app/xrpc/` — giriş gerektirmez, ~50-100 req/dk.
- **DID kararlıdır**, handle değişebilir — mümkün olduğunca DID kullan.
- **Custom domain handle:** `omercelik.com` gibi handle'lar API tarafından çözülür.
- **Cursor:** her zaman `str` tipinde, int değil.
- **429:** tüm scriptler exponential backoff veya sabit bekleme ile retry yapar.

---

## 6. PAPER METODOLOJİ NOTLARI

- **Sentiment:** TurkishBERTweet (Najafi & Varol, 2024), 163M param, 128 token limit.
  Accuracy: dev F1=0.687 (SA), dev F1=0.796 (HS).
- **Ideology:** TF-IDF (word+char n-gram) + LinearSVC, 5-Fold Stratified CV. Metrik: Macro-F1 + MCC.
- **Topic Modeling:** LDA (Gensim), C_V coherence ile k∈{5..11}, JSD parti mesafesi.
- **Network:** Directed graph, PageRank α=0.85, Louvain community detection, assortativity katsayısı.
- **İstatistik:** Kruskal-Wallis + Mann-Whitney U (post-hoc), FDR-BH düzeltme, Wilson %95 CI, Cramér's V.
- **Tekrarlanabilirlik:** Tüm random seed'ler 42. `requirements.txt` ile ortam sabitlendi.

---

## 7. PAPER FİGÜR LİSTESİ

| Figür | Dosya | Paper Bölümü |
|-------|-------|--------------|
| Fig 1 | G2_weekly_post_volume.pdf | §3.1 Data Collection |
| Fig 2 | G3_sentiment_heatmap.pdf | §3.2 Sentiment Analysis |
| Fig 3 | G_statistical_forest_plot.pdf | §3.2 Statistical Validation |
| Fig 4 | G_LDA_topic_similarity.pdf | §3.3 Topic Modeling |
| Fig 5 | ideology_confusion_matrix.pdf | §3.4 Ideology Classification |
| Fig 6 | G_network_scatter.pdf | §3.5 Network Analysis |
| Fig 7 | G6_network_interactive.html | §3.5 (online supplement) |

---

## 8. VERSİYON 1 TAMAMLANMA KRİTERLERİ

- [ ] `verified_accounts.csv` oluşturuldu
- [ ] `all_posts_raw.jsonl` toplandı
- [ ] `political_keywords.json` + `lda_topics.json` üretildi
- [ ] `weekly_search_results.jsonl` toplandı
- [ ] `sentiment_results.csv` etiketlendi
- [ ] `statistical_test_results.json` hesaplandı
- [ ] `ideology_classifier_results.json` üretildi
- [ ] `network_edges.csv` + `network_summary.json` oluşturuldu
- [ ] `outputs/figures/` içinde 11+ figür üretildi
- [ ] `analysis.ipynb` başarıyla çalışıyor

---

## 9. ENS492 — GELECEKTEKİ GELİŞTİRMELER

1. **Two-Tower Ranking:** Actor + post embedding birleşimi, öğrenilmiş sıralama.
2. **LoRA Fine-tuning:** Türk siyasi metinleri üzerinde TurkishBERTweet ince ayarı.
3. **Gerçek Zamanlı Firehose:** AT Protocol Jetstream ile anlık veri akışı.
4. **Feed Generator Server:** Bluesky'de canlı feed yayınlama (`feed-generator`).
5. **Gündem Proximity Skoru:** Haftalık haber gündemini otomatik çekerek postlarla karşılaştırma.

---

## 10. .GITIGNORE HATIRLATICI

```
.env
venv/
outputs/all_posts_raw.jsonl
outputs/weekly_search_results.jsonl
TurkishBERTweet/
__pycache__/
.DS_Store
```

---

*Bu CLAUDE.md Claude Code agent'ına yöneliktir. Kod bu dosyada değil, `src/*.py` dosyalarındadır.
Bir adım hata verirse stack trace'i oku, düzelt, sormadan devam et.*
