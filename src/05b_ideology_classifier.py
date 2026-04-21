# run in colab in order to use gpu an drive paths
!pip install catboost scikit-learn pandas numpy matplotlib seaborn optuna snowballstemmer stopwords_tr

"""
=============================================================================
AŞAMA 1 (ŞAMPİYON VERSİYON): PREPROCESSING VE META-ÖZELLİKLER
=============================================================================
En yüksek F1 skorunu (%73.7) veren, Stemming (Kök Bulma) İÇERMEYEN, 
siyasi jargonun doğallığını koruyan temel veri hazırlama mimarisi.
- Bağımsız sınıfı elendi.
- Çapraz kopyalar (conflicting labels) temizlendi.
- Kelime sınırı 10 yapıldı.
- Mention ve Hashtag kelimeleri sembolsüz olarak yaşatıldı.
"""

import os
import re
import json
import warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from sklearn.preprocessing import LabelEncoder
from sklearn.feature_selection import mutual_info_classif

warnings.filterwarnings("ignore")
sns.set_theme(style="whitegrid", context="paper", font_scale=1.2)

# ─── 1. ORTAM VE KÜTÜPHANE KURULUMU ───────────────────────────────────────────
try:
    from google.colab import drive
    drive.mount('/content/drive')
    DRIVE_BASE = "/content/drive/MyDrive/outputs"
except ImportError:
    DRIVE_BASE = "outputs"

POSTS_PATH = f"{DRIVE_BASE}/all_posts_raw.jsonl"
PROCESSED_DATA_PATH = f"{DRIVE_BASE}/processed_data_champion.csv" # Şampiyon verisi
FIGURES_DIR = f"{DRIVE_BASE}/figures"
os.makedirs(FIGURES_DIR, exist_ok=True)

try:
    import stopwords_tr as stp
    TR_STOPWORDS = frozenset(stp.stopwords())
except ImportError:
    TR_STOPWORDS = frozenset({"ve", "ile", "bir", "bu", "de", "da", "mi", "mu", "için"})
    print("[WARN] stopwords_tr kütüphanesi yok, basit liste kullanılıyor. (!pip install stopwords_tr)")

# ─── 2. DOĞAL METİN TEMİZLEME (STEMMING YOK) ──────────────────────────────────
_URL_RE     = re.compile(r"http\S+|www\.\S+")
_HTML_RE    = re.compile(r"&[a-z]+;")
_PUNCT_RE   = re.compile(r"[^\w\s]", re.UNICODE)
_REPEAT_RE  = re.compile(r"(.)\1{3,}")
_DIGIT_RE   = re.compile(r"\b\d+\b")
_SPACE_RE   = re.compile(r"\s+")

def clean_text(text: str) -> str:
    """Kelime köklerini bozmadan sadece gürültüyü temizler."""
    t = str(text).lower()
    t = _URL_RE.sub(" ", t)
    t = t.replace("@", " ").replace("#", " ") # Sembolü at, kelime kalsın
    t = _HTML_RE.sub(" ", t)
    t = _PUNCT_RE.sub(" ", t)
    t = _REPEAT_RE.sub(r"\1\1\1", t)
    t = _DIGIT_RE.sub(" ", t)
    
    tokens = [w for w in t.split() if len(w) >= 2 and w not in TR_STOPWORDS]
    return _SPACE_RE.sub(" ", " ".join(tokens))

# ─── 3. ÖZELLİK MÜHENDİSLİĞİ (FEATURE ENGINEERING) ────────────────────────────
def extract_meta_features(df: pd.DataFrame) -> pd.DataFrame:
    """Ham metin üzerinden makaledeki yapısal özellikleri çıkarır."""
    text_raw = df["text"].fillna("")
    text_len = text_raw.str.len().replace(0, 1) 
    
    upper_count = text_raw.str.count(r'[A-ZÇĞİÖŞÜ]')
    punct_count = text_raw.str.count(r'[^\w\s]')
    digit_count = text_raw.str.count(r'\d')

    def _safe(col):
        return pd.to_numeric(df[col], errors="coerce").fillna(0) if col in df.columns else pd.Series(0.0, index=df.index)

    feat_df = pd.DataFrame({
        "log_like":        np.log1p(_safe("like_count")),
        "log_reply":       np.log1p(_safe("reply_count")),
        "log_repost":      np.log1p(_safe("repost_count")),
        "word_count":      df["text_clean"].str.split().str.len().astype(float),
        "hashtag_count":   text_raw.str.count(r"#").astype(float),
        "mention_count":   text_raw.str.count(r"@").astype(float),
        "has_url":         text_raw.str.contains("http", regex=False).astype(float),
        "uppercase_ratio": (upper_count / text_len).astype(float),
        "punct_ratio":     (punct_count / text_len).astype(float),
        "digit_ratio":     (digit_count / text_len).astype(float),
    }, index=df.index)
    
    return feat_df

