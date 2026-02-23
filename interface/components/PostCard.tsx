"use client";

import { useState } from "react";

export interface Post {
  uri: string;
  author_handle: string;
  party: string;
  party_normalized: string;
  party_affinity: string;       // inferred for non-tracked actors
  affinity_label: string;       // e.g. "CHP'ye yakın"
  alliance: string;
  political_stance: string;
  isMilletvekili: boolean;
  text: string;
  created_at: string;
  like_count: number;
  reply_count: number;
  repost_count: number;
  sentiment: string;
  sentiment_scores: string;
  hate_speech: string;
  hs_score: number;
  source: string;               // "dataset" | "keyword" | "protest"
  keyword: string;
  is_tracked_actor: boolean;
}

/* ─── Party colors ─────────────────────────────────────────────── */
export const PARTY_COLORS: Record<string, string> = {
  "Cumhuriyet Halk Partisi":                "#e03040",
  "Adalet ve Kalkınma Partisi":             "#e6a817",
  "Milliyetçi Hareket Partisi":             "#b8860b",
  "Halkların Eşitlik ve Demokrasi Partisi": "#27ae60",
  "İYİ Parti":                              "#2980b9",
  "Yeni Yol":                               "#8e44ad",
  "Bağımsız":                               "#7f8c8d",
  "Muhalif":                                "#c0392b",
  "İktidar Yanlısı":                        "#d68910",
  "Tarafsız/Haber":                         "#5d6d7e",
  "Diğer":                                  "#636e72",
};

export const PARTY_SHORT: Record<string, string> = {
  "Cumhuriyet Halk Partisi":                "CHP",
  "Adalet ve Kalkınma Partisi":             "AKP",
  "Milliyetçi Hareket Partisi":             "MHP",
  "Halkların Eşitlik ve Demokrasi Partisi": "DEM",
  "İYİ Parti":                              "İYİ",
  "Yeni Yol":                               "YY",
  "Bağımsız":                               "Bağ.",
  "Muhalif":                                "Muh",
  "İktidar Yanlısı":                        "İkt",
  "Tarafsız/Haber":                         "Tar",
  "Diğer":                                  "Diğer",
};

export function partyColor(party: string) {
  return PARTY_COLORS[party] || PARTY_COLORS["Diğer"];
}
export function partyShort(party: string) {
  return PARTY_SHORT[party] || "—";
}

/* ─── Relative time ─────────────────────────────────────────────── */
function relTime(iso: string): string {
  if (!iso) return "";
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return `${Math.floor(diff)}sn`;
  if (diff < 3600) return `${Math.floor(diff / 60)}dk`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}sa`;
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)}g`;
  return new Date(iso).toLocaleDateString("tr-TR", { day: "numeric", month: "short" });
}

/* ─── Bluesky action icons (SVG) ────────────────────────────────── */
function ReplyIcon() {
  return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>;
}
function RepostIcon() {
  return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/></svg>;
}
function LikeIcon({ filled }: { filled?: boolean }) {
  return <svg width="18" height="18" viewBox="0 0 24 24" fill={filled ? "currentColor" : "none"} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>;
}
function QuoteIcon() {
  return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 21c3 0 7-1 7-8V5c0-1.25-.756-2.017-2-2H4c-1.25 0-2 .75-2 1.972V11c0 1.25.75 2 2 2 1 0 1 0 1 1v1c0 1-1 2-2 2s-1 .008-1 1.031V20c0 1 0 1 1 1z"/><path d="M15 21c3 0 7-1 7-8V5c0-1.25-.757-2.017-2-2h-4c-1.25 0-2 .75-2 1.972V11c0 1.25.75 2 2 2h.75c0 2.25.25 4-2.75 4v3c0 1 0 1 1 1z"/></svg>;
}
function MoreIcon() {
  return <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><circle cx="5" cy="12" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="19" cy="12" r="1.5"/></svg>;
}

/* ─── Sentiment dot ─────────────────────────────────────────────── */
const SENT_DOT: Record<string, string> = {
  positive: "#27ae60",
  neutral: "#95a5a6",
  negative: "#e74c3c",
};
const SENT_TR: Record<string, string> = {
  positive: "Pozitif",
  neutral: "Nötr",
  negative: "Negatif",
};

