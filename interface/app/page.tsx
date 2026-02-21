"use client";

import { useState, useEffect } from "react";
import SunumTab from "../components/SunumTab";
import FeedTab from "../components/FeedTab";

type Tab = "sunum" | "feed";

export default function Home() {
  const [activeTab, setActiveTab] = useState<Tab>("sunum");
  const [dark, setDark] = useState(false);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
  }, [dark]);

  return (
    <div style={{ background: "var(--bg)", color: "var(--text)", minHeight: "100vh" }}>
      {/* Top navigation */}
      <nav
        style={{
          position: "fixed", top: 0, left: 0, right: 0, zIndex: 100, height: 48,
          background: "rgba(var(--bg-rgb, 255,255,255), 0.97)",
          backgroundColor: "var(--bg)",
          borderBottom: "1px solid var(--border)",
          display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "0 32px",
          boxShadow: "0 1px 5px rgba(0,0,0,0.04)",
        }}
      >
        <div style={{ fontFamily: "var(--mono)", fontSize: 15, fontWeight: 500, letterSpacing: "0.14em", color: "var(--accent)", textTransform: "uppercase" }}>
          BlueSky / TR Siyasi
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 0 }}>
          {(["sunum", "feed"] as Tab[]).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              style={{
                fontFamily: "var(--mono)", fontSize: 14, fontWeight: 500,
                color: activeTab === tab ? "var(--text)" : "var(--muted)",
                background: "none", border: "none", cursor: "pointer",
                padding: "0 20px", height: 48,
                borderBottom: activeTab === tab ? "2px solid var(--accent)" : "2px solid transparent",
                borderLeft: "1px solid var(--border)",
                letterSpacing: "0.06em", textTransform: "uppercase",
                transition: "color 0.15s",
              }}
            >
              {tab === "sunum" ? "Sunum" : "Feed"}
            </button>
          ))}

          {/* Dark mode toggle */}
          <button
            onClick={() => setDark((d) => !d)}
            title={dark ? "Açık Tema" : "Koyu Tema"}
            style={{
              fontFamily: "var(--mono)", fontSize: 18, background: "none", border: "none",
              cursor: "pointer", padding: "0 16px", height: 48,
              borderLeft: "1px solid var(--border)", color: "var(--muted)",
            }}
          >
            {dark ? "☀" : "◐"}
          </button>
        </div>
      </nav>

      {/* Tab content */}
      <div style={{ paddingTop: 48 }}>
        {activeTab === "sunum" ? <SunumTab /> : <FeedTab />}
      </div>
    </div>
  );
}
