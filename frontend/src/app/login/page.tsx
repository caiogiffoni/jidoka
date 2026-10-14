import type { Metadata } from "next";
import { AuthCard } from "@/components/auth/auth-card";
import { LoginForm } from "@/components/auth/login-form";
import { OAuthButtons } from "@/components/auth/oauth-buttons";
import { OAuthErrorAlert } from "@/components/auth/oauth-error-alert";
import { BACKEND_URL } from "@/lib/api";

export const metadata: Metadata = {
  title: "Sign in | Jidoka",
};

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string | string[] }>;
}) {
  const { error } = await searchParams;

  return (
    <AuthCard
      title="Sign in"
      description="Enter your email and password to continue."
      footerText="Don't have an account?"
      footerLinkText="Create one"
      footerLinkHref="/register"
    >
      <OAuthErrorAlert error={error} />
      <LoginForm />
      <OAuthButtons
        backendUrl={BACKEND_URL}
        providers={["google", "github"]}
        className="pt-2"
      />
    </AuthCard>
  );
}
