import {
  readSession,
  redirectToExpiredSessionLogin,
  redirectToLogin,
} from "./auth-session";


export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const session = readSession();
  if (!session) {
    redirectToLogin();
    throw new Error("Connexion requise.");
  }

  const headers = new Headers(init?.headers);
  headers.set("Authorization", `Bearer ${session.accessToken}`);
  if (typeof init?.body === "string" && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`/api/backend${path}`, { ...init, headers });
  if (response.status === 401) {
    redirectToExpiredSessionLogin();
    throw new Error("Session expirée.");
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? `Erreur HTTP ${response.status}`);
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

