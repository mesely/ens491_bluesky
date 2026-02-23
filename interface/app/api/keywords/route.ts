import { NextRequest, NextResponse } from "next/server";
import fs from "fs";
import path from "path";
import readline from "readline";

const OUTPUTS     = path.join(process.cwd(), "..", "outputs");
const KW_PATH     = path.join(OUTPUTS, "political_keywords.json");
const SEARCH_KW_PATH = path.join(OUTPUTS, "search_keywords.json");
const WEEKLY_PATH = path.join(OUTPUTS, "weekly_search_results.jsonl");
const PROTEST_PATH = path.join(OUTPUTS, "protest_posts.jsonl");

// Protest-specific keywords always pinned to the top of the Gündem list
const PROTEST_PINNED = [
  "ekrem imamoğlu",
  "saraçhane",
  "protesto",
  "diploma",
  "marmara üniversitesi",
  "kent uzlaşısı",
  "imamoğlu",
  "polis müdahalesi",
];

async function countKeywordsFromJSONL(filePath: string): Promise<Map<string, number>> {
  const counts = new Map<string, number>();
  if (!fs.existsSync(filePath)) return counts;
  const fileStream = fs.createReadStream(filePath);
  const rl = readline.createInterface({ input: fileStream, crlfDelay: Infinity });
  for await (const line of rl) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    try {
      const obj = JSON.parse(trimmed);
      const kw = (obj.keyword as string || "").trim().toLowerCase();
      if (kw) counts.set(kw, (counts.get(kw) || 0) + 1);
    } catch { /* skip */ }
  }
  return counts;
}

// Cache
let cache: { data: { keyword: string; count: number }[]; time: number } | null = null;
const CACHE_TTL = 10 * 60 * 1000;  // 10 minutes

export async function GET(req: NextRequest) {
  const feed = req.nextUrl.searchParams.get("feed") || "all";

  // Use cache unless requesting protest-specific feed
  if (cache && Date.now() - cache.time < CACHE_TTL && feed !== "protest") {
    return NextResponse.json({ keywords: cache.data });
  }

  // Load real counts from JSONL files
  const [weeklyCounts, protestCounts] = await Promise.all([
    countKeywordsFromJSONL(WEEKLY_PATH),
    countKeywordsFromJSONL(PROTEST_PATH),
  ]);

  // Merge counts
  const merged = new Map<string, number>();
  for (const [kw, cnt] of weeklyCounts) merged.set(kw, (merged.get(kw) || 0) + cnt);
  for (const [kw, cnt] of protestCounts) merged.set(kw, (merged.get(kw) || 0) + cnt);

  if (feed === "protest") {
    // Return protest-specific keyword counts only
    const protestResult = PROTEST_PINNED.map((kw) => ({
      keyword: kw,
      count: protestCounts.get(kw) || weeklyCounts.get(kw) || 0,
    })).filter((k) => k.count > 0 || PROTEST_PINNED.includes(k.keyword));

    // Add any additional protest keywords with counts
    for (const [kw, cnt] of protestCounts) {
      if (!PROTEST_PINNED.includes(kw)) {
        protestResult.push({ keyword: kw, count: cnt });
      }
    }
    protestResult.sort((a, b) => b.count - a.count);
    return NextResponse.json({ keywords: protestResult.slice(0, 25) });
  }

  // General feed: combine political_keywords.json with real counts
  const basePath = fs.existsSync(SEARCH_KW_PATH) ? SEARCH_KW_PATH : KW_PATH;
  if (!fs.existsSync(basePath)) {
    // Fall back to protest + merged counts
    const result = Array.from(merged.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 20)
      .map(([keyword, count]) => ({ keyword, count }));
    return NextResponse.json({ keywords: result });
  }

  const data = JSON.parse(fs.readFileSync(basePath, "utf-8"));
  const baseKws: string[] = data.keywords || [];

  // Pin protest keywords first, then fill from base list.
  const pinned = PROTEST_PINNED.filter((kw) => (merged.get(kw) || 0) > 0);
  const remaining = baseKws
    .filter((kw) => !PROTEST_PINNED.includes(kw))
    .slice(0, Math.max(0, 30 - pinned.length));

  const ordered = [
    ...pinned.map((kw) => ({
      keyword: kw,
      count: merged.get(kw) || 0,
    })),
    ...remaining.map((kw: string) => ({
      keyword: kw,
      count: merged.get(kw) || 0,
    })),
  ];

  // Add counted keywords that are not in the curated base list.
  const inOrdered = new Set(ordered.map((r) => r.keyword.toLowerCase()));
  const extras = Array.from(merged.entries())
    .filter(([kw]) => !inOrdered.has(kw.toLowerCase()))
    .sort((a, b) => b[1] - a[1])
    .slice(0, 20)
    .map(([keyword, count]) => ({ keyword, count }));
  const result = [...ordered, ...extras]
    .sort((a, b) => b.count - a.count)
    .slice(0, 30);

  if (feed !== "protest") {
    cache = { data: result, time: Date.now() };
  }
  return NextResponse.json({ keywords: result });
}
