# CLAUDE.md — BlueSky Turkish Political Feed Analysis Pipeline
## Project: Developing BlueSky Custom Feeds for Turkish Political Systems

Bu dosya Claude Code agent'ına bu projeyi baştan sona nasıl çalıştıracağını anlatan ana komut belgesidir.
Her adımı sırayla, eksiksiz ve bağımsız modüller hâlinde yaz. Tüm çıktılar `outputs/` klasörüne gitsin.

---

## 0. PROJE GENEL MİMARİSİ

```
PHASE 1 — Hesap Doğrulama & Veri Toplama
  └─ 1a. CSV'deki bsky_handle'ları AT Protocol API ile doğrula
  └─ 1b. Doğrulanan hesapların tüm postlarını çek (pagination ile)
  └─ 1c. Postlardan siyasi anahtar kelime seti oluştur

PHASE 2 — Bluesky Geneli Arama & Dağılım
  └─ 2a. Anahtar kelimelerle son 7 gün bluesky geneli ara
  └─ 2b. Post dağılımlarını hesapla (zaman, parti, ittifak bazlı)

PHASE 3 — Sentiment Analysis (TurkishBERTweet)
  └─ 3a. Her postu ön işle (preprocessor)
  └─ 3b. Sentiment: pozitif / nötr / negatif (Lora-SA)
  └─ 3c. Hate Speech tespiti (Lora-HS)
  └─ 3d. Parti bazlı sentimenti grupla

PHASE 4 — Network Analizi & Görselleştirme
  └─ 4a. Etkileşim ağı oluştur (reply/quote/like)
  └─ 4b. Network graph (NetworkX + PyVis)
  └─ 4c. Tüm analizleri sade, anlamlı grafiklerle görselleştir

PHASE 5 — Rapor & Özet
  └─ 5a. Bulguları markdown özet belgesi olarak yaz
```

---

## 1. ORTAM KURULUMU

Proje Python 3.10+ gerektirir. Sanal ortam oluştur:

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install atproto pandas openpyxl requests tqdm \
            torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
