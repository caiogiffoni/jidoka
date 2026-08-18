import { expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { OAuthButtons } from "./oauth-buttons";

it("renders nothing when no providers are configured", () => {
  const { container } = render(<OAuthButtons backendUrl="http://localhost:8000" providers={[]} />);
  expect(container).toBeEmptyDOMElement();
});

it("renders Google and GitHub links when both providers are configured", () => {
  render(
    <OAuthButtons
      backendUrl="http://localhost:8000"
      providers={["google", "github"]}
    />,
  );

  expect(screen.getByRole("link", { name: /sign in with google/i })).toHaveAttribute(
    "href",
    "http://localhost:8000/auth/oauth/google",
  );
  expect(screen.getByRole("link", { name: /sign in with github/i })).toHaveAttribute(
    "href",
    "http://localhost:8000/auth/oauth/github",
  );
});

it("renders only the configured provider", () => {
  render(
    <OAuthButtons backendUrl="http://localhost:8000" providers={["google"]} />,
  );

  expect(screen.getByRole("link", { name: /sign in with google/i })).toBeInTheDocument();
  expect(
    screen.queryByRole("link", { name: /sign in with github/i }),
  ).not.toBeInTheDocument();
});
