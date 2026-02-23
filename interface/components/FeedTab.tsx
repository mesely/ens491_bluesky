"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import PostCard, { Post, PARTY_COLORS, PARTY_SHORT, partyColor } from "./PostCard";

/* ─── Types ──────────────────────────────────────────────────────── */
interface Stats {
  total: number;
  byParty: Record<string, number>;
  bySentiment: Record<string, number>;
  byHateSpeech: Record<string, number>;
}
interface Keyword { keyword: string; count: number; }

/* ─── Bluesky SVG icons ─────────────────────────────────────────── */
function HomeIcon({ active }: { active?: boolean }) {
  return <svg width="26" height="26" viewBox="0 0 24 24" fill={active ? "currentColor" : "none"} stroke="currentColor" strokeWidth={active ? 0 : 1.8} strokeLinecap="round" strokeLinejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>;
}
function BellIcon({ active }: { active?: boolean }) {
  return <svg width="26" height="26" viewBox="0 0 24 24" fill={active ? "currentColor" : "none"} stroke="currentColor" strokeWidth={active ? 0 : 1.8} strokeLinecap="round" strokeLinejoin="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>;
}
function MailIcon() {
  return <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>;
}
function SearchIconSvg() {
  return <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>;
}
function ListIcon() {
  return <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>;
}
function UserIcon() {
  return <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>;
}
function SettingsIcon() {
  return <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>;
}
function PlusIcon() {
  return <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>;
}
function BskyLogo() {
  // bluesky.webp from /public — invert in dark mode via CSS filter
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src="/bluesky.webp"
      alt="Bluesky"
      width={34}
      height={34}
      style={{
        objectFit: "contain",
        // light mode = keep original colours; dark mode = invert to white
        filter: "var(--bsky-logo-filter)",
      }}
    />
  );
}

/* ─── Constants ─────────────────────────────────────────────────── */
const PAGE_SIZE = 20;

const PARTY_ORDER = [
  "Cumhuriyet Halk Partisi",
  "Adalet ve Kalkınma Partisi",
  "Milliyetçi Hareket Partisi",
  "Halkların Eşitlik ve Demokrasi Partisi",
  "İYİ Parti",
  "Yeni Yol",
  "Bağımsız",
  "Muhalif",
  "İktidar Yanlısı",
  "Tarafsız/Haber",
  "Diğer",
];

