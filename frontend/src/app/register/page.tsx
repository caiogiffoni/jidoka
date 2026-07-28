import type { Metadata } from "next";
import { AuthCard } from "@/components/auth/auth-card";
import { RegisterForm } from "@/components/auth/register-form";

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
    </AuthCard>
  );
}
