import { NextRequest, NextResponse } from "next/server";
import fs from "fs";
import path from "path";
import readline from "readline";

const OUTPUTS = path.join(process.cwd(), "..", "outputs");
const CSV_PATH          = path.join(OUTPUTS, "sentiment_results.csv");
const JSONL_RAW_PATH    = path.join(OUTPUTS, "all_posts_raw.jsonl");
const WEEKLY_PATH       = path.join(OUTPUTS, "weekly_search_results.jsonl");
const PROTEST_PATH      = path.join(OUTPUTS, "protest_posts.jsonl");

// ─── Party normalization ──────────────────────────────────────────────────────

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

// Protest/İmamoğlu keywords → strong CHP signal by context
const PROTEST_KWS = new Set([
  "imamoğlu", "ekrem imamoğlu", "saraçhane", "kent uzlaşısı", "diploma",
  "diploma iptali", "marmara üniversitesi", "istanbul üniversitesi protesto",
  "protesto", "cumhurbaşkanı adayı", "31 mart", "polis müdahalesi",
  "siyasi operasyon", "yargı bağımsızlığı", "hukuk dışı", "siyasi yargı",
  "tahliye", "siyasi tutuklama", "belediye başkanı tutuklandı",
]);

/**
 * Score-based party affinity for non-tracked actors.
 * Always returns a party name or "Diğer" — never empty.
 */
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
    "Bağımsız": 0,
  };

  // Keyword context: protest keywords → strong CHP signal
  if (PROTEST_KWS.has(kw)) scores["Cumhuriyet Halk Partisi"] += 4;

  // CHP signals
  for (const s of ["chp", "cumhuriyet halk", "kılıçdaroğlu", "özgür özel", "imamoğlu",
    "imamoglu", "yavaş", "saraçhane", "chp'li", "chp'nin", "chp'ye",
    "ana muhalefet", "millet ittifakı", "istanbul büyükşehir",
    "ibb başkanı", "kent uzlaşısı", "diploma iptali",
    "yargı bağımsızlığı", "siyasi operasyon", "hukuk dışı", "siyasi tutuklama"]) {
    if (t.includes(s)) scores["Cumhuriyet Halk Partisi"] += 2;
  }

  // AKP signals
  for (const s of ["akp", "ak parti", "adalet ve kalkınma", "erdoğan", "cumhur ittifakı",
    "iktidar", "akp'li", "akp'nin", "ak parti'nin", "tayyip"]) {
    if (t.includes(s)) scores["Adalet ve Kalkınma Partisi"] += 2;
  }

  // MHP signals
  for (const s of ["mhp", "bahçeli", "milliyetçi hareket", "ülkücü", "bozkurt",
    "mhp'li", "mhp'nin"]) {
    if (t.includes(s)) scores["Milliyetçi Hareket Partisi"] += 2;
  }

  // DEM/HDP signals
  for (const s of ["dem parti", "hdp", "demirtaş", "halkların eşitlik",
    "yeşil sol", "dem'li", "hdp'li", "kürt siyaseti"]) {
    if (t.includes(s)) scores["Halkların Eşitlik ve Demokrasi Partisi"] += 2;
  }

  // İYİ signals
  for (const s of ["iyi parti", "akşener", "iyi parti'nin", "iyili"]) {
    if (t.includes(s)) scores["İYİ Parti"] += 2;
  }

  // Yeni Yol signals
  for (const s of ["yeni yol", "yeni yol partisi", "yyp"]) {
    if (t.includes(s)) scores["Yeni Yol"] += 2;
  }

  // Pick highest score
  let best = ""; let bestScore = 0;
  for (const [party, score] of Object.entries(scores)) {
    if (score > bestScore) { bestScore = score; best = party; }
  }
  return best || "Diğer";  // always return something
}