pip install transformers peft urlextract
pip install networkx pyvis matplotlib seaborn plotly
pip install jupyter ipykernel wordcloud scikit-learn
pip install python-dotenv
```

`.env` dosyası oluştur (repo'ya commit ETME):
```
BSKY_IDENTIFIER=your_bluesky_email_or_handle
BSKY_PASSWORD=your_bluesky_app_password
```

Bluesky App Password almak için: Settings → App Passwords → Add App Password.

---

## 2. DOSYA YAPISI

```
project/
├── CLAUDE.md                          # bu dosya
├── .env                               # kimlik bilgileri (gitignore'da!)
├── .gitignore
├── data/
│   ├── combined_users_with_bsky_final.csv   # ana actor listesi
│   └── bsky_manual_minimalda.xlsx           # manuel doğrulama listesi
├── outputs/
│   ├── verified_accounts.csv
│   ├── all_posts_raw.jsonl
│   ├── political_keywords.json
│   ├── weekly_search_results.jsonl
│   ├── sentiment_results.csv
│   ├── network_edges.csv
│   └── figures/
│       ├── *.png / *.html
├── src/
│   ├── 01_verify_accounts.py
│   ├── 02_fetch_posts.py
│   ├── 03_keyword_extraction.py
│   ├── 04_weekly_search.py
│   ├── 05_sentiment_analysis.py
│   ├── 06_network_analysis.py
│   └── 07_visualizations.py
└── analysis.ipynb                     # tüm adımları bir arada gören notebook
```

---

## 3. PHASE 1a — HESAP DOĞRULAMA (`01_verify_accounts.py`)

**Görev:** `combined_users_with_bsky_final.csv` dosyasındaki `bsky_handle` sütununu AT Protocol API ile gerçek zamanlı doğrula.

### CSV Sütunları:
- `blueskyid`, `name`, `surname`, `party`, `alliance`, `isMilletvekili`
- `bsky_handle` — doğrulanacak olan (NaN ise boş bırak)
- `bsky_match_status` — `ok`, `manual`, `auto` değerleri mevcut

### Yapılacaklar:
1. CSV'yi pandas ile oku.
2. `bsky_handle` dolu olan satırları filtrele (`bsky_match_status == 'ok'` veya handle NaN değil).
3. Her handle için AT Protocol `app.bsky.actor.getProfile` endpoint'ini çağır:
   ```
   GET https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile?actor=<handle>
   ```
   - Başarılıysa (HTTP 200) → `verified=True`, `did` ve `displayName` kaydet.
   - Başarısızsa (404 vb.) → `verified=False` kaydet.
4. Oturum açmayı gerektirmeyen public endpoint'leri kullan mümkün olduğunca.
   Oturum gereken şeyler için `atproto` kütüphanesini kullan:
   ```python
   from atproto import Client
   client = Client()
   client.login(os.getenv("BSKY_IDENTIFIER"), os.getenv("BSKY_PASSWORD"))
   ```
5. Rate limit: istekler arası `time.sleep(0.3)` koy. 429 alırsan `time.sleep(10)` ve tekrar dene.
6. Çıktıyı `outputs/verified_accounts.csv` olarak kaydet. Sütunlar:
   `blueskyid, name, surname, party, alliance, political_stance, bsky_handle, did, verified, displayName`

### Önemli Notlar:
- `omercelik.com` gibi custom domain handle'lar geçerlidir, AT Protocol bunları çözer.
- `nan` string'i olan satırları NaN gibi işle.
- `bsky_match_status == 'manual'` olan satırları da doğrulamaya çalış ama olmayanlara zorla.

---

## 4. PHASE 1b — POST TOPLAMA (`02_fetch_posts.py`)

**Görev:** Doğrulanmış her hesabın tüm postlarını çek.

### Yöntem:
AT Protocol `app.bsky.feed.getAuthorFeed` endpoint'i:
```
GET https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed
    ?actor=<did_or_handle>
    &limit=100
    &cursor=<pagination_cursor>
