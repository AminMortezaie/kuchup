export type AuthUser = {
  id: number;
  username: string;
  email: string;
  display_name: string;
  is_admin: boolean;
  plan: string;
};

export type AuthStatus =
  | { authenticated: false }
  | { authenticated: true; user: AuthUser };

export function authDisplayName(user: AuthUser): string {
  return user.display_name.trim();
}

export function authGivenName(user: AuthUser): string {
  return authDisplayName(user).split(/\s+/).find(Boolean) || "";
}

let pending: Promise<AuthStatus> | null = null;

export async function fetchAuthStatus(): Promise<AuthStatus> {
  if (!pending) {
    pending = readAuthStatus();
  }
  return pending;
}

async function readAuthStatus(): Promise<AuthStatus> {
  try {
    const res = await fetch("/api/auth/status", { credentials: "same-origin" });
    if (!res.ok) return { authenticated: false };
    const payload = await res.json();
    if (!payload?.authenticated || !payload.user) {
      return { authenticated: false };
    }
    return {
      authenticated: true,
      user: {
        id: payload.user.id,
        username: payload.user.username || "",
        email: payload.user.email || "",
        display_name: payload.user.display_name || "",
        is_admin: Boolean(payload.user.is_admin),
        plan: payload.user.plan || "free",
      },
    };
  } catch {
    return { authenticated: false };
  }
}
