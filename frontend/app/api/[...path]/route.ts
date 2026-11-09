import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

async function forward(request: NextRequest, context: { params: { path: string[] } }) {
  const base = process.env.API_URL;
  if (!base) {
    return NextResponse.json({ detail: "API_URL is not configured on this web service." }, { status: 503 });
  }
  const target = `${base.replace(/\/$/, "")}/api/${context.params.path.join("/")}${request.nextUrl.search}`;
  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  const response = await fetch(target, {
    method: request.method,
    headers,
    body: request.method === "GET" || request.method === "HEAD" ? undefined : await request.text(),
    cache: "no-store",
  });
  return new NextResponse(await response.arrayBuffer(), {
    status: response.status,
    headers: { "content-type": response.headers.get("content-type") || "application/json" },
  });
}

export const GET = forward;
export const POST = forward;