```

### Uygulama Detayları:
1. `outputs/verified_accounts.csv` oku, `verified=True` olanları al.
2. Her hesap için cursor tabanlı pagination ile tüm postları çek:
   ```python
   cursor = None
   while True:
       params = {"actor": did, "limit": 100}
       if cursor:
           params["cursor"] = cursor
       response = requests.get(url, params=params)
       data = response.json()
       posts = data.get("feed", [])
       if not posts:
           break
       # kaydet
       cursor = data.get("cursor")
       if not cursor:
           break
       time.sleep(0.3)
   ```
3. Her post için şu alanları kaydet (JSONL formatında, satır satır):
   ```json
   {
     "uri": "at://...",
     "cid": "...",
     "author_did": "...",
     "author_handle": "...",
     "author_name": "...",
     "party": "...",
     "alliance": "...",
     "political_stance": "...",
     "text": "...",
     "created_at": "...",
     "like_count": 0,
     "reply_count": 0,
     "repost_count": 0,
     "reply_to_uri": null,
     "quote_uri": null
   }
   ```
4. Çıktı: `outputs/all_posts_raw.jsonl` — her satır bir JSON post.
5. Duplicate URI kontrolü yap (set ile).
6. İlerlemeyi `tqdm` ile göster.

### Rate Limit Stratejisi:
- Normal istekler: `time.sleep(0.3)`
- 429 hatası: `time.sleep(30)`, retry max 3 kez
- Her 500 postta bir checkpoint JSONL'yi flush et

---

## 5. PHASE 1c — SİYASİ ANAHTAR KELİME ÇIKARIMI (`03_keyword_extraction.py`)

**Görev:** Toplanan postlardan Türk siyasetiyle ilgili anlamlı anahtar kelimeler çıkar.

### Yöntem (Kural Tabanlı + TF-IDF Hibrit):

1. `outputs/all_posts_raw.jsonl` oku.
2. Türkçe stopword listesi kullan (hazır liste aşağıda, genişlet):
   ```python
   STOPWORDS = {"bir", "bu", "ve", "ile", "de", "da", "ki", "için",
                "olan", "var", "çok", "daha", "ben", "sen", "biz", "o",
                "ama", "ya", "da", "mi", "mı", "mu", "mü", "ne", "en"}
   ```
3. Metin temizleme:
   - URL'leri kaldır (`re.sub(r'http\S+', '', text)`)
   - Mention'ları kaldır (`@handle`)
   - Hashtag # işaretini kaldır ama kelimeyi tut
   - Küçük harfe çevir
4. TF-IDF ile en önemli unigram ve bigramları çıkar (`sklearn.TfidfVectorizer`).
5. Aynı zamanda elle tanımlanmış **siyasi seed kelimeler** listesini kullan:

```python
SEED_POLITICAL_KEYWORDS = [
    # Genel siyasi
    "meclis", "tbmm", "milletvekili", "seçim", "oy", "iktidar", "muhalefet",
    "hükümet", "cumhurbaşkanı", "başbakan", "bakan", "kanun", "yasa", "komisyon",
    "anayasa", "demokrasi", "özgürlük", "adalet", "yargı", "mahkeme",
    
    # Partiler
    "akp", "chp", "mhp", "hdp", "dem parti", "iyi parti", "yeni yol",
    "cumhur ittifakı", "millet ittifakı", "dip", "saadet",
    
    # Ekonomi
    "enflasyon", "döviz", "dolar", "euro", "ekonomi", "faiz", "bütçe",
    "vergi", "zamm", "işsizlik", "asgari ücret", "emekli", "esnaf",
    
    # Sosyal
    "deprem", "afet", "sığınmacı", "göç", "eğitim", "sağlık", "çevre",
    "iklim", "emniyet", "terör", "kürt", "alevileri", "laiklik",
    
    # Gündem
    "gözaltı", "tutuklama", "baskı", "sansür", "medya", "sosyal medya",
    "protesto", "eylem", "yürüyüş", "grev", "işçi",
]
```

6. TF-IDF skorları yüksek ve siyasi seed ile örtüşen kelimeleri birleştir.
7. Top 200 anahtar kelimeyi JSON olarak kaydet:
   ```json
   {
     "keywords": ["meclis", "seçim", ...],
     "by_party": {
       "Cumhuriyet Halk Partisi": ["...", ...],
       "Adalet ve Kalkınma Partisi": ["...", ...]
     },
     "seed_keywords": ["..."],
     "tfidf_keywords": ["..."]
   }
   ```
   Çıktı: `outputs/political_keywords.json`

---

## 6. PHASE 2 — BLUESKY GENELİNDE HAFTALIK ARAMA (`04_weekly_search.py`)

**Görev:** Çıkarılan anahtar kelimelerle Bluesky'de son 7 gün içindeki postları ara ve dağılımları hesapla.

### AT Protocol Arama Endpoint'i:
```
GET https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts
    ?q=<keyword>
    &limit=100
    &since=<ISO8601_datetime>
    &until=<ISO8601_datetime>
    &cursor=<cursor>
