import type { Metadata } from "next";
import { AuthCard } from "@/components/auth/auth-card";
import { LoginForm } from "@/components/auth/login-form";

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
    </AuthCard>
  );
}
