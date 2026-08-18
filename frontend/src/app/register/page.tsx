import type { Metadata } from "next";
import { AuthCard } from "@/components/auth/auth-card";
import { OAuthButtons } from "@/components/auth/oauth-buttons";
import { RegisterForm } from "@/components/auth/register-form";
import { BACKEND_URL } from "@/lib/api";

export const metadata: Metadata = {
  title: "Create account | Jidoka",
};

export default function RegisterPage() {
  return (
    <AuthCard
      title="Create account"
      description="Enter your email and choose a password to get started."
      footerText="Already have an account?"
      footerLinkText="Sign in"
      footerLinkHref="/login"
    >
      <RegisterForm />
      <OAuthButtons
        backendUrl={BACKEND_URL}
        providers={["google", "github"]}
        className="pt-2"
      />
    </AuthCard>
  );
}
