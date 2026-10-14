// Fixed OAuth error codes the backend and the /oauth/callback route handler
// may put in `?error=`. The login page only ever renders these messages -
// never the raw query value - so a crafted link can't inject text.
// This file must not import any server-only APIs.
export const OAUTH_ERROR_MESSAGES = {
  account_exists_password:
    "An account with this email already exists - sign in with your password.",
  account_exists_oauth:
    "An account with this email already exists - sign in with the provider you used to create it.",
  email_unverified:
    "Your email isn't verified with that provider. Verify it there, then try again.",
  invalid_state:
    "Your sign-in attempt expired or was started in another browser. Please try again.",
  provider_request_failed:
    "We couldn't reach the sign-in provider. Please try again.",
  exchange_failed: "Sign-in link expired or was already used. Please try again.",
  oauth_failed: "Sign-in failed. Please try again.",
} as const;

export type OAuthErrorCode = keyof typeof OAUTH_ERROR_MESSAGES;

export function isOAuthErrorCode(value: unknown): value is OAuthErrorCode {
  return (
    typeof value === "string" &&
    Object.prototype.hasOwnProperty.call(OAUTH_ERROR_MESSAGES, value)
  );
}

/** Map any `?error=` value to a known code; unknown values collapse to the
 * generic `oauth_failed`. */
export function toOAuthErrorCode(value: unknown): OAuthErrorCode {
  return isOAuthErrorCode(value) ? value : "oauth_failed";
}

export function oauthErrorMessage(value: unknown): string | null {
  if (value === undefined || value === null || value === "") return null;
  return OAUTH_ERROR_MESSAGES[toOAuthErrorCode(value)];
}