// Human-readable affinity label (Turkish grammar)
const AFFINITY_LABEL: Record<string, string> = {
  "Cumhuriyet Halk Partisi":                "CHP'ye yakın",
  "Adalet ve Kalkınma Partisi":             "AKP'ye yakın",
  "Milliyetçi Hareket Partisi":             "MHP'ye yakın",
  "Halkların Eşitlik ve Demokrasi Partisi": "DEM'e yakın",
  "İYİ Parti":                              "İYİ'ye yakın",
  "Yeni Yol":                               "YY'ye yakın",
  "Bağımsız":                               "Bağımsız",
  "Diğer":                                  "Diğer",
};

function makeAffinityLabel(affinity: string, isTracked: boolean): string {
  if (isTracked) return "";
  return AFFINITY_LABEL[affinity] || "Diğer";
}

/**
 * Returns true if text is likely Turkish.
 * ş, ğ, ı (undotted-i) are unique to Turkish and a few other languages.
 */
function isTurkish(text: string): boolean {
  if (!text || text.length < 10) return true;
  if (/[şğı]/.test(text)) return true;
  if (/[İ]/.test(text)) return true;  // capital dotted I
  if (/\b(türkiye|türk|istanbul|ankara|cumhurbaşkan|milletvekili|meclis|belediye|protesto|gözaltı|tutuklama|seçim|hükümet|muhalefet)\b/i.test(text)) return true;
  if (/[çöü]/i.test(text) && /\b(bir|bu|ve|ile|de|da|ki|için|olan|var|daha)\b/i.test(text)) return true;
  return false;
}

// ─── CSV parser ───────────────────────────────────────────────────────────────

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

// ─── JSONL loaders ────────────────────────────────────────────────────────────

async function loadJSONL(filePath: string): Promise<Record<string, unknown>[]> {
  const records: Record<string, unknown>[] = [];
  if (!fs.existsSync(filePath)) return records;
  const fileStream = fs.createReadStream(filePath);
  const rl = readline.createInterface({ input: fileStream, crlfDelay: Infinity });
  for await (const line of rl) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    try {
      records.push(JSON.parse(trimmed));
    } catch {
      // skip malformed lines
    }
  }
  return records;
}

// ─── Cache ────────────────────────────────────────────────────────────────────

interface CacheEntry<T> { data: T; time: number; }
let rawTextCache: CacheEntry<Map<string, string>> | null = null;
let weeklyCache: CacheEntry<Record<string, unknown>[]> | null = null;
let protestCache: CacheEntry<Record<string, unknown>[]> | null = null;
const CACHE_TTL = 5 * 60 * 1000;  // 5 minutes

async function getRawTexts(): Promise<Map<string, string>> {
  if (rawTextCache && Date.now() - rawTextCache.time < CACHE_TTL) return rawTextCache.data;
  const records = await loadJSONL(JSONL_RAW_PATH);
  const map = new Map<string, string>();
  for (const r of records) {
    const uri = r.uri as string;
    const text = r.text as string;
    if (uri && text) map.set(uri, text);
  }
  rawTextCache = { data: map, time: Date.now() };
  return map;
}

async function getWeeklyRecords(): Promise<Record<string, unknown>[]> {
  if (weeklyCache && Date.now() - weeklyCache.time < CACHE_TTL) return weeklyCache.data;
  const data = await loadJSONL(WEEKLY_PATH);
  weeklyCache = { data, time: Date.now() };
  return data;
}

async function getProtestRecords(): Promise<Record<string, unknown>[]> {
  if (protestCache && Date.now() - protestCache.time < CACHE_TTL) return protestCache.data;
  const data = await loadJSONL(PROTEST_PATH);
  protestCache = { data, time: Date.now() };
  return data;
}

// ─── Unified post shape ───────────────────────────────────────────────────────

interface UnifiedPost {
  uri: string;
  author_handle: string;
  party: string;
  party_normalized: string;
  party_affinity: string;       // inferred affinity for non-tracked actors
  affinity_label: string;       // human label, e.g. "CHP'ye yakın"
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
  keyword: string;              // matched keyword (if from search)
  is_tracked_actor: boolean;
}

const PARTY_SHORT_MAP: Record<string, string> = {
  "Cumhuriyet Halk Partisi": "CHP",
  "Adalet ve Kalkınma Partisi": "AKP",
  "Milliyetçi Hareket Partisi": "MHP",
  "Halkların Eşitlik ve Demokrasi Partisi": "DEM",
  "İYİ Parti": "İYİ",
  "Yeni Yol": "YY",
  "Bağımsız": "Bağ.",
};