```

### Uygulama:
1. `outputs/political_keywords.json` oku, top 50 kelimeyi kullan (çok fazla istek yapmamak için).
2. Son 7 günün tarihini hesapla:
   ```python
   from datetime import datetime, timedelta, timezone
   since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
   until = datetime.now(timezone.utc).isoformat()
   ```
3. Her anahtar kelime için pagination ile postları çek (max 500 post/keyword).
4. Her post için kaydet: `uri, text, author_handle, created_at, like_count, keyword`
5. Yazar handle'ı `verified_accounts.csv` ile karşılaştır → parti/ittifak etiketi ekle.
6. Çıktı: `outputs/weekly_search_results.jsonl`

### Dağılım Analizi (bu script içinde):
- Keyword başına post sayısı
- Günlük post hacmi (time series)
- Parti başına kaç post
- Hesap başına kaç post (top 20)

Bu istatistikleri `outputs/weekly_distribution_stats.json` olarak kaydet.

---

## 7. PHASE 3 — SENTIMENT ANALİZİ (`05_sentiment_analysis.py`)

**Görev:** TurkishBERTweet Lora modellerini kullanarak her postun duygusunu ve nefret söylemi içerip içermediğini saptıyoruz.

### TurkishBERTweet Kurulumu ve Kullanımı:

```bash
git clone https://github.com/ViralLab/TurkishBERTweet.git
# Preprocessor klasörünü proje kökünüze kopyalayın:
cp -r TurkishBERTweet/Preprocessor ./
```

### Model Bilgileri:
| Model | Görev | Etiketler |
|-------|-------|-----------|
| `VRLLab/TurkishBERTweet` | Base model / feature extraction | — |
| `VRLLab/TurkishBERTweet-Lora-SA` | Sentiment Analysis | negative(0), neutral(1), positive(2) |
| `VRLLab/TurkishBERTweet-Lora-HS` | Hate Speech Detection | No(0), Yes(1) |

### Tam Uygulama Kodu (kopyala/yapıştır kullanılabilir şablonu):

```python
import sys
sys.path.insert(0, "./TurkishBERTweet")  # veya Preprocessor klasörünün üst dizini

import torch
from peft import PeftModel, PeftConfig
from transformers import AutoModelForSequenceClassification, AutoTokenizer
from Preprocessor import preprocess  # TurkishBERTweet repo'sundan

def load_sentiment_model():
    peft_model = "VRLLab/TurkishBERTweet-Lora-SA"
    peft_config = PeftConfig.from_pretrained(peft_model)
    tokenizer = AutoTokenizer.from_pretrained(
        peft_config.base_model_name_or_path, padding_side="right"
    )
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.eos_token_id
    id2label = {0: "negative", 1: "neutral", 2: "positive"}
    model = AutoModelForSequenceClassification.from_pretrained(
        peft_config.base_model_name_or_path,
        return_dict=True, num_labels=3, id2label=id2label
    )
    model = PeftModel.from_pretrained(model, peft_model)
    model.eval()
    return model, tokenizer, id2label

def load_hatespeech_model():
    peft_model = "VRLLab/TurkishBERTweet-Lora-HS"
    peft_config = PeftConfig.from_pretrained(peft_model)
    tokenizer = AutoTokenizer.from_pretrained(
        peft_config.base_model_name_or_path, padding_side="right"
    )
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.eos_token_id
    id2label = {0: "No", 1: "Yes"}
    model = AutoModelForSequenceClassification.from_pretrained(
        peft_config.base_model_name_or_path,
        return_dict=True, num_labels=2, id2label=id2label
    )
    model = PeftModel.from_pretrained(model, peft_model)
    model.eval()
    return model, tokenizer, id2label

def predict(text, model, tokenizer, id2label):
    preprocessed = preprocess(text)
    # Model max 128 token — uzun metni truncate et
    ids = tokenizer.encode_plus(
        preprocessed, return_tensors="pt",
        max_length=128, truncation=True, padding="max_length"
    )
    with torch.no_grad():
        logits = model(**ids).logits
        label_id = logits.argmax(-1).item()
    return id2label[label_id], torch.softmax(logits, dim=-1).squeeze().tolist()
