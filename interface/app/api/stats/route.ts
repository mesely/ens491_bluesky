import { NextRequest, NextResponse } from "next/server";
import fs from "fs";
import path from "path";

const OUTPUTS = path.join(process.cwd(), "..", "outputs");
const CSV_PATH = path.join(OUTPUTS, "sentiment_results.csv");

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

export async function GET(req: NextRequest) {
  const { searchParams } = req.nextUrl;
  const days = parseInt(searchParams.get("days") || "0");
  const party = searchParams.get("party") || "";
  const sentiment = searchParams.get("sentiment") || "";
  const hate_speech = searchParams.get("hate_speech") || "";
  const search = (searchParams.get("search") || "").toLowerCase();

  if (!fs.existsSync(CSV_PATH)) {
    return NextResponse.json({ error: "Data not found" }, { status: 404 });
  }

  const csv = fs.readFileSync(CSV_PATH, "utf-8").replace(/^\uFEFF/, "");
  const lines = csv.split("\n").filter((l) => l.trim());
  if (lines.length < 2) return NextResponse.json({ total: 0 });

  const headers = parseCSVLine(lines[0]).map((h) => h.trim());
  const cutoff = days > 0 ? Date.now() - days * 24 * 60 * 60 * 1000 : 0;

  const byParty: Record<string, number> = {};
  const bySentiment: Record<string, number> = { positive: 0, neutral: 0, negative: 0 };
  const byHateSpeech: Record<string, number> = { Yes: 0, No: 0 };
  let total = 0;

  for (let i = 1; i < lines.length; i++) {
    const row = parseCSVLine(lines[i]);
    if (row.length < headers.length) continue;
    const obj: Record<string, string> = {};
    headers.forEach((h, idx) => { obj[h] = (row[idx] || "").trim(); });

    if (cutoff > 0) {
      const ts = new Date(obj.created_at).getTime();
      if (isNaN(ts) || ts < cutoff) continue;
    }

    const pNorm = MAIN_PARTIES.has(obj.party) ? obj.party : "Diğer";
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

  return NextResponse.json({ total, byParty, bySentiment, byHateSpeech });
}
