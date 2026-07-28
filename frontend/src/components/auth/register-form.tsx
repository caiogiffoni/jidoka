"use client";

import { useActionState, useState } from "react";
import { register, type AuthActionState } from "@/app/actions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

const USERNAME_PATTERN = "^[a-zA-Z][a-zA-Z0-9_-]{2,29}$";
const PASSWORD_PATTERN = "^(?=.*[^A-Za-z0-9\\s]).{8,}$";

export function RegisterForm() {
  const [state, formAction, isPending] = useActionState<
    AuthActionState | null,
    FormData
  >(register, null);

  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const passwordsMatch =
    confirmPassword === "" || password === confirmPassword;

  return (
    <form action={formAction} className="flex flex-col gap-3">
      <div className="flex flex-col gap-1.5">
        <label
          htmlFor="register-username"
          className="text-xs font-medium text-muted-foreground"
        >
          Username
        </label>
        <Input
          id="register-username"
          name="username"
          type="text"
          autoComplete="username"
          placeholder="johndoe"
          required
          pattern={USERNAME_PATTERN}
          title="3-30 characters, must start with a letter, letters/numbers/_/- only"
        />
      </div>
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
          pattern={PASSWORD_PATTERN}
          title="At least 8 characters and one special character"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
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
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          aria-invalid={!passwordsMatch}
        />
        {!passwordsMatch && (
          <p className="text-xs text-destructive">Passwords do not match.</p>
        )}
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
      <Button
        type="submit"
        disabled={isPending || !passwordsMatch}
        className="w-full"
      >
        {isPending ? "Creating account…" : "Create account"}
      </Button>
    </form>
  );
}