/* ─── Left Sidebar ───────────────────────────────────────────────── */
function LeftSidebar({
  activeFilter, setFilter,
}: {
  activeFilter: string;
  setFilter: (f: string) => void;
}) {
  const navItems = [
    { label: "Ana Sayfa", icon: <HomeIcon active />, value: "" },
    { label: "Bildirimler", icon: <BellIcon />, value: null },
    { label: "Mesajlar", icon: <MailIcon />, value: null },
    { label: "Keşfet", icon: <SearchIconSvg />, value: null },
    { label: "Listeler", icon: <ListIcon />, value: null },
    { label: "Profil", icon: <UserIcon />, value: null },
    { label: "Ayarlar", icon: <SettingsIcon />, value: null },
  ];

  return (
    <aside style={{
      width: 240, flexShrink: 0,
      display: "flex", flexDirection: "column",
      position: "sticky", top: 48, height: "calc(100vh - 48px)",
      overflowY: "auto", paddingTop: 4,
      borderRight: "1px solid var(--bsky-border)",
    }}>
      {/* Logo */}
      <div style={{ padding: "16px 20px 12px", display: "flex", alignItems: "center", gap: 10 }}>
        <BskyLogo />
      </div>

      {/* Nav items */}
      <nav style={{ flex: 1 }}>
        {navItems.map((item) => (
          <button
            key={item.label}
            onClick={() => item.value !== null && setFilter(item.value as string)}
            style={{
              width: "100%", display: "flex", alignItems: "center", gap: 16,
              padding: "12px 20px", background: "none", border: "none",
              cursor: item.value !== null ? "pointer" : "default",
              color: item.label === "Ana Sayfa" ? "var(--bsky-text)" : "var(--bsky-dim)",
              fontSize: 20, fontWeight: item.label === "Ana Sayfa" ? 700 : 400,
              borderRadius: 40, transition: "background 0.12s",
              textAlign: "left",
            }}
            onMouseEnter={(e) => {
              if (item.value !== null)
                (e.currentTarget as HTMLElement).style.background = "var(--bsky-hover-strong)";
            }}
            onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = "none"; }}
          >
            <span style={{ color: item.label === "Ana Sayfa" ? "var(--bsky-text)" : "var(--bsky-dim)", display: "flex" }}>
              {item.icon}
            </span>
            {item.label}
          </button>
        ))}
      </nav>

      {/* New post / feed button */}
      <div style={{ padding: "16px 20px" }}>
        <button style={{
          width: "100%", padding: "14px 20px",
          background: "var(--bsky-blue)", color: "#fff", border: "none",
          borderRadius: 40, fontSize: 17, fontWeight: 700, cursor: "pointer",
          display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
          transition: "opacity 0.15s",
        }}
          onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.opacity = "0.88"; }}
          onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.opacity = "1"; }}
        >
          <PlusIcon /> Feed Oluştur
        </button>
      </div>

      {/* Bottom user profile */}
      <div style={{
        margin: "8px 12px 20px",
        padding: "10px 12px", borderRadius: 40,
        display: "flex", alignItems: "center", gap: 10,
        cursor: "pointer", transition: "background 0.12s",
      }}
        onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = "var(--bsky-hover-strong)"; }}
        onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = "none"; }}
      >
        <div style={{
          width: 40, height: 40, borderRadius: "50%",
          background: "var(--bsky-blue)",
          display: "flex", alignItems: "center", justifyContent: "center",
          color: "#fff", fontWeight: 700, fontSize: 16, flexShrink: 0,
        }}>A</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 700, fontSize: 14, color: "var(--bsky-text)" }}>Araştırmacı</div>
          <div style={{ fontSize: 13, color: "var(--bsky-dim)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>@arastirmaci.bsky.social</div>
        </div>
        <span style={{ color: "var(--bsky-dim)", fontSize: 18 }}>···</span>
      </div>
    </aside>
  );
}

