"use client";

import { useActionState } from "react";
import { register, type AuthActionState } from "@/app/actions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

export function RegisterForm() {
  const [state, formAction, isPending] = useActionState<
    AuthActionState | null,
    FormData
  >(register, null);

  return (
    <form action={formAction} className="flex flex-col gap-3">
      <div className="flex flex-col gap-1.5">
        <label
          htmlFor="register-email"
          className="text-xs font-medium text-muted-foreground"
        >
          Email
        </label>
        <Input
          id="register-email"
          name="email"
          type="email"
          autoComplete="email"
          placeholder="you@example.com"
          required
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <label
          htmlFor="register-password"
          className="text-xs font-medium text-muted-foreground"
        >
          Password
        </label>
        <Input
          id="register-password"
          name="password"
          type="password"
          autoComplete="new-password"
          placeholder="••••••••"
          required
          minLength={8}
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <label
          htmlFor="register-confirm-password"
          className="text-xs font-medium text-muted-foreground"
        >
          Confirm password
        </label>
        <Input
          id="register-confirm-password"
          name="confirmPassword"
          type="password"
          autoComplete="new-password"
          placeholder="••••••••"
          required
          minLength={8}
        />
      </div>
      {state && (
        <p
          role="alert"
          aria-live="polite"
          className={cn(
            "text-xs",
            state.type === "error"
              ? "text-destructive"
              : "text-muted-foreground",
          )}
        >
          {state.message}
        </p>
      )}
      <Button type="submit" disabled={isPending} className="w-full">
        {isPending ? "Creating account…" : "Create account"}
      </Button>
    </form>
  );
}
