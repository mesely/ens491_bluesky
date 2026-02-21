import { NextRequest, NextResponse } from "next/server";
import fs from "fs";
import path from "path";
import readline from "readline";

const OUTPUTS = path.join(process.cwd(), "..", "outputs");
const CSV_PATH = path.join(OUTPUTS, "sentiment_results.csv");
const JSONL_PATH = path.join(OUTPUTS, "all_posts_raw.jsonl");

// Simple CSV line parser handling quoted fields
function parseCSVLine(line: string): string[] {
  const result: string[] = [];
  let current = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const c = line[i];
    if (c === '"') {
      inQuotes = !inQuotes;
    } else if (c === "," && !inQuotes) {
      result.push(current);
      current = "";
    } else {
      current += c;
    }
  }
  result.push(current);
  return result;
}

// Load full text from JSONL (indexed by URI)
async function loadFullTexts(): Promise<Map<string, string>> {
  const map = new Map<string, string>();
  if (!fs.existsSync(JSONL_PATH)) return map;
  const fileStream = fs.createReadStream(JSONL_PATH);
  const rl = readline.createInterface({ input: fileStream, crlfDelay: Infinity });
  for await (const line of rl) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    try {
      const obj = JSON.parse(trimmed);
      if (obj.uri && obj.text) map.set(obj.uri, obj.text);
    } catch {
      // skip malformed lines
    }
  }
  return map;
}

// Cache for full texts (avoids re-reading 9MB file every request)
let fullTextCache: Map<string, string> | null = null;
let cacheTime = 0;

async function getFullTexts(): Promise<Map<string, string>> {
  const now = Date.now();
  if (fullTextCache && now - cacheTime < 5 * 60 * 1000) return fullTextCache;
  fullTextCache = await loadFullTexts();
  cacheTime = now;
  return fullTextCache;
}

export async function GET(req: NextRequest) {
  const { searchParams } = req.nextUrl;
  const days = parseInt(searchParams.get("days") || "0");
  const party = searchParams.get("party") || "";
  const sentiment = searchParams.get("sentiment") || "";
  const hate_speech = searchParams.get("hate_speech") || "";
  const search = (searchParams.get("search") || "").toLowerCase();
  const limit = Math.min(parseInt(searchParams.get("limit") || "50"), 200);
  const offset = parseInt(searchParams.get("offset") || "0");

  if (!fs.existsSync(CSV_PATH)) {
    return NextResponse.json({ error: "Data file not found" }, { status: 404 });
  }

  const fullTexts = await getFullTexts();

  const csvContent = fs.readFileSync(CSV_PATH, "utf-8").replace(/^\uFEFF/, ""); // strip BOM
  const lines = csvContent.split("\n").filter((l) => l.trim());
  if (lines.length < 2) return NextResponse.json({ posts: [], total: 0 });

  const headers = parseCSVLine(lines[0]);

  const cutoff = days > 0 ? Date.now() - days * 24 * 60 * 60 * 1000 : 0;

  // Main parties list — others grouped as "Diğer"
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

  const posts = [];
  for (let i = 1; i < lines.length; i++) {
    const row = parseCSVLine(lines[i]);
    if (row.length < headers.length) continue;

    const obj: Record<string, string> = {};
    headers.forEach((h, idx) => { obj[h.trim()] = (row[idx] || "").trim(); });

    // Time filter
    if (cutoff > 0) {
      const ts = new Date(obj.created_at).getTime();
      if (isNaN(ts) || ts < cutoff) continue;
    }

    // Party filter
    const normalizedParty = normalizeParty(obj.party);
    if (party && party !== "Diğer" && obj.party !== party) continue;
    if (party === "Diğer" && MAIN_PARTIES.has(obj.party)) continue;

    // Sentiment filter
    if (sentiment && obj.sentiment !== sentiment) continue;

    // Hate speech filter
    if (hate_speech && obj.hate_speech !== hate_speech) continue;

    // Search filter (case-insensitive on text + handle)
    const text = fullTexts.get(obj.uri) || obj.text_preview || "";
    if (search && !text.toLowerCase().includes(search) && !obj.author_handle.toLowerCase().includes(search)) continue;

    posts.push({
      uri: obj.uri,
      author_handle: obj.author_handle,
      party: obj.party,
      party_normalized: normalizedParty,
      alliance: obj.alliance,
      political_stance: obj.political_stance,
      isMilletvekili: obj.isMilletvekili === "True",
      text: text || obj.text_preview,
      created_at: obj.created_at,
      like_count: parseInt(obj.like_count) || 0,
      reply_count: 0,  // not in CSV, available from JSONL
      repost_count: 0,
      sentiment: obj.sentiment,
      sentiment_scores: obj.sentiment_scores,
      hate_speech: obj.hate_speech,
      hs_score: parseFloat(obj.hs_score) || 0,
      source: obj.source,
    });
  }

  const total = posts.length;
  const paginated = posts.slice(offset, offset + limit);

  return NextResponse.json({ posts: paginated, total, offset, limit });
}
