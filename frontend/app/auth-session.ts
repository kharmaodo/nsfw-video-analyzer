export type AuthenticatedUser = {
  id: number;
  username: string;
  role: "GUEST" | "SUPER_POWER";
};

export type AuthSession = {
  accessToken: string;
  expiresIn: number;
  user: AuthenticatedUser;
};

const SESSION_KEY = "nsfw-video-analyzer.auth-session";

export function readSession(): AuthSession | null {
  if (typeof window === "undefined") return null;
  const serialized = window.sessionStorage.getItem(SESSION_KEY);
  if (!serialized) return null;
  try {
    const value = JSON.parse(serialized) as AuthSession;
    return value.accessToken ? value : null;
  } catch {
    window.sessionStorage.removeItem(SESSION_KEY);
    return null;
  }
}

export function saveSession(session: AuthSession): void {
  window.sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
}

export function clearSession(): void {
  if (typeof window !== "undefined") {
    window.sessionStorage.removeItem(SESSION_KEY);
  }
}

export function redirectToExpiredSessionLogin(): void {
  clearSession();
  if (window.location.pathname !== "/login") {
    window.location.assign("/login?reason=expired");
  }
}