/* ─── Right Sidebar ─────────────────────────────────────────────── */
function RightSidebar({
  stats, keywords, filterParams, onSearch, postsTotal,
}: {
  stats: Stats | null;
  keywords: Keyword[];
  filterParams: Record<string, string>;
  onSearch: (q: string) => void;
  postsTotal: number;
}) {
  const [searchVal, setSearchVal] = useState(filterParams.search || "");

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSearch(searchVal);
  };

  return (
    <aside style={{
      width: 320, flexShrink: 0,
      position: "sticky", top: 48, height: "calc(100vh - 48px)",
      overflowY: "auto", padding: "16px 16px",
      borderLeft: "1px solid var(--bsky-border)",
    }}>
      {/* Search bar */}
      <form onSubmit={handleSearchSubmit} style={{ marginBottom: 20 }}>
        <div style={{
          display: "flex", alignItems: "center", gap: 10,
          background: "var(--bsky-input)", borderRadius: 40,
          padding: "10px 18px", border: "2px solid transparent",
        }}
          onFocus={(e) => { (e.currentTarget as HTMLElement).style.borderColor = "var(--bsky-blue)"; }}
          onBlur={(e) => { (e.currentTarget as HTMLElement).style.borderColor = "transparent"; }}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--bsky-dim)" strokeWidth="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          <input
            type="text"
            placeholder="Gönderilerde ara"
            value={searchVal}
            onChange={(e) => setSearchVal(e.target.value)}
            style={{
              flex: 1, background: "none", border: "none", outline: "none",
              fontSize: 15, color: "var(--bsky-text)",
              fontFamily: "var(--font-sans, sans-serif)",
            }}
          />
          {searchVal && (
            <button type="button" onClick={() => { setSearchVal(""); onSearch(""); }}
              style={{ background: "none", border: "none", cursor: "pointer", color: "var(--bsky-dim)", fontSize: 16 }}>✕</button>
          )}
        </div>
      </form>

      {/* Stats widget */}
      {stats && (
        <section style={{
          background: "var(--bsky-card)", borderRadius: 16,
          padding: "18px 20px", marginBottom: 16,
          border: "1px solid var(--bsky-border)",
        }}>
          <div style={{ fontWeight: 700, fontSize: 20, color: "var(--bsky-text)", marginBottom: 14 }}>
            Filtre İstatistikleri
          </div>
          <div style={{ fontSize: 13, color: "var(--bsky-dim)", fontFamily: "var(--font-mono, monospace)", marginBottom: 12 }}>
            {postsTotal.toLocaleString("tr-TR")} gönderi
          </div>

          {/* Party breakdown */}
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: "var(--bsky-dim)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 8 }}>Parti Dağılımı</div>
            {PARTY_ORDER.filter((p) => stats.byParty[p] > 0).map((party) => {
              const count = stats.byParty[party] || 0;
              const pct = postsTotal > 0 ? (count / postsTotal) * 100 : 0;
              const color = PARTY_COLORS[party] || "#636e72";
              const short = PARTY_SHORT[party] || "?";
              return (
                <div key={party} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                  <span style={{
                    width: 32, fontSize: 10, fontWeight: 700, fontFamily: "var(--font-mono, monospace)",
                    color, textAlign: "right", flexShrink: 0,
                  }}>{short}</span>
                  <div style={{
                    flex: 1, height: 8, background: "var(--bsky-border)", borderRadius: 4, overflow: "hidden",
                  }}>
                    <div style={{ width: `${Math.max(pct, 1)}%`, height: "100%", background: color, borderRadius: 4, transition: "width 0.4s" }} />
                  </div>
                  <span style={{ fontSize: 12, color: "var(--bsky-dim)", fontFamily: "var(--font-mono, monospace)", width: 40, textAlign: "right" }}>
                    {count.toLocaleString("tr-TR")}
                  </span>
                </div>
              );
            })}
          </div>

          {/* Sentiment */}
          <div style={{ marginBottom: 10 }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: "var(--bsky-dim)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 8 }}>Duygu Dağılımı</div>
            {[
              { key: "positive", label: "Pozitif", color: "#27ae60" },
              { key: "neutral", label: "Nötr", color: "#95a5a6" },
              { key: "negative", label: "Negatif", color: "#e74c3c" },
            ].map(({ key, label, color }) => {
              const count = stats.bySentiment[key] || 0;
              const sentTotal = (stats.bySentiment.positive || 0) + (stats.bySentiment.neutral || 0) + (stats.bySentiment.negative || 0);
              const pct = sentTotal > 0 ? (count / sentTotal) * 100 : 0;
              return (
                <div key={key} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                  <span style={{ width: 50, fontSize: 11, color: "var(--bsky-dim)", flexShrink: 0 }}>{label}</span>
                  <div style={{ flex: 1, height: 8, background: "var(--bsky-border)", borderRadius: 4, overflow: "hidden" }}>
                    <div style={{ width: `${Math.max(pct, 0.5)}%`, height: "100%", background: color, borderRadius: 4, transition: "width 0.4s" }} />
                  </div>
                  <span style={{ fontSize: 11, color: "var(--bsky-dim)", fontFamily: "var(--font-mono, monospace)", width: 32, textAlign: "right" }}>
                    {Math.round(pct)}%
                  </span>
                </div>
              );
            })}
          </div>

          {/* Hate speech */}
          {stats.byHateSpeech.Yes > 0 && (
            <div style={{ marginTop: 10, padding: "8px 12px", background: "#e74c3c10", borderRadius: 8, border: "1px solid #e74c3c25" }}>
              <span style={{ fontSize: 12, color: "#e74c3c", fontFamily: "var(--font-mono, monospace)" }}>
                ⚠ Nefret söylemi: {stats.byHateSpeech.Yes.toLocaleString("tr-TR")} gönderi
                ({postsTotal > 0 ? ((stats.byHateSpeech.Yes / postsTotal) * 100).toFixed(1) : "0"}%)
              </span>
            </div>
          )}
        </section>
      )}

      {/* Keyword list */}
      {keywords.length > 0 && (
        <section style={{
          background: "var(--bsky-card)", borderRadius: 16,
          padding: "18px 20px", marginBottom: 16,
          border: "1px solid var(--bsky-border)",
        }}>
          <div style={{ fontWeight: 700, fontSize: 20, color: "var(--bsky-text)", marginBottom: 14 }}>
            Kullanılan Anahtar Kelimeler
          </div>
          {keywords.map((kw) => (
            <div key={kw.keyword} style={{
              padding: "8px 0", borderBottom: "1px solid var(--bsky-border)",
              cursor: "pointer", transition: "background 0.1s",
            }}
              onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = "var(--bsky-hover)"; }}
              onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = "none"; }}
              onClick={() => onSearch(kw.keyword)}
            >
              <div style={{ fontSize: 15, fontWeight: 600, color: "var(--bsky-text)" }}>
                #{kw.keyword}
              </div>
              <div style={{ fontSize: 12, color: "var(--bsky-dim)", marginTop: 2 }}>
                {kw.count.toLocaleString("tr-TR")} gönderi
              </div>
            </div>
          ))}
        </section>
      )}

      {/* Footer links */}
      <div style={{ fontSize: 12, color: "var(--bsky-dim)", lineHeight: 2 }}>
        <span style={{ marginRight: 10, cursor: "pointer" }}>Hizmetler</span>
        <span style={{ marginRight: 10, cursor: "pointer" }}>Gizlilik</span>
        <span style={{ marginRight: 10, cursor: "pointer" }}>Çerezler</span>
        <span style={{ marginRight: 10, cursor: "pointer" }}>Erişilebilirlik</span>
        <span style={{ marginRight: 10, cursor: "pointer" }}>Daha Fazla</span>
        <div style={{ marginTop: 4 }}>BlueSky TR Siyasi Ekosistemi · Şubat 2026</div>
      </div>
    </aside>
  );
}

