"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import PostCard, { Post } from "./PostCard";

/* ─── Filter definitions ────────────────────────────────────────── */
const DAYS_OPTIONS = [
  { label: "Son 1 Gün", value: 1 },
  { label: "Son 7 Gün", value: 7 },
  { label: "Son 30 Gün", value: 30 },
  { label: "Tümü", value: 0 },
];

const PARTY_OPTIONS = [
  { label: "Tüm Partiler", value: "" },
  { label: "CHP", value: "Cumhuriyet Halk Partisi" },
  { label: "AKP", value: "Adalet ve Kalkınma Partisi" },
  { label: "MHP", value: "Milliyetçi Hareket Partisi" },
  { label: "DEM Parti", value: "Halkların Eşitlik ve Demokrasi Partisi" },
  { label: "İYİ Parti", value: "İYİ Parti" },
  { label: "Yeni Yol", value: "Yeni Yol" },
  { label: "Bağımsız", value: "Bağımsız" },
  { label: "Diğer", value: "Diğer" },
];

const SENTIMENT_OPTIONS = [
  { label: "Tüm Duygular", value: "" },
  { label: "▲ Pozitif", value: "positive" },
  { label: "▬ Nötr", value: "neutral" },
  { label: "▼ Negatif", value: "negative" },
];

const HS_OPTIONS = [
  { label: "Tümü", value: "" },
  { label: "⚠ Nefret Söylemi Var", value: "Yes" },
  { label: "✓ Temiz", value: "No" },
];

const PAGE_SIZE = 30;

/* ─── Select component ──────────────────────────────────────────── */
function FilterSelect({
  value, onChange, options,
}: {
  value: string;
  onChange: (v: string) => void;
  options: { label: string; value: string | number }[];
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      style={{
        fontFamily: "var(--mono)", fontSize: 13,
        background: "var(--input-bg)", color: "var(--text)",
        border: "1px solid var(--border)", borderRadius: 6,
        padding: "7px 12px", cursor: "pointer", outline: "none",
        appearance: "none", WebkitAppearance: "none",
        backgroundImage: "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%236b7280' stroke-width='2'%3E%3Cpolyline points='6 9 12 15 18 9'/%3E%3C/svg%3E\")",
        backgroundRepeat: "no-repeat", backgroundPosition: "right 10px center",
        paddingRight: 30,
      }}
    >
      {options.map((o) => (
        <option key={String(o.value)} value={String(o.value)}>{o.label}</option>
      ))}
    </select>
  );
}

/* ─── Stats bar ─────────────────────────────────────────────────── */
function StatsBar({ total, loaded }: { total: number; loaded: number }) {
  return (
    <div style={{
      fontFamily: "var(--mono)", fontSize: 12, color: "var(--muted)",
      padding: "10px 0", borderBottom: "1px solid var(--border)", marginBottom: 16,
      display: "flex", gap: 20,
    }}>
      <span><strong style={{ color: "var(--accent-d)" }}>{total.toLocaleString("tr-TR")}</strong> gönderi bulundu</span>
      <span>Gösterilen: <strong style={{ color: "var(--text)" }}>{loaded}</strong></span>
    </div>
  );
}

