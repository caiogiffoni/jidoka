"use client";

import { useEffect, useState } from "react";
import { setAuthToken } from "@/app/actions";

export default function OAuthCallbackPage() {
  const [status, setStatus] = useState("Completing sign in…");

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get("token");
    const error = params.get("error");

    if (error) {
      setStatus("Sign-in failed. Redirecting…");
      window.location.href = `/login?error=${encodeURIComponent(error)}`;
      return;
    }

    if (!token) {
      setStatus("Missing token. Redirecting…");
      window.location.href = "/login?error=missing_token";
      return;
    }

    let cancelled = false;

    setAuthToken(token)
      .then((result) => {
        if (cancelled) return;
        if (result.type === "success") {
          window.location.href = "/board";
        } else {
          setStatus("Could not sign in. Redirecting…");
          window.location.href = `/login?error=${encodeURIComponent(result.message)}`;
        }
      })
      .catch(() => {
        if (cancelled) return;
        setStatus("Something went wrong. Redirecting…");
        window.location.href = "/login?error=callback_failed";
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="flex min-h-dvh items-center justify-center bg-background p-4 text-sm text-muted-foreground">
      {status}
    </div>
  );
}
