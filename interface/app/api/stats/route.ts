import { NextRequest, NextResponse } from "next/server";
import fs from "fs";
import path from "path";
import readline from "readline";

const OUTPUTS      = path.join(process.cwd(), "..", "outputs");
const CSV_PATH     = path.join(OUTPUTS, "sentiment_results.csv");
const WEEKLY_PATH  = path.join(OUTPUTS, "weekly_search_results.jsonl");
const PROTEST_PATH = path.join(OUTPUTS, "protest_posts.jsonl");
const EXCLUDED_HANDLES = new Set(["omercelik.com"]);

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
  "Muhalif",
  "İktidar Yanlısı",
  "Tarafsız/Haber",
]);

function normalizeParty(p: string): string {
  return MAIN_PARTIES.has(p) ? p : "Diğer";
}

const PROTEST_KWS_STATS = new Set([
  "imamoğlu", "ekrem imamoğlu", "saraçhane", "kent uzlaşısı", "diploma",
  "diploma iptali", "protesto", "cumhurbaşkanı adayı", "31 mart",
  "polis müdahalesi", "siyasi operasyon", "yargı bağımsızlığı",
  "tahliye", "siyasi tutuklama",
]);

const PARTY_TERMS_STATS: Record<string, string[]> = {
  "Cumhuriyet Halk Partisi": ["chp", "cumhuriyet halk", "özgür özel", "kılıçdaroğlu", "imamoğlu", "yavaş", "saraçhane"],
  "Adalet ve Kalkınma Partisi": ["akp", "ak parti", "adalet ve kalkınma", "erdoğan", "tayyip", "cumhur ittifakı"],
  "Milliyetçi Hareket Partisi": ["mhp", "bahçeli", "milliyetçi hareket", "ülkücü"],
  "Halkların Eşitlik ve Demokrasi Partisi": ["dem parti", "hdp", "demirtaş", "halkların eşitlik", "yeşil sol"],
  "İYİ Parti": ["iyi parti", "akşener", "müsavat dervişoğlu"],
  "Yeni Yol": ["yeni yol", "deva", "gelecek partisi", "saadet partisi"],
};
const NEGATIVE_WORDS_STATS = ["faşist", "fascist", "yıkılacak", "istifa", "rezalet", "yolsuz", "hırsız", "diktatör", "otoriter", "hukuksuz"];
const POSITIVE_WORDS_STATS = ["destek", "tebrik", "başarı", "helal", "yanındayız", "güveniyoruz"];
const NEWS_WORDS_STATS = ["haber", "son dakika", "ajans", "canlı yayın", "açıklama", "duyurdu"];

function localContextScoreStats(text: string, term: string): number {
  let score = 0;
  let idx = text.indexOf(term);
  while (idx >= 0) {
    const start = Math.max(0, idx - 36);
    const end = Math.min(text.length, idx + term.length + 36);
    const ctx = text.slice(start, end);
    const hasNeg = NEGATIVE_WORDS_STATS.some((w) => ctx.includes(w));
    const hasPos = POSITIVE_WORDS_STATS.some((w) => ctx.includes(w));
    if (hasNeg && !hasPos) score -= 2;
    else if (hasPos && !hasNeg) score += 2;
    else score += 1;
    idx = text.indexOf(term, idx + term.length);
  }
  return score;
}

