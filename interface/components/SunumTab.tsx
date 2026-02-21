"use client";

import { useEffect, useState, useCallback } from "react";

/* ─── Lightbox ─────────────────────────────────────────────────── */
function Lightbox({ src, onClose }: { src: string; onClose: () => void }) {
  useEffect(() => {
    const fn = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", fn);
    return () => window.removeEventListener("keydown", fn);
  }, [onClose]);
  return (
    <div className="lightbox" onClick={onClose}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={src} alt="Enlarged figure" onClick={(e) => e.stopPropagation()} />
    </div>
  );
}

/* ─── Figure panel ─────────────────────────────────────────────── */
function Fig({ file, caption }: { file: string; caption: string }) {
  const [lb, setLb] = useState(false);
  const src = `/api/figures/${file}`;
  return (
    <>
      <div className="fw">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={src}
          alt={file}
          onClick={() => setLb(true)}
          onError={(e) => {
            const el = e.currentTarget.parentElement!;
            el.innerHTML = `<div style="display:flex;flex-direction:column;align-items:center;gap:8px;color:var(--muted)"><code class="i">${file}</code><span style="font-size:13px">Görsel yüklenemedi</span></div>`;
          }}
        />
      </div>
      <div className="fcap">{caption}</div>
      {lb && <Lightbox src={src} onClose={() => setLb(false)} />}
    </>
  );
}

/* ─── Section wrapper ──────────────────────────────────────────── */
function Section({ id, left, right }: { id: string; left: React.ReactNode; right: React.ReactNode }) {
  return (
    <section className="pg" id={id}>
      <div className="tc">
        <div className="fp-l">{left}</div>
        <div className="fp-r">{right}</div>
      </div>
    </section>
  );
}

function Find({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="find">
      <div className="ftit">{title}</div>
      <div className="fbdy">{children}</div>
    </div>
  );
}

function Meth({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="meth">
      <div className="mtag">{title}</div>
      <div className="mbdy">{children}</div>
    </div>
  );
}

/* ─── Nav links ────────────────────────────────────────────────── */
const NAV_LINKS = [
  { href: "#s-cover", label: "Giriş" },
  { href: "#s-pipe", label: "Yöntem" },
  { href: "#s1", label: "Aktivite" },
  { href: "#s2", label: "Hacim" },
  { href: "#s3", label: "İstatistik" },
  { href: "#s4", label: "LDA" },
  { href: "#s5", label: "Duygu" },
  { href: "#s6", label: "Nefret" },
  { href: "#s7", label: "Çapraz" },
  { href: "#s8", label: "Efor" },
  { href: "#s9", label: "Power User" },
  { href: "#s10", label: "Kelime Bulutu" },
  { href: "#s11", label: "İdeoloji" },
];