# ─── 4. ANA İŞLEM AKIŞI (PIPELINE) ────────────────────────────────────────────
print("1. Veri yükleniyor ve filtreleniyor...")
records = []
with open(POSTS_PATH, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line:
            try: records.append(json.loads(line))
            except: pass
df = pd.DataFrame(records)

initial_len = len(df)
# Bağımsız sınıfını çıkar
df = df[df["party"].notna() & (df["party"].str.strip() != "") & (df["party"] != "Bağımsız")].copy()

print("2. Metinler temizleniyor (Doğal kelimeler korunuyor)...")
df["text_clean"] = df["text"].fillna("").apply(clean_text)
# Kelime sınırı 10
df = df[df["text_clean"].str.split().str.len() >= 10].copy()

# Çapraz Parti Kopyalarını Temizle
cross_party = df.groupby('text_clean')['party'].nunique()
conflicting = cross_party[cross_party > 1].index
df = df[~df['text_clean'].isin(conflicting)].copy()

# 200 post altı partileri ele
MIN_PARTY_POSTS = 200
party_counts = df["party"].value_counts()
valid_parties = party_counts[party_counts >= MIN_PARTY_POSTS].index.tolist()
df = df[df["party"].isin(valid_parties)].copy()

print(f"-> Başlangıç: {initial_len} post | Temizlenmiş Final: {len(df)} post")

# ─── 5. ÖZNİTELİK ÇIKARIMI VE BİLGİ KAZANIMI (IG) ANALİZİ ─────────────────────
print("\n3. Meta-özellikler çıkarılıyor ve Bilgi Kazanımı (IG) hesaplanıyor...")
le = LabelEncoder()
df["target"] = le.fit_transform(df["party"])

meta_features = extract_meta_features(df)
df = pd.concat([df, meta_features], axis=1)

mi_scores = mutual_info_classif(meta_features, df["target"], random_state=42)
ig_df = pd.DataFrame({"Feature": meta_features.columns, "IG_Score": mi_scores})
ig_df = ig_df.sort_values("IG_Score", ascending=False)

# ─── 6. AKADEMİK GÖRSELLEŞTİRMELER (EDA) ──────────────────────────────────────
print("\n4. Akademik Grafikler Çiziliyor...")

plt.figure(figsize=(10, 5))
ax = sns.countplot(y="party", data=df, order=df["party"].value_counts().index, palette="viridis")
plt.title("Temizlenmiş Verisetindeki Siyasi Parti Dağılımı")
plt.xlabel("Gönderi Sayısı")
plt.ylabel("")
plt.tight_layout()
plt.savefig(f"{FIGURES_DIR}/01_party_distribution.png", dpi=300)
plt.close()

plt.figure(figsize=(10, 6))
sns.barplot(x="IG_Score", y="Feature", data=ig_df, palette="magma")
plt.title("Meta-Özelliklerin Bilgi Kazanımı (IG) Skorları")
plt.xlabel("Mutual Information Score")
plt.ylabel("Özellikler")
plt.tight_layout()
plt.savefig(f"{FIGURES_DIR}/02_information_gain.png", dpi=300)
plt.close()

plt.figure(figsize=(12, 6))
sns.boxplot(x="word_count", y="party", data=df, palette="crest", showfliers=False)
plt.title("Partilere Göre Temizlenmiş Kelime Sayısı Dağılımı")
plt.xlabel("Kelime Sayısı")
plt.ylabel("")
plt.tight_layout()
plt.savefig(f"{FIGURES_DIR}/03_word_count_distribution.png", dpi=300)
plt.close()

# Şampiyon veriyi özel isimle kaydet
df.to_csv(PROCESSED_DATA_PATH, index=False)
print(f"\n✅ Aşama 1 Tamamlandı! Şampiyon veri '{PROCESSED_DATA_PATH}' konumuna kaydedildi.")


"""
=============================================================================
AŞAMA 2 (ŞAMPİYON VERSİYON): MODEL EĞİTİMİ VE AÇIKLANABİLİRLİK (SHAP)
=============================================================================
Bu hücre, "Doğal" temizlenmiş veri üzerinde şampiyon modelimizi eğitir:
1. LinearSVC: Hızlı baseline olarak TF-IDF ile çalışır.
2. CatBoost: Bize %73.7 skorunu getiren, kendi varsayılan metin işleme 
   motoruyla çalışan en kararlı ayarlar (depth=7, iter=600) ile eğitilir.
3. Karışıklık Matrisi (Confusion Matrix) ve Özellik Önem (Feature Importance) grafikleri çizilir.
"""

import os
import warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
warnings.filterwarnings("ignore")
sns.set_theme(style="whitegrid", context="paper", font_scale=1.1)

from scipy.sparse import hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.feature_selection import SelectKBest, chi2
from sklearn.svm import LinearSVC
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.metrics import classification_report, confusion_matrix, f1_score, matthews_corrcoef
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder

try:
    from catboost import CatBoostClassifier, Pool as CatPool
    HAS_CATBOOST = True
except ImportError:
    HAS_CATBOOST = False
    print("[WARN] CatBoost bulunamadı! (!pip install catboost)")

# ─── AYARLAR ──────────────────────────────────────────────────────────────────
try:
    from google.colab import drive
    DRIVE_BASE = "/content/drive/MyDrive/outputs"
except ImportError:
    DRIVE_BASE = "outputs"

PROCESSED_DATA_PATH = f"{DRIVE_BASE}/processed_data_champion.csv" # Şampiyon veri!
FIGURES_DIR = f"{DRIVE_BASE}/figures"
os.makedirs(FIGURES_DIR, exist_ok=True)

N_SPLITS = 5
RANDOM_STATE = 42

# ─── 1. VERİYİ YÜKLEME VE HAZIRLAMA ───────────────────────────────────────────
print("1. Şampiyon veri yükleniyor...")
df = pd.read_csv(PROCESSED_DATA_PATH)
df["text_clean"] = df["text_clean"].fillna("")

le = LabelEncoder()
y = le.fit_transform(df["party"])
label_names = list(le.classes_)

meta_cols = [
    "log_like", "log_reply", "log_repost", "word_count", "hashtag_count", 
    "mention_count", "has_url", "uppercase_ratio", "punct_ratio", "digit_ratio"
]
feat_df = df[["text_clean"] + meta_cols].copy()

# Sınıf ağırlıklarını manuel dengeliyoruz (Azınlık partileri ezilmesin)
unique, counts = np.unique(y, return_counts=True)
cw = {int(c): float(len(y) / (len(unique) * cnt)) for c, cnt in zip(unique, counts)}
cv = StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_STATE)

