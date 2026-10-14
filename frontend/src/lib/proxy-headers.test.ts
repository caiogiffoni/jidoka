import { describe, expect, it, vi } from "vitest";

vi.mock("next/headers", () => ({ headers: vi.fn() }));

import {
  buildProxyHeaders,
  CLIENT_IP_HEADER,
  clientIpFrom,
  PROXY_SECRET_HEADER,
} from "./proxy-headers";

describe("clientIpFrom", () => {
  it("takes the first hop of x-forwarded-for", () => {
    const h = new Headers({ "x-forwarded-for": " 1.2.3.4 , 10.0.0.1" });
    expect(clientIpFrom(h)).toBe("1.2.3.4");
  });

  it("falls back to x-real-ip", () => {
    expect(clientIpFrom(new Headers({ "x-real-ip": "5.6.7.8" }))).toBe(
      "5.6.7.8",
    );
  });

  it("returns null when neither header is present", () => {
    expect(clientIpFrom(new Headers())).toBeNull();
  });
});

describe("buildProxyHeaders", () => {
  const source = new Headers({ "x-forwarded-for": "1.2.3.4" });

  it("forwards the client IP with the shared secret", () => {
    expect(buildProxyHeaders(source, "s3cret")).toEqual({
      [CLIENT_IP_HEADER]: "1.2.3.4",
      [PROXY_SECRET_HEADER]: "s3cret",
    });
  });

  it("sends nothing when no secret is configured", () => {
    expect(buildProxyHeaders(source, undefined)).toEqual({});
    expect(buildProxyHeaders(source, "")).toEqual({});
  });

  it("sends nothing when the client IP is unknown", () => {
    expect(buildProxyHeaders(new Headers(), "s3cret")).toEqual({});
  });
});