/* ─── Filter pills row ───────────────────────────────────────────── */
const DAYS_OPTS = [
  { label: "Tümü", value: "0" },
  { label: "1 Gün", value: "1" },
  { label: "7 Gün", value: "7" },
  { label: "30 Gün", value: "30" },
];
const PARTY_OPTS = [
  { label: "Tüm Partiler", value: "" },
  { label: "CHP", value: "Cumhuriyet Halk Partisi" },
  { label: "AKP", value: "Adalet ve Kalkınma Partisi" },
  { label: "MHP", value: "Milliyetçi Hareket Partisi" },
  { label: "DEM", value: "Halkların Eşitlik ve Demokrasi Partisi" },
  { label: "İYİ", value: "İYİ Parti" },
  { label: "YY", value: "Yeni Yol" },
  { label: "Bağ.", value: "Bağımsız" },
  { label: "Muhalif", value: "Muhalif" },
  { label: "İktidar Y.", value: "İktidar Yanlısı" },
  { label: "Tarafsız", value: "Tarafsız/Haber" },
  { label: "Diğer", value: "Diğer" },
];
const SENT_OPTS = [
  { label: "Tüm Duygular", value: "" },
  { label: "▲ Pozitif", value: "positive" },
  { label: "▬ Nötr", value: "neutral" },
  { label: "▼ Negatif", value: "negative" },
];
const HS_OPTS = [
  { label: "Tümü", value: "" },
  { label: "⚠ Nefret Var", value: "Yes" },
  { label: "✓ Temiz", value: "No" },
];
const FEED_OPTS = [
  { label: "Tüm Kaynaklar", value: "all" },
  { label: "Anahtar Kelime", value: "keyword" },
  { label: "Protesto", value: "protest" },
];

function PillSelect({ value, onChange, options }: {
  value: string;
  onChange: (v: string) => void;
  options: { label: string; value: string }[];
}) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)}
      style={{
        fontSize: 14, background: "var(--bsky-input)", color: "var(--bsky-text)",
        border: "1px solid var(--bsky-border)", borderRadius: 20,
        padding: "6px 28px 6px 14px", cursor: "pointer", outline: "none",
        appearance: "none", WebkitAppearance: "none",
        backgroundImage: "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='10' viewBox='0 0 24 24' fill='none' stroke='%236b7280' stroke-width='2'%3E%3Cpolyline points='6 9 12 15 18 9'/%3E%3C/svg%3E\")",
        backgroundRepeat: "no-repeat", backgroundPosition: "right 10px center",
        fontFamily: "var(--font-sans, sans-serif)",
      }}>
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
}

