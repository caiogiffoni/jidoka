// @vitest-environment node
import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

vi.mock("@/app/actions", () => ({
  exchangeOAuthCode: vi.fn(),
}));

import { exchangeOAuthCode } from "@/app/actions";
import { GET } from "./route";

function callback(query: string) {
  return GET(new NextRequest(`http://localhost:3000/oauth/callback?${query}`));
}

describe("GET /oauth/callback", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("exchanges the code and redirects to /board without the code", async () => {
    vi.mocked(exchangeOAuthCode).mockResolvedValue({ ok: true });

    const response = await callback("code=one-time-code");

    expect(exchangeOAuthCode).toHaveBeenCalledWith("one-time-code");
    expect(response.status).toBe(303);
    const location = response.headers.get("location")!;
    expect(new URL(location).pathname).toBe("/board");
    expect(location).not.toContain("one-time-code");
    expect(response.headers.get("referrer-policy")).toBe("no-referrer");
    expect(response.headers.get("cache-control")).toBe("no-store");
  });

  it("never accepts a token straight from the URL", async () => {
    const response = await callback("token=some.jwt.value");

    expect(exchangeOAuthCode).not.toHaveBeenCalled();
    expect(response.headers.get("location")).toBe(
      "http://localhost:3000/login?error=oauth_failed",
    );
  });

  it("redirects to login when the exchange fails", async () => {
    vi.mocked(exchangeOAuthCode).mockResolvedValue({
      ok: false,
      error: "exchange_failed",
    });

    const response = await callback("code=used-code");

    const location = response.headers.get("location")!;
    expect(location).toBe("http://localhost:3000/login?error=exchange_failed");
    expect(location).not.toContain("used-code");
  });

  it("passes known backend error codes through to login", async () => {
    const response = await callback("error=account_exists_password");

    expect(exchangeOAuthCode).not.toHaveBeenCalled();
    expect(response.headers.get("location")).toBe(
      "http://localhost:3000/login?error=account_exists_password",
    );
  });

  it("collapses unknown error text to a generic code", async () => {
    const response = await callback(
      `error=${encodeURIComponent("<script>alert(1)</script>")}`,
    );

    expect(response.headers.get("location")).toBe(
      "http://localhost:3000/login?error=oauth_failed",
    );
  });
});
