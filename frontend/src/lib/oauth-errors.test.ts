import { describe, expect, it } from "vitest";
import {
  OAUTH_ERROR_MESSAGES,
  oauthErrorMessage,
  toOAuthErrorCode,
} from "./oauth-errors";

describe("oauth error codes", () => {
  it("maps known codes to their fixed message", () => {
    expect(oauthErrorMessage("account_exists_password")).toBe(
      OAUTH_ERROR_MESSAGES.account_exists_password,
    );
  });

  it("never reflects unknown text", () => {
    expect(oauthErrorMessage("<b>pwned</b>")).toBe(
      OAUTH_ERROR_MESSAGES.oauth_failed,
    );
    expect(toOAuthErrorCode("__proto__")).toBe("oauth_failed");
    expect(toOAuthErrorCode(["account_exists_password"])).toBe("oauth_failed");
  });

  it("returns null when there is no error", () => {
    expect(oauthErrorMessage(undefined)).toBeNull();
    expect(oauthErrorMessage("")).toBeNull();
  });
});