// ─── Load dataset posts (from CSV + raw JSONL) ───────────────────────────────

async function loadDatasetPosts(fullTexts: Map<string, string>): Promise<UnifiedPost[]> {
  if (!fs.existsSync(CSV_PATH)) return [];
  const csvContent = fs.readFileSync(CSV_PATH, "utf-8").replace(/^\uFEFF/, "");
  const lines = csvContent.split("\n").filter((l) => l.trim());
  if (lines.length < 2) return [];

  const headers = parseCSVLine(lines[0]).map((h) => h.trim());
  const posts: UnifiedPost[] = [];

  for (let i = 1; i < lines.length; i++) {
    const row = parseCSVLine(lines[i]);
    if (row.length < headers.length) continue;
    const obj: Record<string, string> = {};
    headers.forEach((h, idx) => { obj[h] = (row[idx] || "").trim(); });

    const text = fullTexts.get(obj.uri) || obj.text_preview || "";
    const party = obj.party || "";
    posts.push({
      uri:              obj.uri,
      author_handle:    obj.author_handle,
      party,
      party_normalized: normalizeParty(party),
      party_affinity:   "",
      affinity_label:   "",
      alliance:         obj.alliance || "",
      political_stance: obj.political_stance || "",
      isMilletvekili:   obj.isMilletvekili === "True",
      text,
      created_at:       obj.created_at,
      like_count:       parseInt(obj.like_count) || 0,
      reply_count:      0,
      repost_count:     0,
      sentiment:        obj.sentiment || "",
      sentiment_scores: obj.sentiment_scores || "",
      hate_speech:      obj.hate_speech || "",
      hs_score:         parseFloat(obj.hs_score) || 0,
      source:           "dataset",
      keyword:          "",
      is_tracked_actor: true,
    });
  }
  return posts;
}

// ─── Load keyword/protest posts (from JSONL) ─────────────────────────────────

function jsonlRecordsToUnifiedPosts(
  records: Record<string, unknown>[],
  sourceLabel: "keyword" | "protest",
): UnifiedPost[] {
  // Deduplicate by URI
  const seen = new Set<string>();
  const posts: UnifiedPost[] = [];

  for (const r of records) {
    const uri = (r.uri as string) || "";
    if (!uri || seen.has(uri)) continue;
    seen.add(uri);

    const text        = (r.text as string) || "";
    const keyword     = (r.keyword as string) || "";
    const isTracked   = Boolean(r.is_tracked_actor);
    const party       = (r.party as string) || "";

    // Skip non-Turkish posts
    if (!isTurkish(text)) continue;

    const affinity    = isTracked ? (party || "Diğer") : inferPartyAffinity(text, keyword);
    const affinityLabel = makeAffinityLabel(affinity, isTracked);

    posts.push({
      uri,
      author_handle:    (r.author_handle as string) || "",
      party:            party,
      party_normalized: party ? normalizeParty(party) : normalizeParty(affinity),
      party_affinity:   affinity,
      affinity_label:   affinityLabel,
      alliance:         (r.alliance as string) || "",
      political_stance: (r.political_stance as string) || "",
      isMilletvekili:   Boolean(r.isMilletvekili),
      text,
      created_at:       (r.created_at as string) || "",
      like_count:       (r.like_count as number) || 0,
      reply_count:      (r.reply_count as number) || 0,
      repost_count:     (r.repost_count as number) || 0,
      sentiment:        "",
      sentiment_scores: "",
      hate_speech:      "",
      hs_score:         0,
      source:           sourceLabel,
      keyword,
      is_tracked_actor: isTracked,
    });
  }
  return posts;
}

// ─── Main handler ─────────────────────────────────────────────────────────────

