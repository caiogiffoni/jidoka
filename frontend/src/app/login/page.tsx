import type { Metadata } from "next";
import { AuthCard } from "@/components/auth/auth-card";
import { LoginForm } from "@/components/auth/login-form";
import { OAuthButtons } from "@/components/auth/oauth-buttons";
import { BACKEND_URL } from "@/lib/api";

export const metadata: Metadata = {
  title: "Sign in | Jidoka",
};

export default function LoginPage() {
  return (
    <AuthCard
      title="Sign in"
      description="Enter your email and password to continue."
      footerText="Don't have an account?"
      footerLinkText="Create one"
      footerLinkHref="/register"
    >
      <LoginForm />
      <OAuthButtons
        backendUrl={BACKEND_URL}
        providers={["google", "github"]}
        className="pt-2"
      />
    </AuthCard>
  );
}
