"use client";

import { useActionState } from "react";
import { login, type AuthActionState } from "@/app/actions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function LoginForm() {
  const [state, formAction, isPending] = useActionState<
    AuthActionState | null,
    FormData
  >(login, null);

  return (
    <form action={formAction} className="flex flex-col gap-3">
      <div className="flex flex-col gap-1.5">
        <label
          htmlFor="login-email"
          className="text-xs font-medium text-muted-foreground"
        >
          Email
        </label>
        <Input
          id="login-email"
          name="email"
          type="email"
          autoComplete="email"
          placeholder="you@example.com"
          required
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <label
          htmlFor="login-password"
          className="text-xs font-medium text-muted-foreground"
        >
          Password
        </label>
        <Input
          id="login-password"
          name="password"
          type="password"
          autoComplete="current-password"
          placeholder="••••••••"
          required
          minLength={8}
        />
      </div>
      {state && (
        <p
          role="alert"
          aria-live="polite"
          className={`text-xs ${
            state.type === "error" ? "text-destructive" : "text-muted-foreground"
          }`}
        >
          {state.message}
        </p>
      )}
      <Button type="submit" disabled={isPending} className="w-full">
        {isPending ? "Signing in…" : "Sign in"}
      </Button>
    </form>
  );
}