# ─── 2. LİNEAR SVC (BASELINE) EĞİTİMİ ─────────────────────────────────────────
print("\n2. LinearSVC Baseline için TF-IDF özellikleri çıkarılıyor...")
word_vec = TfidfVectorizer(ngram_range=(1, 3), max_features=35_000, min_df=2, sublinear_tf=True)
char_vec = TfidfVectorizer(ngram_range=(2, 5), max_features=20_000, min_df=2, sublinear_tf=True, analyzer="char_wb")
X_tfidf = hstack([word_vec.fit_transform(df["text_clean"]), char_vec.fit_transform(df["text_clean"])], format="csr")

pipe = Pipeline([
    ("select", SelectKBest(chi2, k=min(18_000, X_tfidf.shape[1]))),
    ("clf", LinearSVC(C=1.5, max_iter=5000, class_weight="balanced", dual=True))
])

print(f"   Running {N_SPLITS}-fold CV — LinearSVC …")
svc_pred = cross_val_predict(pipe, X_tfidf, y, cv=cv, n_jobs=-1)
svc_f1 = f1_score(y, svc_pred, average="macro", zero_division=0)
print(f"   -> LinearSVC Macro-F1: {svc_f1:.4f}")

# ─── 3. CATBOOST ŞAMPİYON EĞİTİMİ ─────────────────────────────────────────────
all_preds = {"LinearSVC": svc_pred}
all_results = {"LinearSVC": {"macro_f1": svc_f1, "mcc": matthews_corrcoef(y, svc_pred)}}