function inferPartyAffinity(text: string, keyword: string): string {
  const t = (text || "").toLowerCase();
  const kw = (keyword || "").toLowerCase();

  const scores: Record<string, number> = {
    "Cumhuriyet Halk Partisi": 0,
    "Adalet ve Kalkınma Partisi": 0,
    "Milliyetçi Hareket Partisi": 0,
    "Halkların Eşitlik ve Demokrasi Partisi": 0,
    "İYİ Parti": 0,
    "Yeni Yol": 0,
  };

  if (PROTEST_KWS_STATS.has(kw)) scores["Cumhuriyet Halk Partisi"] += 4;
  for (const [party, terms] of Object.entries(PARTY_TERMS_STATS)) {
    for (const term of terms) {
      if (!t.includes(term)) continue;
      scores[party] += localContextScoreStats(t, term);
    }
  }

  let best = ""; let bestScore = 0;
  for (const [party, score] of Object.entries(scores)) {
    if (score > bestScore) { bestScore = score; best = party; }
  }
  if (best && bestScore >= 2) return best;
  const antiGov = /(\bakp\b|\bak parti\b|erdoğan|tayyip|cumhur ittifakı).*(faşist|fascist|istifa|yıkılacak|yikilacak|diktatör|otoriter|yolsuz|hırsız)|(faşist|fascist|istifa|yıkılacak|yikilacak|diktatör|otoriter|yolsuz|hırsız).*(\bakp\b|\bak parti\b|erdoğan|tayyip|cumhur ittifakı)/i.test(t);
  const proGov = /(\bakp\b|\bak parti\b|erdoğan|tayyip|cumhur ittifakı).*(destek|tebrik|başarı|helal|yanındayız|güveniyoruz)|(destek|tebrik|başarı|helal|yanındayız|güveniyoruz).*(\bakp\b|\bak parti\b|erdoğan|tayyip|cumhur ittifakı)/i.test(t);
  if (NEWS_WORDS_STATS.some((w) => t.includes(w))) return "Tarafsız/Haber";
  if (proGov) return "İktidar Yanlısı";
  if (antiGov) return "Muhalif";
  return "Diğer";
}

function isTurkish(text: string): boolean {
  if (!text || text.length < 10) return true;
  if (/[şğı]/.test(text)) return true;
  if (/[İ]/.test(text)) return true;
  if (/\b(türkiye|türk|istanbul|ankara|cumhurbaşkan|milletvekili|meclis|belediye|protesto|gözaltı|tutuklama|seçim|hükümet|muhalefet)\b/i.test(text)) return true;
  if (/[çöü]/i.test(text) && /\b(bir|bu|ve|ile|de|da|ki|için|olan|var|daha)\b/i.test(text)) return true;
  return false;
}

function isPoliticalLikely(text: string): boolean {
  if (!text) return false;
  return /\b(akp|ak parti|chp|mhp|dem parti|iyi parti|yeni yol|tbmm|meclis|milletvekili|seçim|sandık|iktidar|muhalefet|hükümet|cumhurbaşkan|parti|protesto|gözaltı|tutuklama|anayasa|anayasa değişikliği|yargı|mahkeme|belediye|ibb|imamoğlu|imamoglu|çözüm süreci|terörsüz türkiye|terörle mücadele|kayyum|akın gürlek|can atalay|ekonomi|enflasyon|asgari ücret|emekli maaşı|merkez bankası|faiz|ab|nato|gazze|israil|filistin|dış politika)\b/i.test(text);
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
      const authorHandle = ((r.author_handle as string) || "").toLowerCase();
      if (EXCLUDED_HANDLES.has(authorHandle)) continue;

      if (cutoff > 0) {
        const ts = new Date(r.created_at as string).getTime();
        if (isNaN(ts) || ts < cutoff) continue;
      }

      const text    = (r.text as string) || "";
      const keyword = (r.keyword as string) || "";
      const rawParty = (r.party as string) || "";
      const isTracked = Boolean(r.is_tracked_actor);

      // Skip non-Turkish posts
      if (!isTurkish(text)) continue;
      if (!isPoliticalLikely(text)) continue;

      const effectiveParty = isTracked
        ? (rawParty || "Diğer")
        : inferPartyAffinity(text, keyword);  // always non-empty
      const norm = normalizeParty(effectiveParty);

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
        if (EXCLUDED_HANDLES.has((obj.author_handle || "").toLowerCase())) continue;

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
        if (!isPoliticalLikely(obj.text_preview || "")) continue;

        byParty[pNorm] = (byParty[pNorm] || 0) + 1;
        if (obj.sentiment in bySentiment) bySentiment[obj.sentiment as keyof typeof bySentiment]++;
        if (obj.hate_speech in byHateSpeech) byHateSpeech[obj.hate_speech as keyof typeof byHateSpeech]++;
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