/* ─── PostCard ──────────────────────────────────────────────────── */
export default function PostCard({ post }: { post: Post }) {
  const [liked, setLiked] = useState(false);
  const [likeCount, setLikeCount] = useState(post.like_count);
  const [expanded, setExpanded] = useState(false);

  const MAX = 300;
  const truncated = post.text.length > MAX && !expanded;
  const displayText = truncated ? post.text.slice(0, MAX) + "…" : post.text;

  // Effective party: tracked actors use real party, others use affinity
  const effectiveParty = post.is_tracked_actor ? post.party : (post.party || post.party_affinity);
  const pColor  = partyColor(effectiveParty);
  const pShort  = partyShort(effectiveParty);
  const initial = post.author_handle[0]?.toUpperCase() || "?";
  const sentColor = SENT_DOT[post.sentiment] || "#95a5a6";

  // Source badge config
  const SOURCE_CFG: Record<string, { label: string; bg: string; color: string }> = {
    keyword:  { label: "Anahtar Kelime", bg: "#2980b920", color: "#2980b9" },
    protest:  { label: "Protesto", bg: "#e67e2220", color: "#e67e22" },
    dataset:  { label: "", bg: "", color: "" },  // no badge for dataset
  };

  const handleLike = () => {
    setLiked((l) => !l);
    setLikeCount((c) => liked ? c - 1 : c + 1);
  };

  return (
    <article
      className="bsky-post"
      style={{
        borderBottom: "1px solid var(--bsky-border)",
        padding: "12px 16px",
        display: "flex",
        gap: 12,
        cursor: "pointer",
        transition: "background 0.1s",
      }}
      onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = "var(--bsky-hover)"; }}
      onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = "transparent"; }}
    >
      {/* Avatar */}
      <div style={{ flexShrink: 0 }}>
        <div style={{
          width: 48, height: 48, borderRadius: "50%",
          background: pColor,
          display: "flex", alignItems: "center", justifyContent: "center",
          color: "#fff", fontWeight: 700, fontSize: 20,
          fontFamily: "var(--font-sans, sans-serif)",
          userSelect: "none",
        }}>
          {initial}
        </div>
      </div>

      {/* Content */}
      <div style={{ flex: 1, minWidth: 0 }}>
        {/* Header line */}
        <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: "0 6px", marginBottom: 2 }}>
          <span style={{ fontWeight: 700, fontSize: 15, color: "var(--bsky-text)", lineHeight: 1.4 }}>
            {post.author_handle.replace(/\..+$/, "").replace(/-/g, " ")}
          </span>
          <span style={{ fontSize: 14, color: "var(--bsky-dim)" }}>@{post.author_handle}</span>
          <span style={{ fontSize: 14, color: "var(--bsky-dim)" }}>·</span>
          <span style={{ fontSize: 14, color: "var(--bsky-dim)" }}>{relTime(post.created_at)}</span>

          {/* Party badge (tracked actors) or affinity label (non-tracked) */}
          {post.is_tracked_actor && pShort && pShort !== "—" && (
            <span style={{
              marginLeft: 4,
              fontSize: 11, fontWeight: 600, fontFamily: "var(--font-mono, monospace)",
              background: pColor + "20", color: pColor,
              border: `1px solid ${pColor}40`,
              padding: "0px 6px", borderRadius: 4, lineHeight: "18px",
            }}>
              {pShort}
            </span>
          )}
          {!post.is_tracked_actor && post.affinity_label && (
            <span style={{
              marginLeft: 4,
              fontSize: 11, fontWeight: 500, fontFamily: "var(--font-mono, monospace)",
              background: pColor + "14", color: pColor,
              border: `1px dashed ${pColor}50`,
              padding: "0px 6px", borderRadius: 4, lineHeight: "18px",
            }}>
              {post.affinity_label}
            </span>
          )}

          {/* Milletvekili */}
          {post.isMilletvekili && (
            <span style={{
              fontSize: 10, fontWeight: 600, fontFamily: "var(--font-mono, monospace)",
              background: "var(--bsky-blue)20", color: "var(--bsky-blue)",
              border: "1px solid var(--bsky-blue)40",
              padding: "0px 6px", borderRadius: 4, lineHeight: "18px",
            }}>
              MV
            </span>
          )}

          {/* Source badge (keyword / protest) */}
          {SOURCE_CFG[post.source]?.label && (
            <span style={{
              fontSize: 10, fontWeight: 600, fontFamily: "var(--font-mono, monospace)",
              background: SOURCE_CFG[post.source].bg,
              color: SOURCE_CFG[post.source].color,
              border: `1px solid ${SOURCE_CFG[post.source].color}40`,
              padding: "0px 6px", borderRadius: 4, lineHeight: "18px",
            }}>
              {SOURCE_CFG[post.source].label}
            </span>
          )}

          {/* Hate speech warning */}
          {post.hate_speech === "Yes" && (
            <span style={{
              fontSize: 10, fontWeight: 600,
              background: "#e74c3c20", color: "#e74c3c",
              border: "1px solid #e74c3c40",
              padding: "0px 6px", borderRadius: 4, lineHeight: "18px",
              fontFamily: "var(--font-mono, monospace)",
            }}>
              ⚠ Nefret
            </span>
          )}
        </div>

        {/* Post text */}
        <div style={{ fontSize: 15, lineHeight: 1.6, color: "var(--bsky-text)", marginBottom: 10, wordBreak: "break-word" }}>
          {displayText}
          {truncated && (
            <button
              onClick={(e) => { e.stopPropagation(); setExpanded(true); }}
              style={{ background: "none", border: "none", cursor: "pointer", color: "var(--bsky-blue)", fontSize: 14, marginLeft: 4, padding: 0 }}
            >
              devamını gör
            </button>
          )}
        </div>

        {/* Sentiment indicator (subtle dot line) — only for dataset posts */}
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6, flexWrap: "wrap" }}>
          {post.sentiment ? (
            <>
              <span style={{ width: 8, height: 8, borderRadius: "50%", background: sentColor, display: "inline-block", flexShrink: 0 }} />
              <span style={{ fontSize: 12, color: "var(--bsky-dim)", fontFamily: "var(--font-mono, monospace)" }}>
                {SENT_TR[post.sentiment] || post.sentiment}
                {post.sentiment_scores && (
                  <span style={{ marginLeft: 4, opacity: 0.7 }}>
                    ({Math.round(parseFloat(post.sentiment_scores.split("|")[post.sentiment === "negative" ? 0 : post.sentiment === "neutral" ? 1 : 2] || "0") * 100)}%)
                  </span>
                )}
              </span>
            </>
          ) : null}

          {/* Keyword pill for non-dataset posts */}
          {post.keyword && (
            <span style={{
              fontSize: 11, fontFamily: "var(--font-mono, monospace)",
              background: "var(--bsky-border)", color: "var(--bsky-dim)",
              padding: "0px 7px", borderRadius: 4, lineHeight: "18px",
            }}>
              #{post.keyword}
            </span>
          )}
        </div>

        {/* Action row — Bluesky style */}
        <div style={{ display: "flex", gap: 28, color: "var(--bsky-dim)" }}>
          <ActionBtn icon={<ReplyIcon />} count={post.reply_count} />
          <ActionBtn icon={<RepostIcon />} count={post.repost_count} color="#27ae60" />
          <ActionBtn
            icon={<LikeIcon filled={liked} />}
            count={likeCount}
            color="#e74c3c"
            active={liked}
            onClick={(e) => { e.stopPropagation(); handleLike(); }}
          />
          <ActionBtn icon={<QuoteIcon />} />
          <ActionBtn icon={<MoreIcon />} />
        </div>
      </div>
    </article>
  );
}

/* ─── ActionBtn ─────────────────────────────────────────────────── */
function ActionBtn({
  icon, count, color, active, onClick,
}: {
  icon: React.ReactNode;
  count?: number;
  color?: string;
  active?: boolean;
  onClick?: (e: React.MouseEvent) => void;
}) {
  const [hover, setHover] = useState(false);
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: "flex", alignItems: "center", gap: 4,
        background: "none", border: "none", cursor: "pointer",
        color: active ? color : hover ? (color || "var(--bsky-blue)") : "var(--bsky-dim)",
        fontSize: 13, padding: 0,
        transition: "color 0.12s",
        fontFamily: "var(--font-mono, monospace)",
      }}
    >
      {icon}
      {count !== undefined && count > 0 && <span>{count}</span>}
    </button>
  );
}
