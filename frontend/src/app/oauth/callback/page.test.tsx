import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { OAuthCallbackHandler } from "./page";

const mockReplace = vi.fn();
const searchParams: Record<string, string> = {};

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mockReplace }),
  useSearchParams: () => ({
    get: (key: string) => searchParams[key] ?? null,
  }),
}));

vi.mock("@/app/actions", () => ({
  setAuthToken: vi.fn(),
}));

import { setAuthToken } from "@/app/actions";

describe("OAuthCallbackHandler", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.keys(searchParams).forEach((key) => delete searchParams[key]);
  });

  it("sets the token and redirects to /board on success", async () => {
    searchParams.token = "valid-token";
    vi.mocked(setAuthToken).mockResolvedValue({
      type: "success",
      message: "ok",
    });

    render(<OAuthCallbackHandler />);

    expect(screen.getByText(/completing sign in/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(setAuthToken).toHaveBeenCalledWith("valid-token");
    });
    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith("/board");
    });
  });

  it("redirects to login with error when token is missing", async () => {
    render(<OAuthCallbackHandler />);

    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith("/login?error=missing_token");
    });
    expect(setAuthToken).not.toHaveBeenCalled();
  });

  it("redirects to login with provider error", async () => {
    searchParams.error = "invalid_state";

    render(<OAuthCallbackHandler />);

    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith(
        "/login?error=invalid_state",
      );
    });
    expect(setAuthToken).not.toHaveBeenCalled();
  });

  it("redirects to login when setAuthToken returns an error", async () => {
    searchParams.token = "bad-token";
    vi.mocked(setAuthToken).mockResolvedValue({
      type: "error",
      message: "Invalid token.",
    });

    render(<OAuthCallbackHandler />);

    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith(
        "/login?error=Invalid%20token.",
      );
    });
  });
});
