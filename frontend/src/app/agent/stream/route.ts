import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import { AUTH_COOKIE } from "@/lib/auth";
import { BACKEND_URL } from "@/lib/api";
import { proxyHeaders } from "@/lib/proxy-headers";

export async function POST(request: NextRequest) {
  const cookieStore = await cookies();
  const token = cookieStore.get(AUTH_COOKIE)?.value;

  if (!token) {
    return NextResponse.json({ detail: "unauthorized" }, { status: 401 });
  }

  let backendRes: Response;
  try {
    backendRes = await fetch(`${BACKEND_URL}/agent/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(await proxyHeaders()),
        Authorization: `Bearer ${token}`,
      },
      body: await request.text(),
      // Cancel the upstream agent run when the browser aborts (unmount, new send).
      signal: request.signal,
    });
  } catch (err) {
    if (request.signal.aborted) {
      // Client is gone; nobody reads this response.
      return new NextResponse(null, { status: 499 });
    }
    console.error("agent stream proxy failed", err);
    return NextResponse.json(
      { detail: "Agent backend is unreachable" },
      { status: 502 },
    );
  }

  return new NextResponse(backendRes.body, {
    status: backendRes.status,
    statusText: backendRes.statusText,
    headers: {
      "Content-Type":
        backendRes.headers.get("Content-Type") ?? "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    },
  });
}
