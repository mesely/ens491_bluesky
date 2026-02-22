import { NextRequest, NextResponse } from "next/server";
import fs from "fs";
import path from "path";
import readline from "readline";

const OUTPUTS      = path.join(process.cwd(), "..", "outputs");
const CSV_PATH     = path.join(OUTPUTS, "sentiment_results.csv");
const WEEKLY_PATH  = path.join(OUTPUTS, "weekly_search_results.jsonl");
const PROTEST_PATH = path.join(OUTPUTS, "protest_posts.jsonl");

// ─── Helpers ──────────────────────────────────────────────────────────────────

function parseCSVLine(line: string): string[] {
  const result: string[] = [];
  let current = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const c = line[i];
    if (c === '"') { inQuotes = !inQuotes; }
    else if (c === "," && !inQuotes) { result.push(current); current = ""; }
    else { current += c; }
  }
  result.push(current);
  return result;
}

const MAIN_PARTIES = new Set([
  "Cumhuriyet Halk Partisi",
  "Adalet ve Kalkınma Partisi",
  "Milliyetçi Hareket Partisi",
  "Halkların Eşitlik ve Demokrasi Partisi",
  "İYİ Parti",
  "Yeni Yol",
  "Bağımsız",
]);

function normalizeParty(p: string): string {
  return MAIN_PARTIES.has(p) ? p : "Diğer";
}

function inferPartyAffinity(text: string, keyword: string): string {
  const t = (text || "").toLowerCase();
  const kw = (keyword || "").toLowerCase();
  if (
    t.includes("chp") || t.includes("cumhuriyet halk") ||
    t.includes("imamoğlu") || t.includes("imamoglu") ||
    t.includes("kılıçdaroğlu") || t.includes("özgür özel") ||
    t.includes("yavaş") || t.includes("saraçhane") ||
    kw.includes("imamoğlu") || kw.includes("saraçhane")
  ) return "Cumhuriyet Halk Partisi";
  if (t.includes("akp") || t.includes("ak parti") || t.includes("erdoğan"))
    return "Adalet ve Kalkınma Partisi";
  if (t.includes("mhp") || t.includes("bahçeli"))
    return "Milliyetçi Hareket Partisi";
  if (t.includes("dem parti") || t.includes("hdp") || t.includes("demirtaş"))
    return "Halkların Eşitlik ve Demokrasi Partisi";
  if (t.includes("iyi parti") || t.includes("akşener"))
    return "İYİ Parti";
  return "";
}

async function loadJSONLStats(
  filePath: string,
  cutoff: number,
  party: string,
  search: string,
  byParty: Record<string, number>,
  bySentiment: Record<string, number>,
  byHateSpeech: Record<string, number>,
): Promise<number> {
  let count = 0;
  if (!fs.existsSync(filePath)) return 0;
  const fileStream = fs.createReadStream(filePath);
  const rl = readline.createInterface({ input: fileStream, crlfDelay: Infinity });
  const seen = new Set<string>();

  for await (const line of rl) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    try {
      const r = JSON.parse(trimmed);
      const uri = r.uri as string;
      if (!uri || seen.has(uri)) continue;
      seen.add(uri);

      if (cutoff > 0) {
        const ts = new Date(r.created_at as string).getTime();
        if (isNaN(ts) || ts < cutoff) continue;
      }

      const text    = (r.text as string) || "";
      const keyword = (r.keyword as string) || "";
      const rawParty = (r.party as string) || "";
      const isTracked = Boolean(r.is_tracked_actor);
      const effectiveParty = isTracked ? rawParty : (rawParty || inferPartyAffinity(text, keyword));
      const norm = effectiveParty ? normalizeParty(effectiveParty) : "Diğer";

      if (party) {
        if (party !== "Diğer" && effectiveParty !== party) continue;
        if (party === "Diğer" && MAIN_PARTIES.has(effectiveParty)) continue;
      }

      if (search && !text.toLowerCase().includes(search)) continue;

      byParty[norm] = (byParty[norm] || 0) + 1;
      // No sentiment/hate speech for JSONL sources
      count++;
    } catch { /* skip */ }
  }
  return count;
}

// ─── Main handler ─────────────────────────────────────────────────────────────

export async function GET(req: NextRequest) {
  const { searchParams } = req.nextUrl;
  const days        = parseInt(searchParams.get("days") || "0");
  const party       = searchParams.get("party") || "";
  const sentiment   = searchParams.get("sentiment") || "";
  const hate_speech = searchParams.get("hate_speech") || "";
  const search      = (searchParams.get("search") || "").toLowerCase();
  const feed        = searchParams.get("feed") || "all";

  const cutoff = days > 0 ? Date.now() - days * 24 * 60 * 60 * 1000 : 0;

  const byParty: Record<string, number> = {};
  const bySentiment: Record<string, number> = { positive: 0, neutral: 0, negative: 0 };
  const byHateSpeech: Record<string, number> = { Yes: 0, No: 0 };
  let total = 0;

  // ─── Dataset (CSV) ────────────────────────────────────────────────────────
  if ((feed === "all" || feed === "dataset") && fs.existsSync(CSV_PATH)) {
    const csv = fs.readFileSync(CSV_PATH, "utf-8").replace(/^\uFEFF/, "");
    const lines = csv.split("\n").filter((l) => l.trim());
    if (lines.length >= 2) {
      const headers = parseCSVLine(lines[0]).map((h) => h.trim());
      for (let i = 1; i < lines.length; i++) {
        const row = parseCSVLine(lines[i]);
        if (row.length < headers.length) continue;
        const obj: Record<string, string> = {};
        headers.forEach((h, idx) => { obj[h] = (row[idx] || "").trim(); });

        if (cutoff > 0) {
          const ts = new Date(obj.created_at).getTime();
          if (isNaN(ts) || ts < cutoff) continue;
        }
        const pNorm = normalizeParty(obj.party);
        if (party && party !== "Diğer" && obj.party !== party) continue;
        if (party === "Diğer" && MAIN_PARTIES.has(obj.party)) continue;
        if (sentiment && obj.sentiment !== sentiment) continue;
        if (hate_speech && obj.hate_speech !== hate_speech) continue;
        if (search && !(obj.text_preview || "").toLowerCase().includes(search)) continue;

        byParty[pNorm] = (byParty[pNorm] || 0) + 1;
        if (obj.sentiment in bySentiment) bySentiment[obj.sentiment]++;
        if (obj.hate_speech in byHateSpeech) byHateSpeech[obj.hate_speech]++;
        total++;
      }
    }
  }

  // ─── Weekly keyword search (JSONL) ────────────────────────────────────────
  if (feed === "all" || feed === "keyword") {
    // Only include non-protest records
    const weeklyCount = await loadJSONLStats(
      WEEKLY_PATH, cutoff, party, search, byParty, bySentiment, byHateSpeech
    );
    if (!sentiment && !hate_speech) total += weeklyCount;
  }

  // ─── Protest posts (JSONL) ────────────────────────────────────────────────
  if (feed === "all" || feed === "protest") {
    const protestCount = await loadJSONLStats(
      PROTEST_PATH, cutoff, party, search, byParty, bySentiment, byHateSpeech
    );
    if (!sentiment && !hate_speech) total += protestCount;
  }

  return NextResponse.json({ total, byParty, bySentiment, byHateSpeech });
}