/* ─── Center Feed ────────────────────────────────────────────────── */
function CenterFeed({
  activeTab, setActiveTab, days, setDays, party, setParty,
  sentiment, setSentiment, hateSpeech, setHateSpeech,
  feed, setFeed,
  search, setSearch, posts, total, offset, loading, error, loadMore,
}: {
  activeTab: string; setActiveTab: (t: string) => void;
  days: string; setDays: (v: string) => void;
  party: string; setParty: (v: string) => void;
  sentiment: string; setSentiment: (v: string) => void;
  hateSpeech: string; setHateSpeech: (v: string) => void;
  feed: string; setFeed: (v: string) => void;
  search: string; setSearch: (v: string) => void;
  posts: Post[]; total: number; offset: number;
  loading: boolean; error: string; loadMore: () => void;
}) {
  const TABS = ["Tüm Siyasi Gönderiler", "İmamoğlu Protestoları"];

  return (
    <main style={{
      flex: 1, minWidth: 0, maxWidth: 600,
      borderLeft: "1px solid var(--bsky-border)",
      borderRight: "1px solid var(--bsky-border)",
    }}>
      {/* Tabs */}
      <div style={{
        position: "sticky", top: 48, zIndex: 10,
        background: "var(--bsky-bg)", borderBottom: "1px solid var(--bsky-border)",
        display: "flex",
        backdropFilter: "blur(8px)",
        overflowX: "auto",
      }}>
        {TABS.map((tab) => (
          <button key={tab} onClick={() => handleTabChange(tab)}
            style={{
              flex: 1,
              padding: "16px 12px",
              background: "none", border: "none", cursor: "pointer",
              fontSize: 15,
              fontWeight: activeTab === tab ? 700 : 400,
              color: activeTab === tab
                ? (tab === "İmamoğlu Protestoları" ? "#e67e22" : "var(--bsky-text)")
                : "var(--bsky-dim)",
              borderBottom: activeTab === tab
                ? `2px solid ${tab === "İmamoğlu Protestoları" ? "#e67e22" : "var(--bsky-blue)"}`
                : "2px solid transparent",
              transition: "all 0.15s",
              whiteSpace: "nowrap",
            }}>
            {tab}
          </button>
        ))}
      </div>

      {/* Filter row */}
      <div style={{
        padding: "12px 16px", borderBottom: "1px solid var(--bsky-border)",
        display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center",
      }}>
        {/* Time pills */}
        <div style={{ display: "flex", gap: 4 }}>
          {DAYS_OPTS.map((o) => (
            <button key={o.value} onClick={() => setDays(o.value)}
              style={{
                fontSize: 13, fontWeight: 500, padding: "5px 12px", borderRadius: 20,
                border: `1px solid ${days === o.value ? "var(--bsky-blue)" : "var(--bsky-border)"}`,
                background: days === o.value ? "var(--bsky-blue)" : "var(--bsky-input)",
                color: days === o.value ? "#fff" : "var(--bsky-dim)",
                cursor: "pointer", transition: "all 0.12s",
              }}>
              {o.label}
            </button>
          ))}
        </div>

        <PillSelect value={party} onChange={setParty} options={PARTY_OPTS} />
        <PillSelect value={sentiment} onChange={setSentiment} options={SENT_OPTS} />
        <PillSelect value={hateSpeech} onChange={setHateSpeech} options={HS_OPTS} />
        <PillSelect value={feed} onChange={setFeed} options={FEED_OPTS} />

        {/* Clear filters */}
        {(party || sentiment || hateSpeech || search || days !== "0" || feed !== "all") && (
          <button onClick={() => { setDays("0"); setParty(""); setSentiment(""); setHateSpeech(""); setSearch(""); setFeed("all"); }}
            style={{
              fontSize: 12, padding: "5px 12px", borderRadius: 20,
              border: "1px solid var(--bsky-border)",
              background: "none", color: "var(--bsky-dim)", cursor: "pointer",
            }}>
            Temizle ✕
          </button>
        )}

        {/* Active search chip */}
        {search && (
          <span style={{
            fontSize: 12, fontWeight: 500,
            background: "var(--bsky-blue)20", color: "var(--bsky-blue)",
            border: "1px solid var(--bsky-blue)40",
            padding: "4px 12px", borderRadius: 20,
            display: "inline-flex", alignItems: "center", gap: 6,
          }}>
            &ldquo;{search}&rdquo;
            <button onClick={() => setSearch("")} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--bsky-blue)", fontSize: 13, padding: 0 }}>✕</button>
          </span>
        )}

        {/* Protest mode banner */}
        {activeTab === "İmamoğlu Protestoları" && (
          <div style={{
            width: "100%", marginTop: 4,
            padding: "8px 12px", borderRadius: 8,
            background: "#e67e2210", border: "1px solid #e67e2240",
            fontSize: 12, color: "#e67e22", lineHeight: 1.5,
          }}>
            <b>Araştırma sorusu:</b> Sosyal medyada üretilen toksisite ve duygu kutuplaşması,
            fiziksel dünya güvenlik olaylarıyla (gözaltı, tutuklama, polis müdahalesi) zamansal
            olarak nasıl bir etkileşim içindedir? — 18 Mart 2025 sonrası veriler
          </div>
        )}
      </div>

      {/* Post count */}
      {posts.length > 0 && (
        <div style={{ padding: "10px 16px", borderBottom: "1px solid var(--bsky-border)", fontSize: 13, color: "var(--bsky-dim)" }}>
          <span style={{ fontFamily: "var(--font-mono, monospace)" }}>
            {total.toLocaleString("tr-TR")} gönderi · {posts.length} gösteriliyor
          </span>
        </div>
      )}

      {/* Error */}
      {error && (
        <div style={{ margin: "16px", padding: "14px", background: "#e74c3c12", borderRadius: 12, border: "1px solid #e74c3c30", color: "#e74c3c", fontSize: 14 }}>
          Hata: {error}
        </div>
      )}

      {/* Loading skeleton */}
      {loading && posts.length === 0 && (
        <div>
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} style={{
              padding: "16px", display: "flex", gap: 12,
              borderBottom: "1px solid var(--bsky-border)", opacity: 0.4 + i * 0.08,
            }}>
              <div style={{ width: 48, height: 48, borderRadius: "50%", background: "var(--bsky-border)", flexShrink: 0 }} />
              <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 8 }}>
                <div style={{ height: 14, width: "40%", background: "var(--bsky-border)", borderRadius: 4 }} />
                <div style={{ height: 12, width: "90%", background: "var(--bsky-border)", borderRadius: 4 }} />
                <div style={{ height: 12, width: "70%", background: "var(--bsky-border)", borderRadius: 4 }} />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Empty state */}
      {!loading && posts.length === 0 && !error && (
        <div style={{ textAlign: "center", padding: "80px 20px" }}>
          <div style={{ fontSize: 52, marginBottom: 16 }}>🔍</div>
          <div style={{ fontSize: 20, fontWeight: 700, color: "var(--bsky-text)", marginBottom: 8 }}>Gönderi bulunamadı</div>
          <div style={{ fontSize: 15, color: "var(--bsky-dim)" }}>Filtrelerinizi değiştirip tekrar deneyin.</div>
        </div>
      )}

      {/* Feed */}
      {posts.map((post) => <PostCard key={post.uri} post={post} />)}

      {/* Load more */}
      {posts.length > 0 && (
        <div style={{ padding: "24px 16px", textAlign: "center", borderTop: "1px solid var(--bsky-border)" }}>
          {loading ? (
            <span style={{ fontSize: 14, color: "var(--bsky-dim)" }}>Yükleniyor…</span>
          ) : offset < total ? (
            <button onClick={loadMore}
              style={{
                fontSize: 15, fontWeight: 600, color: "var(--bsky-blue)",
                background: "none", border: "1px solid var(--bsky-blue)",
                borderRadius: 40, padding: "10px 32px", cursor: "pointer",
                transition: "background 0.12s",
              }}
              onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = "var(--bsky-blue)14"; }}
              onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = "none"; }}
            >
              Daha Fazla Göster ({(total - offset).toLocaleString("tr-TR")} kaldı)
            </button>
          ) : (
            <span style={{ fontSize: 13, color: "var(--bsky-dim)" }}>
              Tüm {total.toLocaleString("tr-TR")} gönderi yüklendi
            </span>
          )}
        </div>
      )}
    </main>
  );
}