if HAS_CATBOOST:
    print(f"\n3. Running {N_SPLITS}-fold CV — CatBoost (Şampiyon Ayarlar) …")
    
    cb_pred = np.zeros(len(y), dtype=int)
    print("   CatBoost Fold: ", end="", flush=True)
    for fold_i, (tr_idx, va_idx) in enumerate(cv.split(feat_df, y)):
        print(f"{fold_i + 1}", end=" ", flush=True)
        train_pool = CatPool(data=feat_df.iloc[tr_idx].reset_index(drop=True), label=y[tr_idx], text_features=["text_clean"])
        val_pool   = CatPool(data=feat_df.iloc[va_idx].reset_index(drop=True), label=y[va_idx], text_features=["text_clean"])

        # En stabil ve yüksek skoru veren parametreler
        model = CatBoostClassifier(
            iterations=600, 
            learning_rate=0.08, 
            depth=7, 
            loss_function="MultiClass", 
            class_weights=cw, 
            random_seed=RANDOM_STATE, 
            task_type="GPU", 
            verbose=0
        )
        model.fit(train_pool, eval_set=val_pool, use_best_model=False)
        cb_pred[va_idx] = model.predict(val_pool).flatten().astype(int)

    cb_f1 = f1_score(y, cb_pred, average="macro", zero_division=0)
    all_results["CatBoost"] = {"macro_f1": cb_f1, "mcc": matthews_corrcoef(y, cb_pred)}
    all_preds["CatBoost"] = cb_pred
    print(f"\n   -> CatBoost Macro-F1: {cb_f1:.4f}")

# ─── 4. GÖRSELLEŞTİRME (CONFUSION MATRIX & FEATURE IMPORTANCE) ────────────────
print("\n4. Akademik Grafikler (Confusion Matrix & Feature Importance) Oluşturuluyor...")

def plot_cm(y_true, y_pred, model_name, filename):
    cm = confusion_matrix(y_true, y_pred, normalize="true")
    short_names = [name.split()[0] if len(name) > 12 else name for name in label_names]
    plt.figure(figsize=(9, 7))
    sns.heatmap(cm, annot=True, fmt=".2f", cmap="Blues", xticklabels=short_names, yticklabels=short_names)
    plt.title(f"Confusion Matrix — {model_name}", pad=15, fontsize=14)
    plt.ylabel("Gerçek Parti", fontsize=12)
    plt.xlabel("Tahmin Edilen Parti", fontsize=12)
    plt.xticks(rotation=45, ha="right", fontsize=11)
    plt.yticks(rotation=0, fontsize=11)
    plt.tight_layout()
    plt.savefig(f"{FIGURES_DIR}/{filename}", dpi=300)
    plt.close()

plot_cm(y, all_preds["LinearSVC"], "LinearSVC (Baseline)", "04_cm_linearsvc.png")
if HAS_CATBOOST:
    plot_cm(y, all_preds["CatBoost"], "CatBoost (Şampiyon Model)", "05_cm_catboost.png")

    print("5. Tüm veri ile CatBoost Feature Importance (Özellik Önemi) Hesaplanıyor...")
    full_pool = CatPool(data=feat_df, label=y, text_features=["text_clean"])
    final_model = CatBoostClassifier(iterations=600, learning_rate=0.08, depth=7, loss_function="MultiClass", 
                                     class_weights=cw, random_seed=RANDOM_STATE, task_type="GPU", verbose=0)
    final_model.fit(full_pool)
    
    importances = final_model.get_feature_importance(full_pool)
    feat_names = final_model.feature_names_
    
    # En önemli 15 özelliği sırala
    top_indices = np.argsort(importances)[-15:]
    top_feats = [feat_names[i] for i in top_indices]
    top_vals = [importances[i] for i in top_indices]

    plt.figure(figsize=(10, 6))
    sns.barplot(x=top_vals, y=top_feats, palette="rocket")
    plt.title("CatBoost Feature Importance (Karara En Çok Etki Eden Özellikler)", fontsize=14)
    plt.xlabel("Etki Değeri", fontsize=12)
    plt.ylabel("Özellikler", fontsize=12)
    plt.tight_layout()
    plt.savefig(f"{FIGURES_DIR}/06_catboost_feature_importance.png", dpi=300)
    plt.close()

print("\n" + "="*50)
print(f"🔥 FINAL ÖZET RAPORU 🔥")
print("="*50)
best_model = max(all_results, key=lambda k: all_results[k]["macro_f1"])
for model, res in sorted(all_results.items(), key=lambda x: x[1]['macro_f1'], reverse=True):
    print(f" {model:<15} | Macro-F1: {res['macro_f1']:.4f} | MCC: {res['mcc']:.4f} {'(ŞAMPİYON)' if model==best_model else ''}")

if HAS_CATBOOST:
    print("\nCatBoost Detaylı Sınıflandırma Raporu:")
    print(classification_report(y, all_preds["CatBoost"], target_names=label_names))

print(f"\n✅ Tüm işlemler başarıyla bitti! Grafikler (Confusion Matrix ve Feature Importance) '{FIGURES_DIR}' klasörüne kaydedildi.")