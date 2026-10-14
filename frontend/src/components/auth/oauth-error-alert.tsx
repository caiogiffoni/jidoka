import { oauthErrorMessage } from "@/lib/oauth-errors";

/**
 * Shows a failed OAuth sign-in on the login page. Only fixed messages keyed
 * by a known error code are rendered - the raw `?error=` value never is.
 */
export function OAuthErrorAlert({ error }: { error?: string | string[] }) {
  const message = oauthErrorMessage(Array.isArray(error) ? error[0] : error);
  if (!message) return null;

  return (
    <p
      role="alert"
      className="mb-4 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive"
    >
      {message}
    </p>
  );
}