```

### Batch Processing (GPU varsa hızlıdır):
- GPU yoksa CPU'da da çalışır ama yavaştır.
- Batch size = 32 kullan GPU'da, 8 CPU'da.
- `torch.cuda.is_available()` kontrol et, ona göre `device` ayarla.
- Her model için ayrı döngü çalıştır (SA, sonra HS). İkisini de aynı anda belleğe alma.

### Çıktı (`outputs/sentiment_results.csv`):
```
uri, author_handle, party, alliance, political_stance, text_preview,
created_at, like_count, sentiment, sentiment_scores, hate_speech,
hs_score, source  (actor_post / weekly_search)
```

### Analiz Soruları (kod içinde cevapla, istatistik üret):
1. Her parti için sentiment dağılımı (positive/neutral/negative oranları)
2. Hangi parti diğerleri hakkında en çok negatif konuşuyor?
3. Nefret söylemi en yüksek olan hesaplar/partiler
4. Kendi partisi hakkında olumlu konuşma oranı vs karşı parti hakkında
5. Milletvekili mi, değil mi — sentiment farkı var mı?

---

## 8. PHASE 4 — NETWORK ANALİZİ (`06_network_analysis.py`)

**Görev:** Kim kimle etkileşiyor? Reply ve quote graph'ları oluştur.

### Kenar (Edge) Tanımı:
- **Reply:** A kişisi B kişisinin postuna cevap verdi → A→B kenarı (reply)
- **Quote:** A kişisi B kişisinin postunu alıntıladı → A→B kenarı (quote)
- **Like:** (varsa) → A→B kenarı (like)

### Uygulama:
1. `outputs/all_posts_raw.jsonl` oku.
2. `reply_to_uri` alanı dolu olan postlar için:
   - URI'den author did çek ya da `in_reply_to_author` alanından.
3. `quote_uri` alanı dolu olanlar için aynısını yap.
4. Her kenar için parti bilgisini ekle.
5. Çıktı `outputs/network_edges.csv`:
   ```
   source_handle, source_party, target_handle, target_party, edge_type, weight
   ```

### NetworkX Graph:
```python
import networkx as nx