export async function GET(req: NextRequest) {
  const { searchParams } = req.nextUrl;
  const days        = parseInt(searchParams.get("days") || "0");
  const party       = searchParams.get("party") || "";
  const sentiment   = searchParams.get("sentiment") || "";
  const hate_speech = searchParams.get("hate_speech") || "";
  const search      = (searchParams.get("search") || "").toLowerCase();
  const limit       = Math.min(parseInt(searchParams.get("limit") || "50"), 200);
  const offset      = parseInt(searchParams.get("offset") || "0");
  // feed: "all" | "dataset" | "keyword" | "protest"
  const feed        = searchParams.get("feed") || "all";

  const cutoff = days > 0 ? Date.now() - days * 24 * 60 * 60 * 1000 : 0;

  // Load data sources in parallel
  const [fullTexts, weeklyRecords, protestRecords] = await Promise.all([
    (feed === "all" || feed === "dataset" || feed === "keyword") ? getRawTexts() : Promise.resolve(new Map<string, string>()),
    (feed === "all" || feed === "keyword") ? getWeeklyRecords() : Promise.resolve([]),
    (feed === "all" || feed === "protest") ? getProtestRecords() : Promise.resolve([]),
  ]);

  // Build unified post arrays
  let allPosts: UnifiedPost[] = [];

  if (feed === "all" || feed === "dataset") {
    const datasetPosts = await loadDatasetPosts(fullTexts);
    allPosts.push(...datasetPosts);
  }

  if (feed === "all" || feed === "keyword") {
    // Exclude posts already included from protest category
    const protestUris = new Set(protestRecords.map((r) => r.uri as string));
    const weeklyOnly = weeklyRecords.filter((r) => {
      const cat = (r.feed_category as string) || "";
      return cat !== "protest" && !protestUris.has(r.uri as string);
    });
    allPosts.push(...jsonlRecordsToUnifiedPosts(weeklyOnly, "keyword"));
  }

  if (feed === "all" || feed === "protest") {
    allPosts.push(...jsonlRecordsToUnifiedPosts(protestRecords, "protest"));
    // Also include protest-tagged records from weekly search
    if (feed === "all") {
      const protestFromWeekly = weeklyRecords.filter((r) => (r.feed_category as string) === "protest");
      const protestUris = new Set(protestRecords.map((r) => r.uri as string));
      const extras = protestFromWeekly.filter((r) => !protestUris.has(r.uri as string));
      allPosts.push(...jsonlRecordsToUnifiedPosts(extras as Record<string, unknown>[], "protest"));
    }
  }

  // Deduplicate by URI (dataset wins over keyword wins over protest)
  const seenUris = new Set<string>();
  const deduped: UnifiedPost[] = [];
  for (const p of allPosts) {
    if (!p.uri || seenUris.has(p.uri)) continue;
    seenUris.add(p.uri);
    deduped.push(p);
  }

  // ─── Apply filters ───────────────────────────────────────────────────────

  const filtered = deduped.filter((p) => {
    // Time filter
    if (cutoff > 0) {
      const ts = new Date(p.created_at).getTime();
      if (isNaN(ts) || ts < cutoff) return false;
    }

    // Party filter — check both actual party and inferred affinity
    const effectiveParty = p.party || p.party_affinity;
    const effectiveNorm  = normalizeParty(effectiveParty);
    if (party) {
      if (party !== "Diğer") {
        if (effectiveParty !== party) return false;
      } else {
        if (MAIN_PARTIES.has(effectiveParty)) return false;
      }
    }

    // Sentiment (only dataset posts have sentiment)
    if (sentiment && p.sentiment !== sentiment) return false;

    // Hate speech (only dataset posts have labels)
    if (hate_speech && p.hate_speech !== hate_speech) return false;

    // Full-text search
    if (search) {
      const textMatch   = p.text.toLowerCase().includes(search);
      const handleMatch = p.author_handle.toLowerCase().includes(search);
      const kwMatch     = p.keyword.toLowerCase().includes(search);
      if (!textMatch && !handleMatch && !kwMatch) return false;
    }

    return true;
  });

  // Sort newest first
  filtered.sort((a, b) =>
    new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  );

  const total     = filtered.length;
  const paginated = filtered.slice(offset, offset + limit);

  return NextResponse.json({ posts: paginated, total, offset, limit });
}
