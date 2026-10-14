import { NextResponse, type NextRequest } from "next/server";
import { exchangeOAuthCode } from "@/app/actions";
import { toOAuthErrorCode, type OAuthErrorCode } from "@/lib/oauth-errors";

// A route handler rather than a page: nothing renders here, so the one-time
// code in the URL never reaches client JS, page-view analytics, or a Referer
// header - the browser is immediately redirected to a code-free URL.
export const dynamic = "force-dynamic";

function redirectTo(request: NextRequest, path: string) {
  const response = NextResponse.redirect(new URL(path, request.url), 303);
  response.headers.set("Referrer-Policy", "no-referrer");
  response.headers.set("Cache-Control", "no-store");
  return response;
}

function loginError(request: NextRequest, code: OAuthErrorCode) {
  return redirectTo(request, `/login?error=${code}`);
}

export async function GET(request: NextRequest) {
  const params = request.nextUrl.searchParams;
  const error = params.get("error");
  if (error) return loginError(request, toOAuthErrorCode(error));

  const code = params.get("code");
  if (!code) return loginError(request, "oauth_failed");

  const result = await exchangeOAuthCode(code);
  if (!result.ok) return loginError(request, result.error);
  return redirectTo(request, "/board");
}