G = nx.DiGraph()
# node'lara parti rengi ata
PARTY_COLORS = {
    "Cumhuriyet Halk Partisi": "#E63946",
    "Adalet ve Kalkınma Partisi": "#FFC300",
    "Miliyetçi Hareket Partisi": "#C9A84C",
    "Halkların Eşitlik ve Demokrasi Partisi": "#2ECC71",
    "İYİ Parti": "#3498DB",
    "Yeni Yol": "#9B59B6",
    "Bağımsız": "#95A5A6",
}
```

### Hesaplanacak Metrikler:
- In-degree ve out-degree (kim çok alıntılanıyor, kim çok etkileşiyor)
- Betweenness centrality (köprü hesaplar)
- Topluluk tespiti: `nx.community.greedy_modularity_communities()`
- Parti içi vs parti arası etkileşim oranı

---

## 9. PHASE 5 — GÖRSELLEŞTİRME (`07_visualizations.py`)

**Tasarım Prensipleri (ZORUNLU):**
- Her grafik için gereksiz ızgara çizgisi, kenarlık, ve açıklama kaldır.
- Renk paleti tutarlı: partiler için hep aynı renkler kullan (PARTY_COLORS dict).
- Başlık kısa ve açıklayıcı olsun; alt başlık (subtitle) ile detay ver.
- Seaborn `set_theme("white")` ve `despine()` kullan.
- Figür boyutları: genelde `(12, 6)` veya `(10, 8)`.
- DPI=150 ile kaydet.

### Üretilecek Grafikler:

#### G1 — Parti Bazında Hesap & Post Sayısı
```python
# Yatay bar chart
# X: post sayısı, Y: parti adı, renk: PARTY_COLORS
```

#### G2 — Haftalık Post Hacmi (Zaman Serisi)
```python
# Line chart, her parti ayrı renk
# X: tarih, Y: günlük post sayısı
# Hafıza dostu: max 6 parti göster, ötekiler "Diğer" yap
```

#### G3 — Sentiment Dağılımı (Parti Bazında)
```python
# Stacked horizontal bar chart
# Her çubuk = bir parti
# Segmentler: positive (yeşil), neutral (gri), negative (kırmızı)
# Oranlar göster, ham sayı değil
```

#### G4 — Nefret Söylemi Oranı (Parti Bazında)
```python
# Dot plot veya bar chart
# X: nefret söylemi oranı (%), Y: parti
# Hata çubuğu ekle (± std)
```

#### G5 — Kendi Partisine vs Karşı Tarafa Sentiment Karşılaştırması
```python
# Grouped bar chart veya heatmap
# Satır: konuşan parti, Sütun: bahsedilen parti
# Değer: ortalama pozitiflik skoru
# Bu için postun hangi partiden bahsettiğini tespit et:
#   → PARTY_MENTION_KEYWORDS dict kullan:
#     {"CHP": ["chp", "cumhuriyet halk", "özgür özel", ...],
#      "AKP": ["akp", "adalet ve kalkınma", "erdoğan", "ak parti", ...], ...}
```

#### G6 — Network Graph (Etkileşim Ağı)
```python
# PyVis ile interaktif HTML
from pyvis.network import Network
net = Network(height="750px", width="100%", directed=True)
# Node rengi: PARTY_COLORS
# Node büyüklüğü: in-degree ile orantılı
# Kenar kalınlığı: weight ile orantılı
# Çıktı: outputs/figures/network_interactive.html
```

#### G7 — En Aktif Hesaplar Top 20
```python
# Yatay bar chart
# X: post sayısı, renk: parti rengi
# Hover'da: hesap adı, parti, milletvekili mi?
```

#### G8 — Anahtar Kelime WordCloud (Parti Bazında)
```python
from wordcloud import WordCloud
# Her parti için ayrı wordcloud
# Renk: o partinin renk paleti tonu
# 2x3 veya 3x2 subplot grid
```

#### G9 — Parti Destekçi Kitlesi Analizi (Kim Kimleri RT/Alıntılıyor)
```python
# Sankey diagram (Plotly) veya Chord diagram
# Kaynak: reply/quote yapan hesabın partisi
# Hedef: alıntılanan hesabın partisi
# Kalınlık: etkileşim sayısı
```

Tüm grafikler `outputs/figures/` klasörüne kaydet: `.png` (statik) + `.html` (interaktif varsa).

---

## 10. ANALYSIS.IPYNB — ANA NOTEBOOK

Tüm `src/` scriptlerini sırayla çağıran bir ana notebook yaz. Her section başında:
- Ne yapıyor: kısa açıklama
- Input/Output dosyaları
- Örnek çıktı göster (ilk 5 satır DataFrame vb.)

Notebook bölümleri:
```
0. Setup & Imports
1. Account Verification [01_verify_accounts.py çalıştır]
2. Post Collection [02_fetch_posts.py çalıştır]
3. Keyword Extraction [03_keyword_extraction.py çalıştır]
4. Weekly Search [04_weekly_search.py çalıştır]
5. Sentiment Analysis [05_sentiment_analysis.py çalıştır]
6. Network Analysis [06_network_analysis.py çalıştır]
7. Visualizations [07_visualizations.py çalıştır]
8. Summary Statistics & Findings
```

Her script için notebook'ta şöyle çağır:
```python
import subprocess
result = subprocess.run(["python", "src/01_verify_accounts.py"], capture_output=True, text=True)
print(result.stdout)
if result.returncode != 0:
    print("HATA:", result.stderr)
```

---

## 11. PÜF NOTLARI & SIKÇA KARŞILAŞILAN SORUNLAR

### AT Protocol API:
- **Rate Limit:** Public endpoint'ler genelde dakikada ~50-100 istek. Dikkatli ol.
- **Pagination:** `cursor` her zaman string, int değil.
- **DID vs Handle:** Mümkünse `did` kullan (handle değişebilir, DID değişmez).
- **Public API:** `https://public.api.bsky.app/xrpc/` — giriş gerekmez, ama limitleri düşük.
- **Auth API:** `https://bsky.social/xrpc/` — oturum gerektiren, limitleri daha yüksek.
- Custom domain handle çözümlemek için:
  ```
  GET https://public.api.bsky.app/xrpc/com.atproto.identity.resolveHandle?handle=omercelik.com
  ```

