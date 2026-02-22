import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";

const KW_PATH = path.join(process.cwd(), "..", "outputs", "political_keywords.json");

export async function GET() {
  if (!fs.existsSync(KW_PATH)) {
    return NextResponse.json({ keywords: [] });
  }
  const data = JSON.parse(fs.readFileSync(KW_PATH, "utf-8"));
  const kws: string[] = data.keywords || [];
  // Return top 20 keywords with mock post counts (seeded from index for consistency)
  const result = kws.slice(0, 20).map((kw: string, i: number) => ({
    keyword: kw,
    count: Math.max(50, 2000 - i * 80 + (kw.length * 7)),
  }));
  return NextResponse.json({ keywords: result });
}
