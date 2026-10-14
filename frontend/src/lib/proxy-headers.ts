import { headers } from "next/headers";

// All browser traffic reaches FastAPI through this Next server, so FastAPI
// only sees our IP. We forward the real client IP so its rate limits are per
// client, not global. FastAPI trusts the IP header only when the shared secret
// header matches its own INTERNAL_PROXY_SECRET; without a secret configured
// (local dev) nothing is sent and FastAPI falls back to the socket address.
export const CLIENT_IP_HEADER = "x-jidoka-client-ip";
export const PROXY_SECRET_HEADER = "x-internal-proxy-secret";

type HeaderSource = Pick<Headers, "get">;

/** First hop of x-forwarded-for, else x-real-ip. */
export function clientIpFrom(source: HeaderSource): string | null {
  const forwarded = source.get("x-forwarded-for")?.split(",")[0]?.trim();
  if (forwarded) return forwarded;
  const realIp = source.get("x-real-ip")?.trim();
  return realIp || null;
}

export function buildProxyHeaders(
  source: HeaderSource,
  secret: string | undefined = process.env.INTERNAL_PROXY_SECRET,
): Record<string, string> {
  if (!secret) return {};
  const ip = clientIpFrom(source);
  if (!ip) return {};
  return { [CLIENT_IP_HEADER]: ip, [PROXY_SECRET_HEADER]: secret };
}

/** Headers to attach to every server-side request to FastAPI. */
export async function proxyHeaders(): Promise<Record<string, string>> {
  try {
    return buildProxyHeaders(await headers());
  } catch {
    // Outside a request scope (e.g. build time): nothing to forward.
    return {};
  }
}