### TurkishBERTweet:
- **Max length 128 token** — daha uzun metinleri `truncation=True` ile kes.
- **Preprocessor'ı import etmek için** `sys.path` ayarını doğru yap.
- **GPU bellek hatası:** Batch size'ı düşür veya `model.half()` (FP16) kullan.
- **Model indirme:** İlk çalıştırmada HuggingFace'den ~600MB indirir, internet bağlantısı gerekli.
- Emojileri `<emoji> ... </emoji>` etiketine çevirir preprocessor — bu beklenen davranış.

### Pandas / CSV:
- `combined_users_with_bsky_final.csv` okunurken encoding=utf-8-sig dene (BOM olabilir).
- `nan` string'i ile gerçek NaN'ı ayırt etmek için:
  ```python
  df['bsky_handle'] = df['bsky_handle'].replace('nan', pd.NA)
  df = df[df['bsky_handle'].notna()]
  ```

### Görselleştirme:
- Türkçe karakter sorunu için matplotlib'de:
  ```python
  import matplotlib
  matplotlib.rcParams['font.family'] = 'DejaVu Sans'
  # veya
  plt.rcParams.update({'font.family': 'Arial Unicode MS'})
  ```
- Seaborn ve matplotlib'i birlikte kullanırken `fig, ax = plt.subplots()` pattern'ını kullan.

---

## 12. VERSİYON 1 TAMAMLANMA KRİTERLERİ

Aşağıdakilerin hepsi tamamlanınca Version 1 bitmiş sayılır:

- [ ] `verified_accounts.csv` — tüm handle'lar doğrulandı
- [ ] `all_posts_raw.jsonl` — doğrulanan hesapların postları çekildi
- [ ] `political_keywords.json` — 100+ siyasi anahtar kelime listelendi
- [ ] `weekly_search_results.jsonl` — son 7 günün bluesky verileri toplandı
- [ ] `sentiment_results.csv` — tüm postlar SA + HS ile etiketlendi
- [ ] `network_edges.csv` — etkileşim ağı oluşturuldu
- [ ] `outputs/figures/` — en az 9 grafik üretildi
- [ ] `analysis.ipynb` — çalışan, yorumlu notebook
- [ ] `outputs/summary_report.md` — bulgular yazılı özet

---

## 13. GELECEKTEKİ GELİŞTİRMELER (ENS492)

Bu bölüm şu an yapılmayacak ama planlanıyor:

1. **TF-IDF → Two-Tower Model:** Actor ve post embedding'lerini birleştiren öğrenilmiş sıralama.
2. **Wide & Deep Ranking:** Etkileşim sinyalleri + semantik benzerlik birleşimi.
3. **LoRA Fine-tuning:** Türk siyasi metinleriyle TurkishBERTweet'i fine-tune et.
4. **Gerçek Zamanlı Firehose:** AT Protocol Jetstream ile anlık veri akışı.
5. **Kullanıcı Arayüzü:** Feed'i gerçekten Bluesky'de sunmak için `feed-generator` server'ı.
6. **Gündem Yakınlık Skoru (Gündem Proximity):** Haftalık haber gündemini otomatik çek, postlarla karşılaştır.

---

## 14. .GITIGNORE

```
.env
venv/
__pycache__/
*.pyc
outputs/all_posts_raw.jsonl
outputs/weekly_search_results.jsonl
TurkishBERTweet/
*.egg-info/
.DS_Store
```

---

*Bu CLAUDE.md, Claude Code agent'ına yöneliktir. Her adımı sırayla, eksiksiz ve bağımsız modüller şeklinde uygula. Bir adım tamamlanmadan diğerine geçme. Hata alırsan stack trace'i oku ve düzelt, sormadan devam et.*