/* ─── Main Component ───────────────────────────────────────────── */
export default function SunumTab() {
  const [progress, setProgress] = useState(0);

  const updateProgress = useCallback(() => {
    const s = window.scrollY;
    const m = document.documentElement.scrollHeight - window.innerHeight;
    setProgress(m > 0 ? (s / m) * 100 : 0);
  }, []);

  useEffect(() => {
    window.addEventListener("scroll", updateProgress);
    return () => window.removeEventListener("scroll", updateProgress);
  }, [updateProgress]);

  return (
    <>
      {/* Scroll progress bar */}
      <div id="prog" style={{ width: `${progress}%` }} />

      {/* Sub-navigation (scrollable) */}
      <div style={{
        position: "sticky", top: 48, zIndex: 90,
        background: "var(--surface)", borderBottom: "1px solid var(--border)",
        display: "flex", overflowX: "auto", padding: "0 16px",
        scrollbarWidth: "none",
      }}>
        {NAV_LINKS.map((l) => (
          <a
            key={l.href}
            href={l.href}
            style={{
              fontFamily: "var(--mono)", fontSize: 12, fontWeight: 500,
              color: "var(--muted)", textDecoration: "none", padding: "0 14px",
              height: 36, display: "flex", alignItems: "center", whiteSpace: "nowrap",
              borderBottom: "2px solid transparent", letterSpacing: "0.05em",
              transition: "color 0.12s",
            }}
            onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.color = "var(--text)"; }}
            onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.color = "var(--muted)"; }}
          >
            {l.label}
          </a>
        ))}
      </div>

      {/* ─── Cover ────────────────────────────────────────────────── */}
      <section className="pg" id="s-cover">
        <div style={{ display: "flex", flexDirection: "column", justifyContent: "center", padding: "120px 80px 80px", minHeight: "100vh", background: "var(--surface)" }}>
          <div className="c-eye">Bitirme Projesi &mdash; Şubat 2026</div>
          <h1 className="c-h1">BlueSky Türkiye<br /><em>Siyasi Ekosistemi</em></h1>
          <p className="c-desc">
            Türk siyasi aktörlerinin BlueSky platformundaki söylemsel örüntülerinin, doğal dil işleme ve makine öğrenmesi yöntemleriyle çok boyutlu analizi: ağ yapılanması, gönderi hacmi dinamikleri, duygu kutuplaşması ve ideolojik sınıflandırma.
          </p>
          <div className="c-rule" />
          <div>
            <div className="c-item">Platform &mdash; <span>AT Protocol / app.bsky.social</span></div>
            <div className="c-item">NLP Modeli &mdash; <span>VRLLab / TurkishBERTweet (LoRA adaptasyonu)</span></div>
            <div className="c-item">Konu Modellemesi &mdash; <span>LDA + Jensen-Shannon Divergence</span></div>
            <div className="c-item">İstatistiksel Testler &mdash; <span>Kruskal-Wallis H · Mann-Whitney U · FDR-BH · Wilson CI · Ki-kare</span></div>
            <div className="c-item">Sınıflandırma &mdash; <span>Linear SVM · Logistic Regression · Random Forest · Complement NB</span></div>
          </div>
        </div>
      </section>

      {/* ─── Pipeline ─────────────────────────────────────────────── */}
      <section className="pg" id="s-pipe">
        <div style={{ padding: "72px 80px 64px" }}>
          <div className="slbl">Genel Bakış</div>
          <div className="stit">Araştırma Süreci (Pipeline) ve Veri Seti</div>
          <p style={{ fontSize: 15, color: "var(--muted)", maxWidth: 800, lineHeight: 1.7, marginTop: 12 }}>
            Çalışma beş temel aşama olarak tasarlanmıştır. Her aşamanın çıktısı bir sonrakinin girdisini oluşturmaktadır.
          </p>
          <div className="pipe">
            {[
              { n: "01", t: "Hesap Doğrulama", b: <>AT Protocol <code className="i">app.bsky.actor.getProfile</code> kullanılarak siyasi hesaplar doğrulandı. DID ve displayName eşleştirmesi yapıldı. 429 rate-limit durumları exponential backoff ile yönetildi.</> },
              { n: "02", t: "Gönderi Toplama", b: <>İmleç tabanlı sayfalama ile doğrulanmış hesapların tüm gönderi geçmişi <code className="i">getAuthorFeed</code> üzerinden çekildi. Yanıt ve alıntı bağlantıları ağ analizi için ayrıştırıldı.</> },
              { n: "03", t: "NLP Analizi", b: "TF-IDF ile anahtar kelime çıkarımı, LDA konu modellemesi (gensim, C_V tutarlılığı) uygulandı. TurkishBERTweet-LoRA ile duygu ve nefret söylemi etiketlemesi yapıldı." },
              { n: "04", t: "İstatistiksel Test", b: "Kruskal-Wallis H, Mann-Whitney U + FDR-BH düzeltmesi, Ki-kare + Cramer's V, Wilson %95 CI ve Pearson r korelasyon testleri uygulandı." },
              { n: "05", t: "İdeoloji Sınıflandırma", b: "Kelime ve Karakter TF-IDF, SelectKBest (ki-kare), 5-katlı Stratified CV. Macro-F1 ve MCC metrikleriyle değerlendirme. RandomOverSampler ile veri dengesi." },
            ].map((pc) => (
              <div key={pc.n} className="pc">
                <span className="pn">{pc.n}</span>
                <div className="pt">{pc.t}</div>
                <div className="pb">{pc.b}</div>
              </div>
            ))}
          </div>
          <table className="dt">
            <thead>
              <tr><th>Dosya Adı</th><th>Kaynak ve Yöntem</th><th>Kapsam</th></tr>
            </thead>
            <tbody>
              <tr><td>verified_accounts.csv</td><td>AT Protocol API doğrulaması (manuel kürasyon destekli)</td><td>400+ doğrulanmış hesap, 7 siyasi parti</td></tr>
              <tr><td>all_posts_raw.jsonl</td><td>getAuthorFeed — İmleç tabanlı tam sayfalama</td><td>10.000+ gönderi, yanıt/alıntı ağ verisi</td></tr>
              <tr><td>weekly_search_results.jsonl</td><td>searchPosts — 50 anahtar kelime, 7 günlük periyot</td><td>Kelime başına maks. 500 gönderi</td></tr>
              <tr><td>sentiment_results.csv</td><td>TurkishBERTweet-LoRA-SA + LoRA-HS (Batch Inference)</td><td>3 duygu + 2 nefret sınıfı, softmax olasılıkları</td></tr>
              <tr><td>network_edges / node_metrics.csv</td><td>DID-URI çözümleme, PageRank (α=0.85), Louvain</td><td>Ağırlıklı ve yönlü ağ grafiği</td></tr>
            </tbody>
          </table>
        </div>
      </section>

      {/* ─── S1 Party Activity ────────────────────────────────────── */}
      <Section id="s1"
        left={<>
          <div className="slbl">Bölüm 01 &mdash; Platform Adaptasyonu</div>
          <div className="stit">Parti Bazlı Aktivite ve Hesap Dağılımı</div>
          <div className="ssub">Doğrulanmış hesap sayısı ve toplam gönderi hacminin partiler arası karşılaştırmalı analizi</div>
          <Fig file="G1_party_post_counts.png" caption="Sol Panel: Toplam gönderi sayısı · Sağ Panel: Doğrulanmış hesap sayısı. Küçük partiler 'Diğer' kategorisinde birleştirilmiştir." />
        </>}
        right={<>
          <div className="slbl">Öne Çıkan Bulgular</div>
          <div className="finds">
            <Find title="Muhalefetin Platform Dominansı">
              CHP, <strong><span className="n">5.169 gönderi</span></strong> ve <strong><span className="n">166 doğrulanmış hesap</span></strong> ile platformda açık ara en aktif aktördür. Early adopter kitlesinin ağırlıklı olarak muhalif siyasilerden oluştuğu görülmektedir.
            </Find>
            <Find title="İktidar Bloğunun Pasif Varlığı">
              AKP, <strong><span className="n">84 hesap</span></strong> ile bulunma oranında 2. sırada olmasına rağmen içerik üretiminde (<strong><span className="n">1.022 gönderi</span></strong>) 4. sıraya gerilemektedir.
            </Find>
            <Find title="Bağımsızların Orantısız Eforu">
              Bağımsız siyasetçiler yalnızca <strong><span className="n">14 profile</span></strong> sahip olmalarına karşın <strong><span className="n">1.885 gönderi</span></strong> üretmiştir. Hesap başına <strong><span className="n">~134 gönderi</span></strong> ile en yüksek bireysel yoğunluk.
            </Find>
          </div>
          <Meth title="Veri Toplama Yöntemi">
            Hesap doğrulaması <code className="i">app.bsky.actor.getProfile</code> üzerinden yapılmış; HTTP 429 hataları 10 saniyelik bekleme ve maks. 3 retry ile aşılmıştır. Gönderi sayıları <code className="i">all_posts_raw.jsonl</code> veri setinden derlenmiştir.
          </Meth>
        </>}
      />

      {/* ─── S2 Weekly Volume ─────────────────────────────────────── */}
      <Section id="s2"
        left={<>
          <div className="slbl">Bölüm 02 &mdash; Zamansal Analiz</div>
          <div className="stit">Gönderi Hacminin Zamana Göre Evrimi</div>
          <div className="ssub">3 günlük hareketli ortalama ile oluşturulmuş günlük gönderi serisi</div>
          <Fig file="G2_weekly_post_volume.png" caption="Eğriler: 3-günlük hareketli ortalamalı günlük gönderi sayısı. Gölgeli Alanlar: Görsel okunabilirlik için (alpha=0.06)." />
        </>}
        right={<>
          <div className="slbl">Öne Çıkan Bulgular</div>
          <div className="finds">
            <Find title="Erken Dönem Durgunluğu">
              2023 ortasından 2024 sonbaharına kadar organik siyasi tartışma ortamı oluşmamıştır. Aktivite yok denecek kadar az seviyede kalmıştır.
            </Find>
            <Find title="Görünürlük Kırılması — Eylül 2024">
              Eylül 2024 itibarıyla düzenli veri akışı başlamıştır. X (Twitter) platformundaki olası yasal kısıtlamalar karşısında siyasetçilerin alternatif platform arayışının yansıması olarak yorumlanabilir.
            </Find>
            <Find title="Mayıs 2025 Zirvesi">
              Günlük ortalama <strong><span className="n">~80 gönderi/gün</span></strong> seviyesine ulaşan bu zirve, CHP öncülüğünde gerçekleşmiş ve AKP kısa süreli yüksek reaksiyon vermiştir.
            </Find>
          </div>
          <Meth title="Zamansal Analiz Metodolojisi">
            <strong>Hareketli Ortalama:</strong> Kısa vadeli gürültüyü bastırmak için 3-günlük pencere <code className="i">rolling(3).mean()</code>.<br /><br />
            <strong>Durbin-Watson Testi:</strong> Sosyal kaskad etkisini ölçmek için otokorelasyon kontrolü. DW &lt; 1.5 pozitif otokorelasyona işaret eder.<br /><br />
            <strong>Zirve Tespiti:</strong> Her partinin aktivite zirvesi algoritmik olarak belirlenmiştir.
          </Meth>
        </>}
      />

      {/* ─── S3 Statistical Tests ─────────────────────────────────── */}
      <Section id="s3"
        left={<>
          <div className="slbl">Bölüm 03 &mdash; İstatistiksel Doğrulama</div>
          <div className="stit">İkili Duygu (Sentiment) Farklılıkları</div>
          <div className="ssub">FDR-BH düzeltmeli Mann-Whitney U testleri ve Rank-Biserial Korelasyon etki büyüklüğü</div>
          <Fig file="G_statistical_forest_plot.png" caption="Yatay Çubuklar: FDR-BH sonrası anlamlı (p_adj < 0.05) parti çiftleri arasındaki etki büyüklüğü (r). Negatif r: Solda yer alan partinin daha negatif dil kullandığını gösterir." />
        </>}
        right={<>
          <div className="slbl">Öne Çıkan Bulgular</div>
          <div className="finds">
            <Find title="Bağımsızların Kronik Negatifliği">
              Bağımsız aktörler; AKP, MHP ve CHP ile karşılaştırıldığında sürekli ve en belirgin şekilde daha negatif dil kullanmaktadır (<strong><span className="nr">r ≈ −0.30</span></strong>). Kurumsal yapıya bağlı olmayan bu hesaplar, radikal eleştirinin merkezindedir.
            </Find>
            <Find title="İktidar — Muhalefet Tonu Farkı">
              CHP, genel söylem bazında AKP&apos;ye kıyasla anlamlı derecede daha negatif tona sahiptir (<strong><span className="nr">r ≈ −0.20</span></strong>). Yeni Yol Partisi genel ekosistemdeki en pozitif/nötr dile sahip aktördür.
            </Find>
          </div>
          <Meth title="Üç Aşamalı İstatistiksel Protokol">
            <strong>1. Kruskal-Wallis H:</strong> Parametresiz global test. Gruplar arasında anlamlı fark var mı?<br /><br />
            <strong>2. Mann-Whitney U:</strong> İkili karşılaştırma. P-değerleri FDR-BH ile düzeltilmiştir.<br /><br />
            <strong>3. Rank-Biserial Korelasyon:</strong> Etki büyüklüğü:
            <span className="fm">r = 1 − (2U) / (n₁ × n₂)</span>
            |r| ≥ 0.3 orta düzeyde, belirgin bir farkı temsil eder.
          </Meth>
        </>}
      />

      {/* ─── S4 LDA ───────────────────────────────────────────────── */}
      <Section id="s4"
        left={<>
          <div className="slbl">Bölüm 04 &mdash; Konu Modellemesi</div>
          <div className="stit">LDA Konu Benzerliği (JSD Matrisi)</div>
          <div className="ssub">Parti külliyatlarındaki konu dağılımları arasındaki mesafe ve hiyerarşik kümeleme</div>
          <Fig file="G_LDA_topic_similarity.png" caption="Isı Haritası: Jensen-Shannon Divergence (0 = Tamamen aynı, 1 = Tamamen zıt). Dendrogram: Ward bağlantı yöntemiyle söylemsel kümeleme." />
        </>}
        right={<>
          <div className="slbl">Öne Çıkan Bulgular</div>
          <div className="finds">
            <Find title="Sağ Blokta Yüksek Söylemsel Yakınlık">
              AKP ile İYİ Parti arasındaki söylemsel mesafe (<strong><span className="n">JSD: 0.352</span></strong>) dikkat çekici seviyede düşüktür. Beka, ekonomi ve güvenlik gibi temel kavramlarda söylemleri ortaklaşmaktadır.
            </Find>
            <Find title="CHP ve DEM Parti Arasındaki Kopukluk">
              Yüksek JSD değeri (<strong><span className="nr">0.532</span></strong>), bu iki partinin aynı platformda tamamen farklı siyasi ajandaları konuştuğunu kanıtlamaktadır.
            </Find>
            <Find title="İki Ana Söylemsel Küme">
              Dendrogram iki blok oluşturmuştur: <strong>(1)</strong> AKP, İYİ Parti, Yeni Yol ve <strong>(2)</strong> CHP, DEM Parti.
            </Find>
          </div>
          <Meth title="LDA ve JSD Yöntemi">
            <strong>LDA:</strong> Optimum konu sayısı (k), C_V tutarlılık skoru maksimize edilerek bulunmuştur.<br /><br />
            <strong>Jensen-Shannon Divergence:</strong> Simetrik, 0-1 arasında mesafe ölçütü:
            <span className="fm">JSD(P‖Q) = (1/2)KL(P‖M) + (1/2)KL(Q‖M)</span>
            <strong>Kümeleme:</strong> Ward metodu ile varyans minimize edilerek hiyerarşik kümeleme yapılmıştır.
          </Meth>
        </>}
      />

      {/* ─── S5 Sentiment ─────────────────────────────────────────── */}
      <Section id="s5"
        left={<>
          <div className="slbl">Bölüm 05 &mdash; Duygu Analizi (Sentiment)</div>
          <div className="stit">Parti Bazlı Duygu Dağılımı</div>
          <div className="ssub">Derin öğrenme modelinin ürettiği Negatif / Nötr / Pozitif içerik oranları</div>
          <Fig file="G3_sentiment_heatmap.png" caption="Her Hücre: Partinin toplam içerikleri içinde ilgili duygunun yüzdelik oranı. Renk Skalası: Kırmızı (Düşük) → Yeşil (Yüksek)." />
        </>}
        right={<>
          <div className="slbl">Öne Çıkan Bulgular</div>
          <div className="finds">
            <Find title="Sistemik Nötr Ton Baskınlığı">
              Tüm partilerde &quot;Nötr&quot; içerikler ağırlıktadır (<strong><span className="n">%45–%88 arası</span></strong>). Siyasi aktörler platformu çoğunlukla program duyuruları ve resmi mesajlar için kullanmaktadır.
            </Find>
            <Find title="DEM Parti'nin Steril Dili">
              DEM Parti <strong><span className="n">%88</span></strong> nötr gönderi üretmektedir. Olası hukuki veya politik baskılar nedeniyle yüksek otokontrol mekanizmasıyla yönetilmektedir.
            </Find>
            <Find title="MHP'nin Sert Söylemi">
              MHP hesapları, sistemdeki en yüksek negatif duygu oranına sahiptir (<strong><span className="nr">%31</span></strong>). Güvenlikçi politikalar ve muhalefeti doğrudan hedef alan retoriğin sonucudur.
            </Find>
          </div>
          <Meth title="Model: TurkishBERTweet-LoRA-SA">
            <strong>Mimari:</strong> Türkçe Twitter verisi üzerinde eğitilmiş BERTweet tabanlı dil modeli. LoRA ile ince ayar yapılarak parametre verimliliği sağlanmıştır.<br /><br />
            <strong>Çıkarım:</strong> 3 sınıf (negatif, nötr, pozitif) için softmax olasılıkları → argmax nihai etiket.<br /><br />
            <strong>Ön İşleme:</strong> URL&apos;ler, mention&apos;lar ve özel karakterler temizlenerek normalize edilmiştir.
          </Meth>
        </>}
      />

      {/* ─── S6 Hate Speech ───────────────────────────────────────── */}
      <Section id="s6"
        left={<>
          <div className="slbl">Bölüm 06 &mdash; Toksik Dil Analizi</div>
          <div className="stit">Nefret Söylemi Oranları ve Güven Aralıkları</div>
          <div className="ssub">Partiler bazında nefret söylemi yaygınlığı ve %95 Wilson CI</div>
          <Fig file="G4_hate_speech_rate.png" caption="Nokta: Ham nefret söylemi oranı. Yatay Çizgi: %95 Wilson Güven Aralığı. (n) = örneklem büyüklüğü." />
        </>}
        right={<>
          <div className="slbl">Öne Çıkan Bulgular</div>
          <div className="finds">
            <Find title="MHP Açık Ara Zirvede">
              MHP hesapları yaklaşık <strong><span className="nr">%5.5</span></strong> ile açık ara en yüksek nefret söylemi oranına sahiptir. Alt güven aralığı bile diğer partilerin üst sınırından yüksektir.
            </Find>
            <Find title="Hiyerarşik Azalma Serisi">
              AKP (<strong><span className="nr">~%1.5</span></strong>), CHP (<strong><span className="n">~%0.4</span></strong>), DEM Parti (<strong><span className="n">~%0.1</span></strong>). DEM Parti&apos;nin steril yapısı burada da doğrulanmaktadır.
            </Find>
          </div>
          <Meth title="Wilson Güven Aralığı Yöntemi">
            Standart Wald formülü küçük örneklemlerde yanıltıcı sonuçlar verir. <strong>Wilson Score Interval</strong> kullanılmıştır:
            <span className="fm">CI = (p + z²/2n ± z√(p(1−p)/n + z²/4n²)) / (1 + z²/n)</span>
            <strong>Ki-Kare</strong> ile bağımsızlık testi yapılmış, etki Cramer&apos;s V ile raporlanmıştır.
          </Meth>
        </>}
      />

      {/* ─── S7 Cross-party Sentiment ─────────────────────────────── */}
      <Section id="s7"
        left={<>
          <div className="slbl">Bölüm 07 &mdash; Söylemsel Hedefleme</div>
          <div className="stit">Partiler Arası Çapraz Duygu Matrisi</div>
          <div className="ssub">Konuşan partinin (satır), bahsettiği partiye (sütun) yönelik ortalama pozitiflik skoru</div>
          <Fig file="G5_cross_party_sentiment.png" caption="0.0 (Koyu Kırmızı) = Tamamen Negatif, 0.5 = Nötr, 1.0 (Yeşil) = Tamamen Pozitif. Hedef tespiti: PARTY_KEYWORDS anahtar kelime eşleştirme." />
        </>}
        right={<>
          <div className="slbl">Öne Çıkan Bulgular</div>
          <div className="finds">
            <Find title="Matristeki En Keskin Düşmanlık">
              MHP hesapları, CHP&apos;den bahsederken neredeyse tamamen negatif (<strong><span className="nr">0.08 Skor</span></strong>) dil kullanmaktadır.
            </Find>
            <Find title="Asimetrik İktidar-Muhalefet İlişkisi">
              CHP&apos;nin AKP hakkındaki içerikleri (<strong><span className="nr">0.24</span></strong>), AKP&apos;nin CHP hakkındakilerinden (<strong><span className="nr">0.15</span></strong>) nispeten daha az negatiftir.
            </Find>
            <Find title="DEM Parti: Ortak Hedef">
              Hemen hemen tüm partiler, DEM Parti&apos;den bahsederken yoğun şekilde negatif dil kullanmaktadır.
            </Find>
          </div>
          <Meth title="Hedef Tespiti (Mention) Yöntemi">
            Her gönderi metni önceden tanımlanmış <code className="i">PARTY_KEYWORDS</code> sözlüğü ile taranmıştır. Parti ismi geçen gönderiler filtrelenmiş, &quot;Pozitif&quot; sınıfı softmax olasılıkları toplanıp ortalaması alınmıştır.<br /><br />
            <strong>Araştırma Sınırları:</strong> Dolaylı göndermeler bu matrise dahil edilememiştir.
          </Meth>
        </>}
      />

      {/* ─── S8 Effort ────────────────────────────────────────────── */}
      <Section id="s8"
        left={<>
          <div className="slbl">Bölüm 08 &mdash; Efor Analizi</div>
          <div className="stit">Hesap Başına Gönderi Yoğunluğu</div>
          <div className="ssub">Toplam gönderi hacmi ile bireysel çabanın kıyaslanması</div>
          <Fig file="G7_party_activity.png" caption="Sağ Panel: Gönderi Yoğunluğu = Toplam Gönderi / Benzersiz Hesap. Yüksek yoğunluk = grubun platformu aktif kullandığını gösterir." />
        </>}
        right={<>
          <div className="slbl">Öne Çıkan Bulgular</div>
          <div className="finds">
            <Find title="Bağımsızlar ve İYİ Parti Dinamizmi">
              Bağımsızlar (<strong><span className="n">134.6 gönderi/hesap</span></strong>) ve İYİ Parti (<strong><span className="n">121.8 gönderi/hesap</span></strong>) en yoğun mesaiyi harcayan gruplardır.
            </Find>
            <Find title="CHP'nin Geniş ama Sığ Ağı">
              5.169 gönderi ile zirvede olmasına rağmen bireysel efor oranı (<strong><span className="n">31.1 gönderi/hesap</span></strong>) oldukça düşmektedir.
            </Find>
            <Find title="AKP: Kalabalık ancak Üretimsiz">
              Geniş hesap havuzuna rağmen hesap başına düşen oran (<strong><span className="nr">12.2 gönderi</span></strong>) ile platformun en pasif kitlesidir.
            </Find>
          </div>
          <Meth title="Gönderi Yoğunluğu Metriği">
            Farklı büyüklükteki parti gruplarını adil karşılaştırabilmek için mutlak hacim, gruptaki kişi sayısına bölünerek normalize edilmiştir. Yüksek yoğunluk, grubun üyelerinin platformu aktif kullandığını kanıtlar.
          </Meth>
        </>}
      />

      {/* ─── S9 Power Users ───────────────────────────────────────── */}
      <Section id="s9"
        left={<>
          <div className="slbl">Bölüm 09 &mdash; Bireysel Efor (Power Users)</div>
          <div className="stit">Platformu Domine Eden Süper Kullanıcılar</div>
          <div className="ssub">Tüm ekosistemde en yüksek gönderi hacmine sahip ilk 20 aktör</div>
          <Fig file="G7_top_active_accounts.png" caption="Çubuklar: Toplam gönderi sayısı. Renkler: Siyasi partiyi temsil etmektedir." />
        </>}
        right={<>
          <div className="slbl">Öne Çıkan Bulgular</div>
          <div className="finds">
            <Find title="Sistemin Motoru Bireylerdir">
              DEM Parti milletvekili Ömer Faruk Gergerlioğlu, <strong><span className="n">1.555 gönderi</span></strong> ile platformun açık ara en üretken ismidir. DEM Parti&apos;nin tüm BlueSky varlığının <strong><span className="nr">%70&apos;inden fazlası</span></strong> tek başına bu hesaptan çıkmaktadır.
            </Find>
            <Find title="CHP'yi Sürükleyen İsimler">
              Müzeyyen Şevkin (<strong><span className="n">1.259</span></strong>) ve Suat Özçağdaş (<strong><span className="n">1.233</span></strong>), yüzlerce hesaba sahip muhalefet bloğunun içerik üretimini tek başlarına yukarı çekmektedir.
            </Find>
            <Find title="Bağımsız Gazetecilik Ağı">
              Ruşen Çakır (<strong><span className="n">764</span></strong>) gibi gazetecilerin varlığı, platformun &quot;haber bülteni dağıtım mecrası&quot; olarak konumlandığını göstermektedir.
            </Find>
          </div>
          <Meth title="Güç Yasası (Power Law) Dağılımı">
            Sosyal ağlardaki içerik üretimi <strong>uzun kuyruklu (long-tail)</strong> bir dağılım sergiler. Kullanıcıların çok küçük bir yüzdesi platformdaki içeriğin ezici çoğunluğunu üretir.
          </Meth>
        </>}
      />

      {/* ─── S10 Word Clouds ──────────────────────────────────────── */}
      <Section id="s10"
        left={<>
          <div className="slbl">Bölüm 10 &mdash; Söylemsel Temalar</div>
          <div className="stit">Parti Söylemlerinin Kelime Bulutları</div>
          <div className="ssub">Her partinin dilindeki en ayırt edici (TF-IDF skorlu) kelimelerin görselleştirilmesi</div>
          <Fig file="G8_wordclouds.png" caption="Partilerin içeriklerinde diğerlerine kıyasla en çok kullandığı 60 kelime. Boyutlar rölatif TF-IDF ağırlığı ile ölçeklendirilmiştir." />
        </>}
        right={<>
          <div className="slbl">Öne Çıkan Bulgular</div>
          <div className="finds">
            <Find title="Platform Bir Araç Olarak Kullanım">
              &quot;youtube&quot;, &quot;com&quot;, &quot;watch&quot; gibi teknik URL terimlerinin baskın olması, siyasetçilerin <strong>başka platformlardaki içeriklerinin bağlantılarını paylaştıklarını</strong> kanıtlamaktadır.
            </Find>
            <Find title="DEM Parti'nin Kişi Odaklı Dili">
              DEM Parti&apos;nin kelime bulutu neredeyse tamamen &quot;gergerlioglu&quot; kelimesinden oluşmaktadır. Parti söylemi tek bir vekilin faaliyetine indirgenmiştir.
            </Find>
            <Find title="Morfolojik Parçalanma (NLP Sınırı)">
              &quot;nin&quot;, &quot;ye&quot;, &quot;na&quot; gibi eklerin görünmesi, Türkçenin sondan eklemeli yapısının yarattığı tipik bir zorluktur.
            </Find>
          </div>
          <Meth title="TF-IDF Ağırlıklandırma Yöntemi">
            Bir kelimenin önemini hesaplamak için frekans tek başına yetersizdir:
            <span className="fm">TF-IDF(t, d) = tf(t,d) × log(N / df(t))</span>
            Her partinin kendi içinde sık, genel ekosistemde nadir (ayırt edici) kelimeleri öne çıkarır.
          </Meth>
        </>}
      />

      {/* ─── S11 Ideology ─────────────────────────────────────────── */}
      <Section id="s11"
        left={<>
          <div className="slbl">Bölüm 11 &mdash; İdeoloji Sınıflandırması</div>
          <div className="stit">Makine Öğrenmesi ile Siyasi Söylem Ayrımı</div>
          <div className="ssub">Linear SVM Modeli Karmaşıklık Matrisi (Normalize Edilmiş)</div>
          <Fig file="ideology_confusion_matrix.png" caption="Diyagonal: Modelin doğru tahmin oranları. Diyagonal Dışı: Karıştırılan söylemler. 5-katlı StratifiedKFold çapraz geçerleme." />
        </>}
        right={<>
          <div className="slbl">Öne Çıkan Bulgular</div>
          <div className="finds">
            <Find title="DEM Parti'nin Özgün Söylemi">
              Model, DEM Parti gönderilerini <strong><span className="n">%88</span></strong> isabet oranıyla doğru tahmin etmiştir. Diğer hiçbir partiyle kesişmeyen, tamamen izole bir terminoloji kullanılmaktadır.
            </Find>
            <Find title="CHP'nin Muhalefet Dili Çekim Gücü">
              CHP görece yüksek doğrulukla (<strong><span className="n">%76</span></strong>) tespit edilmiş; küçük muhalefet partilerinin <strong><span className="nr">%33–%42&apos;si</span></strong> yanlışlıkla CHP olarak sınıflandırılmıştır.
            </Find>
            <Find title="İç İçe Geçen İdeolojiler: MHP ve AKP">
              MHP gönderileri yalnızca <strong><span className="nr">%49</span></strong> doğrulukla tahmin edilmiştir; <strong><span className="nr">%18&apos;i</span></strong> AKP söylemiyle karıştırılmıştır. Cumhur İttifakı&apos;nın siyasi dili algoritmik düzeyde entegre olmuştur.
            </Find>
          </div>
          <Meth title="Sınıflandırma Mimarisi ve Metrikler">
            <strong>Özellik Mühendisliği:</strong> Kelime (1-3 gram) + karakter (2-5 gram) TF-IDF birleşimi, <code className="i">SelectKBest</code> ile özellik seçimi.<br /><br />
            <strong>Model:</strong> Seyrek, yüksek boyutlu metin verilerinde başarılı <strong>Linear SVM</strong>. Dengesiz veri: RandomOverSampler.<br /><br />
            <strong>Değerlendirme:</strong> Accuracy yerine Macro-F1 ve MCC kullanılmıştır.
          </Meth>
        </>}
      />
    </>
  );
}
