"use client";

import { useEffect, useState } from "react";
import {
  fetchAuthStatus,
  type AuthUser,
} from "@/lib/auth";

export type AuthView =
  | { status: "loading"; user: null }
  | { status: "signedOut"; user: null }
  | { status: "signedIn"; user: AuthUser };

export function useAuthStatus(): AuthView {
  const [view, setView] = useState<AuthView>({ status: "loading", user: null });

  useEffect(() => {
    let cancelled = false;
    fetchAuthStatus().then((result) => {
      if (cancelled) return;
      if (result.authenticated) {
        setView({ status: "signedIn", user: result.user });
        return;
      }
      setView({ status: "signedOut", user: null });
    });
    return () => {
      cancelled = true;
    };
  }, []);

  return view;
}