/* ─── FeedTab (root) ─────────────────────────────────────────────── */
export default function FeedTab() {
  // Filters
  const [activeTab, setActiveTab] = useState("Tüm Siyasi Gönderiler");
  const [days, setDays] = useState("0");
  const [party, setParty] = useState("");
  const [sentiment, setSentiment] = useState("");
  const [hateSpeech, setHateSpeech] = useState("");
  const [feed, setFeed] = useState("all");  // data source filter
  const [search, setSearch] = useState("");

  // Data
  const [posts, setPosts] = useState<Post[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [stats, setStats] = useState<Stats | null>(null);
  const [keywords, setKeywords] = useState<Keyword[]>([]);

  const abortRef = useRef<AbortController | null>(null);

  // Build query params shared between posts and stats APIs
  const filterQuery = useCallback(() => {
    const p = new URLSearchParams();
    if (days && days !== "0") p.set("days", days);
    if (party) p.set("party", party);
    if (sentiment) p.set("sentiment", sentiment);
    if (hateSpeech) p.set("hate_speech", hateSpeech);
    if (search) p.set("search", search);
    if (feed && feed !== "all") p.set("feed", feed);
    return p;
  }, [days, party, sentiment, hateSpeech, search, feed]);

  const fetchPosts = useCallback(async (off: number, append: boolean) => {
    if (abortRef.current) abortRef.current.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setLoading(true);
    setError("");
    try {
      const p = filterQuery();
      p.set("limit", String(PAGE_SIZE));
      p.set("offset", String(off));
      const res = await fetch(`/api/posts?${p.toString()}`, { signal: ctrl.signal });
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
  }, [filterQuery]);

  const fetchStats = useCallback(async () => {
    try {
      const res = await fetch(`/api/stats?${filterQuery().toString()}`);
      if (res.ok) setStats(await res.json());
    } catch { /* silent */ }
  }, [filterQuery]);

  // Keywords (based on feed)
  useEffect(() => {
    fetch(`/api/keywords?feed=${encodeURIComponent(feed)}`)
      .then((r) => r.json())
      .then((d) => setKeywords(d.keywords || []))
      .catch(() => { /* silent */ });
  }, [feed]);

  // Re-fetch when filters change
  useEffect(() => {
    setOffset(0);
    fetchPosts(0, false);
    fetchStats();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [days, party, sentiment, hateSpeech, search, feed, activeTab]);

  const handleTabChange = (tab: string) => {
    setActiveTab(tab);
    if (tab === "İmamoğlu Protestoları") {
      // Protest feed: use protest data source, clear other filters
      setSentiment("");
      setFeed("protest");
      setDays("0");
      setParty("");
      setHateSpeech("");
      setSearch("");
    } else {
      // "Tüm Siyasi Gönderiler"
      setSentiment("");
      setFeed("all");
    }
  };

  const handleSearchFromSidebar = (q: string) => {
    setSearch(q);
  };

  return (
    <div style={{
      display: "flex",
      maxWidth: 1280,
      margin: "0 auto",
      minHeight: "calc(100vh - 48px)",
      background: "var(--bsky-bg)",
    }}>
      <LeftSidebar activeFilter={party} setFilter={setParty} />
      <CenterFeed
        activeTab={activeTab} setActiveTab={handleTabChange}
        days={days} setDays={setDays}
        party={party} setParty={setParty}
        sentiment={sentiment} setSentiment={setSentiment}
        hateSpeech={hateSpeech} setHateSpeech={setHateSpeech}
        feed={feed} setFeed={setFeed}
        search={search} setSearch={setSearch}
        posts={posts} total={total} offset={offset}
        loading={loading} error={error}
        loadMore={() => fetchPosts(offset, true)}
      />
      <RightSidebar
        stats={stats}
        keywords={keywords}
        filterParams={{ days, party, sentiment, hate_speech: hateSpeech, search }}
        onSearch={handleSearchFromSidebar}
        postsTotal={total}
      />
    </div>
  );
}
