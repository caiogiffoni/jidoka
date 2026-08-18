"use client";

import { Suspense, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { setAuthToken } from "@/app/actions";

export function OAuthCallbackHandler() {
  const router = useRouter();
  const searchParams = useSearchParams();

  useEffect(() => {
    const token = searchParams.get("token");
    const error = searchParams.get("error");

    if (error) {
      router.replace(`/login?error=${encodeURIComponent(error)}`);
      return;
    }

    if (!token) {
      router.replace("/login?error=missing_token");
      return;
    }

    let cancelled = false;

    setAuthToken(token)
      .then((result) => {
        if (cancelled) return;
        if (result.type === "success") {
          router.replace("/board");
        } else {
          router.replace(`/login?error=${encodeURIComponent(result.message)}`);
        }
      })
      .catch(() => {
        if (cancelled) return;
        router.replace("/login?error=callback_failed");
      });

    return () => {
      cancelled = true;
    };
  }, [router, searchParams]);

  return (
    <div className="flex min-h-dvh items-center justify-center bg-background p-4 text-sm text-muted-foreground">
      Completing sign in…
    </div>
  );
}

export default function OAuthCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-dvh items-center justify-center bg-background p-4 text-sm text-muted-foreground">
          Completing sign in…
        </div>
      }
    >
      <OAuthCallbackHandler />
    </Suspense>
  );
}
