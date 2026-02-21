"use client";

import { useState } from "react";

export interface Post {
  uri: string;
  author_handle: string;
  party: string;
  party_normalized: string;
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
  source: string;
}

/* ─── Party colors ─────────────────────────────────────────────── */
const PARTY_COLORS: Record<string, string> = {
  "Cumhuriyet Halk Partisi":                "#E63946",
  "Adalet ve Kalkınma Partisi":             "#FFC300",
  "Milliyetçi Hareket Partisi":             "#C9A84C",
  "Halkların Eşitlik ve Demokrasi Partisi": "#2ECC71",
  "İYİ Parti":                              "#3498DB",
  "Yeni Yol":                               "#9B59B6",
  "Bağımsız":                               "#95A5A6",
};

const PARTY_SHORT: Record<string, string> = {
  "Cumhuriyet Halk Partisi":                "CHP",
  "Adalet ve Kalkınma Partisi":             "AKP",
  "Milliyetçi Hareket Partisi":             "MHP",
  "Halkların Eşitlik ve Demokrasi Partisi": "DEM",
  "İYİ Parti":                              "İYİ",
  "Yeni Yol":                               "YY",
  "Bağımsız":                               "Bağ.",
};

function partyColor(party: string) {
  return PARTY_COLORS[party] || "#7f8c8d";
}

function partyShort(party: string) {
  return PARTY_SHORT[party] || "Diğer";
}

/* ─── Sentiment chip ────────────────────────────────────────────── */
const SENTIMENT_STYLE: Record<string, { bg: string; text: string; label: string }> = {
  positive: { bg: "rgba(46,204,113,0.15)", text: "#1a8a4a", label: "Pozitif" },
  neutral:  { bg: "rgba(108,117,125,0.12)", text: "#495057",  label: "Nötr"   },
  negative: { bg: "rgba(220,53,69,0.12)",   text: "#c0392b",  label: "Negatif"},
};

/* ─── Time formatting ───────────────────────────────────────────── */
function relativeTime(iso: string): string {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return `${Math.floor(diff)}sn`;
  if (diff < 3600) return `${Math.floor(diff / 60)}dk`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}sa`;
  if (diff < 86400 * 30) return `${Math.floor(diff / 86400)}g`;
  return new Date(iso).toLocaleDateString("tr-TR", { day: "numeric", month: "short", year: "2-digit" });
}

/* ─── Avatar ────────────────────────────────────────────────────── */
function Avatar({ handle, party }: { handle: string; party: string }) {
  const letter = handle[0]?.toUpperCase() || "?";
  const color = partyColor(party);
  return (
    <div style={{
      width: 44, height: 44, borderRadius: "50%",
      background: color, color: "#fff",
      display: "flex", alignItems: "center", justifyContent: "center",
      fontFamily: "var(--mono)", fontWeight: 600, fontSize: 18,
      flexShrink: 0,
    }}>
      {letter}
    </div>
  );
}

/* ─── PostCard ──────────────────────────────────────────────────── */
export default function PostCard({ post }: { post: Post }) {
  const [expanded, setExpanded] = useState(false);
  const MAX_CHARS = 280;
  const truncated = post.text.length > MAX_CHARS && !expanded;
  const displayText = truncated ? post.text.slice(0, MAX_CHARS) + "…" : post.text;

  const s = SENTIMENT_STYLE[post.sentiment] || SENTIMENT_STYLE.neutral;
  const pColor = partyColor(post.party);
  const pShort = partyShort(post.party);

  return (
    <article style={{
      background: "var(--card-bg)",
      border: "1px solid var(--card-border)",
      borderRadius: 8,
      padding: "16px 20px",
      display: "flex",
      gap: 14,
      transition: "border-color 0.15s",
    }}
      onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.borderColor = "var(--accent)"; }}
      onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.borderColor = "var(--card-border)"; }}
    >
      <Avatar handle={post.author_handle} party={post.party} />

      <div style={{ flex: 1, minWidth: 0 }}>
        {/* Header row */}
        <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: 8, marginBottom: 6 }}>
          <span style={{ fontWeight: 600, fontSize: 15, color: "var(--text)" }}>
            @{post.author_handle}
          </span>

          {/* Party badge */}
          <span style={{
            fontFamily: "var(--mono)", fontSize: 11, fontWeight: 600,
            background: pColor + "22", color: pColor,
            border: `1px solid ${pColor}44`,
            padding: "1px 7px", borderRadius: 4,
          }}>
            {pShort}
          </span>

          {/* Milletvekili badge */}
          {post.isMilletvekili && (
            <span style={{
              fontFamily: "var(--mono)", fontSize: 10, fontWeight: 500,
              background: "rgba(160,113,42,0.12)", color: "var(--accent-d)",
              border: "1px solid rgba(160,113,42,0.3)",
              padding: "1px 7px", borderRadius: 4,
            }}>
              MV
            </span>
          )}

          {/* Hate speech flag */}
          {post.hate_speech === "Yes" && (
            <span style={{
              fontFamily: "var(--mono)", fontSize: 10, fontWeight: 600,
              background: "rgba(220,53,69,0.12)", color: "var(--red)",
              border: "1px solid rgba(220,53,69,0.3)",
              padding: "1px 7px", borderRadius: 4,
            }}>
              ⚠ Nefret
            </span>
          )}

          <span style={{ marginLeft: "auto", fontFamily: "var(--mono)", fontSize: 12, color: "var(--muted)" }}>
            {relativeTime(post.created_at)}
          </span>
        </div>

        {/* Post text */}
        <p style={{ fontSize: 15, lineHeight: 1.65, color: "var(--text)", marginBottom: 10, wordBreak: "break-word" }}>
          {displayText}
          {truncated && (
            <button onClick={() => setExpanded(true)} style={{
              background: "none", border: "none", cursor: "pointer",
              color: "var(--accent)", fontSize: 13, marginLeft: 4, padding: 0,
            }}>
              devamını gör
            </button>
          )}
        </p>

        {/* Footer row */}
        <div style={{ display: "flex", alignItems: "center", gap: 20, flexWrap: "wrap" }}>
          {/* Sentiment chip */}
          <span style={{
            fontFamily: "var(--mono)", fontSize: 11, fontWeight: 500,
            background: s.bg, color: s.text,
            padding: "2px 9px", borderRadius: 4,
          }}>
            {post.sentiment === "positive" ? "▲" : post.sentiment === "negative" ? "▼" : "▬"} {s.label}
          </span>

          {/* Engagement */}
          <div style={{ display: "flex", gap: 16, color: "var(--muted)", fontSize: 13, fontFamily: "var(--mono)" }}>
            {post.like_count > 0 && (
              <span title="Beğeni">♡ {post.like_count}</span>
            )}
            {post.reply_count > 0 && (
              <span title="Yanıt">↩ {post.reply_count}</span>
            )}
            {post.repost_count > 0 && (
              <span title="Yeniden paylaşım">↻ {post.repost_count}</span>
            )}
          </div>

          {/* Source tag */}
          <span style={{
            marginLeft: "auto",
            fontFamily: "var(--mono)", fontSize: 10, color: "var(--muted)",
            background: "var(--surface)", border: "1px solid var(--border)",
            padding: "1px 6px", borderRadius: 3,
          }}>
            {post.source === "actor_post" ? "hesap" : "arama"}
          </span>
        </div>
      </div>
    </article>
  );
}
