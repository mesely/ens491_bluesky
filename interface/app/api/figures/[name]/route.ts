import { NextRequest, NextResponse } from "next/server";
import fs from "fs";
import path from "path";

const FIGURES = path.join(process.cwd(), "..", "outputs", "figures");

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ name: string }> }
) {
  const { name } = await params;

  // Security: only allow alphanumeric, underscore, hyphen, dot filenames
  if (!/^[\w\-. ]+$/.test(name)) {
    return new NextResponse("Invalid filename", { status: 400 });
  }

  const filePath = path.join(FIGURES, name);

  if (!fs.existsSync(filePath)) {
    return new NextResponse("Not found", { status: 404 });
  }

  const ext = path.extname(name).toLowerCase();
  const mimeTypes: Record<string, string> = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".html": "text/html",
    ".svg": "image/svg+xml",
  };
  const contentType = mimeTypes[ext] || "application/octet-stream";

  const buf = fs.readFileSync(filePath);
  return new NextResponse(buf, {
    headers: {
      "Content-Type": contentType,
      "Cache-Control": "public, max-age=300",
    },
  });
}