/* ─── Main Component ────────────────────────────────────────────── */
export default function FeedTab() {
  const [days, setDays] = useState("0");
  const [party, setParty] = useState("");
  const [sentiment, setSentiment] = useState("");
  const [hateSpeech, setHateSpeech] = useState("");
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");

  const [posts, setPosts] = useState<Post[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const abortRef = useRef<AbortController | null>(null);

  const buildURL = useCallback((off: number) => {
    const p = new URLSearchParams();
    if (days && days !== "0") p.set("days", days);
    if (party) p.set("party", party);
    if (sentiment) p.set("sentiment", sentiment);
    if (hateSpeech) p.set("hate_speech", hateSpeech);
    if (search) p.set("search", search);
    p.set("limit", String(PAGE_SIZE));
    p.set("offset", String(off));
    return `/api/posts?${p.toString()}`;
  }, [days, party, sentiment, hateSpeech, search]);

  const fetchPosts = useCallback(async (off: number, append: boolean) => {
    if (abortRef.current) abortRef.current.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;

    setLoading(true);
    setError("");
    try {
      const res = await fetch(buildURL(off), { signal: ctrl.signal });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setPosts((prev) => append ? [...prev, ...data.posts] : data.posts);
      setTotal(data.total);
      setOffset(off + data.posts.length);
    } catch (e: unknown) {
      if (e instanceof Error && e.name !== "AbortError") setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [buildURL]);

  // Refetch when filters change
  useEffect(() => {
    setOffset(0);
    fetchPosts(0, false);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [days, party, sentiment, hateSpeech, search]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setSearch(searchInput);
  };

  const loadMore = () => fetchPosts(offset, true);

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", padding: "32px 24px" }}>
      {/* ─── Filter bar ─────────────────────────────────────────── */}
      <div style={{
        position: "sticky", top: 48, zIndex: 80,
        background: "var(--bg)", borderBottom: "1px solid var(--border)",
        paddingBottom: 16, paddingTop: 20, marginBottom: 20,
      }}>
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontFamily: "var(--mono)", fontSize: 11, fontWeight: 500, letterSpacing: "0.14em", color: "var(--accent)", textTransform: "uppercase", marginBottom: 12 }}>
            Feed Filtrele
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
            {/* Time filter as pill buttons */}
            <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
              {DAYS_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setDays(String(opt.value))}
                  style={{
                    fontFamily: "var(--mono)", fontSize: 12, fontWeight: 500,
                    padding: "6px 14px", borderRadius: 20, cursor: "pointer",
                    border: `1px solid ${days === String(opt.value) ? "var(--accent)" : "var(--border)"}`,
                    background: days === String(opt.value) ? "var(--accent)" : "var(--input-bg)",
                    color: days === String(opt.value) ? "#fff" : "var(--muted)",
                    transition: "all 0.12s",
                  }}
                >
                  {opt.label}
                </button>
              ))}
            </div>

            <FilterSelect value={party} onChange={setParty} options={PARTY_OPTIONS} />
            <FilterSelect value={sentiment} onChange={setSentiment} options={SENTIMENT_OPTIONS} />
            <FilterSelect value={hateSpeech} onChange={setHateSpeech} options={HS_OPTIONS} />
          </div>
        </div>

        {/* Search bar */}
        <form onSubmit={handleSearch} style={{ display: "flex", gap: 8 }}>
          <input
            type="text"
            placeholder="Anahtar kelime ara... (örn: imamoğlu, seçim, ekonomi)"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            style={{
              flex: 1, fontFamily: "var(--mono)", fontSize: 13,
              background: "var(--input-bg)", color: "var(--text)",
              border: "1px solid var(--border)", borderRadius: 6,
              padding: "9px 14px", outline: "none",
            }}
            onFocus={(e) => { (e.currentTarget as HTMLElement).style.borderColor = "var(--accent)"; }}
            onBlur={(e) => { (e.currentTarget as HTMLElement).style.borderColor = "var(--border)"; }}
          />
          <button
            type="submit"
            style={{
              fontFamily: "var(--mono)", fontSize: 12, fontWeight: 600,
              background: "var(--accent)", color: "#fff", border: "none",
              borderRadius: 6, padding: "9px 20px", cursor: "pointer",
              letterSpacing: "0.05em",
            }}
          >
            Ara
          </button>
          {search && (
            <button
              type="button"
              onClick={() => { setSearchInput(""); setSearch(""); }}
              style={{
                fontFamily: "var(--mono)", fontSize: 12,
                background: "var(--input-bg)", color: "var(--muted)",
                border: "1px solid var(--border)", borderRadius: 6,
                padding: "9px 14px", cursor: "pointer",
              }}
            >
              ✕ Temizle
            </button>
          )}
        </form>

        {/* Active filter chips */}
        {(search || party || sentiment || hateSpeech) && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 10 }}>
            {search && <Chip label={`"${search}"`} onRemove={() => { setSearch(""); setSearchInput(""); }} />}
            {party && <Chip label={PARTY_OPTIONS.find(o => o.value === party)?.label || party} onRemove={() => setParty("")} />}
            {sentiment && <Chip label={SENTIMENT_OPTIONS.find(o => o.value === sentiment)?.label || sentiment} onRemove={() => setSentiment("")} />}
            {hateSpeech && <Chip label={HS_OPTIONS.find(o => o.value === hateSpeech)?.label || hateSpeech} onRemove={() => setHateSpeech("")} />}
          </div>
        )}
      </div>

      {/* ─── Stats ──────────────────────────────────────────────── */}
      {posts.length > 0 && <StatsBar total={total} loaded={posts.length} />}

      {/* ─── Error ──────────────────────────────────────────────── */}
      {error && (
        <div style={{ background: "rgba(220,53,69,0.08)", border: "1px solid rgba(220,53,69,0.3)", borderRadius: 6, padding: "14px 18px", marginBottom: 16, fontFamily: "var(--mono)", fontSize: 14, color: "var(--red)" }}>
          Hata: {error}
        </div>
      )}

      {/* ─── Loading skeleton ────────────────────────────────────── */}
      {loading && posts.length === 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} style={{ background: "var(--card-bg)", border: "1px solid var(--card-border)", borderRadius: 8, padding: "16px 20px", height: 100, opacity: 0.5 + (i * 0.1) }} />
          ))}
        </div>
      )}

      {/* ─── Empty state ─────────────────────────────────────────── */}
      {!loading && posts.length === 0 && !error && (
        <div style={{ textAlign: "center", padding: "80px 0", color: "var(--muted)" }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>🔍</div>
          <div style={{ fontFamily: "var(--mono)", fontSize: 16 }}>Gönderi bulunamadı</div>
          <div style={{ fontSize: 14, marginTop: 8 }}>Filtrelerinizi değiştirip tekrar deneyin.</div>
        </div>
      )}

      {/* ─── Post list ───────────────────────────────────────────── */}
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {posts.map((post) => (
          <PostCard key={post.uri} post={post} />
        ))}
      </div>

      {/* ─── Load more / loading ─────────────────────────────────── */}
      {posts.length > 0 && (
        <div style={{ textAlign: "center", marginTop: 28 }}>
          {loading ? (
            <div style={{ fontFamily: "var(--mono)", fontSize: 13, color: "var(--muted)", padding: 16 }}>
              Yükleniyor…
            </div>
          ) : offset < total ? (
            <button
              onClick={loadMore}
              style={{
                fontFamily: "var(--mono)", fontSize: 13, fontWeight: 500,
                background: "var(--surface)", color: "var(--text)",
                border: "1px solid var(--border)", borderRadius: 6,
                padding: "12px 32px", cursor: "pointer",
                letterSpacing: "0.05em",
              }}
              onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.borderColor = "var(--accent)"; }}
              onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.borderColor = "var(--border)"; }}
            >
              Daha Fazla Yükle ({(total - offset).toLocaleString("tr-TR")} kaldı)
            </button>
          ) : (
            <div style={{ fontFamily: "var(--mono)", fontSize: 12, color: "var(--muted)", padding: 16 }}>
              Tüm gönderiler yüklendi ({total.toLocaleString("tr-TR")} toplam)
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ─── Chip ──────────────────────────────────────────────────────── */
function Chip({ label, onRemove }: { label: string; onRemove: () => void }) {
  return (
    <span style={{
      fontFamily: "var(--mono)", fontSize: 11, fontWeight: 500,
      background: "rgba(160,113,42,0.12)", color: "var(--accent-d)",
      border: "1px solid rgba(160,113,42,0.25)",
      padding: "3px 10px", borderRadius: 20,
      display: "inline-flex", alignItems: "center", gap: 6,
    }}>
      {label}
      <button onClick={onRemove} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--accent)", fontSize: 12, padding: 0, lineHeight: 1 }}>✕</button>
    </span>
  );
}
