import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { OAuthErrorAlert } from "./oauth-error-alert";
import { OAUTH_ERROR_MESSAGES } from "@/lib/oauth-errors";

describe("OAuthErrorAlert", () => {
  it("renders nothing without an error", () => {
    const { container } = render(<OAuthErrorAlert />);
    expect(container).toBeEmptyDOMElement();
  });

  it("explains an existing password account", () => {
    render(<OAuthErrorAlert error="account_exists_password" />);
    expect(screen.getByRole("alert")).toHaveTextContent(
      /already exists - sign in with your password/i,
    );
  });

  it("does not reflect arbitrary text from the URL", () => {
    render(<OAuthErrorAlert error="Click evil.example to recover" />);
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent(OAUTH_ERROR_MESSAGES.oauth_failed);
    expect(alert).not.toHaveTextContent(/evil/);
  });
});
