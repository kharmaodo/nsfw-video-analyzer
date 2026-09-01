"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft, KeyRound, Save, UserRound } from "lucide-react";

import { api } from "../api-client";
import { readSession, redirectToLogin, saveSession } from "../auth-session";

type AuditLog = {
  id: number;
  action: string;
  ip_address: string | null;
  created_at: string;
};

type AuditPage = { items: AuditLog[]; total: number };


type UpdateResponse = {
  access_token: string;
  expires_in: number;
  user: { id: number; username: string; role: "GUEST" | "SUPER_POWER" };
};

type OAuthProviderRead = { provider: string };
type OAuthLinkStartResponse = { code: string };


export default function SettingsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [username, setUsername] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [enabledOAuthProviders, setEnabledOAuthProviders] = useState<string[]>([]);
  const [linkingProvider, setLinkingProvider] = useState<string | null>(null);
  const backendOrigin = (process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000").replace(/\/$/, "");



  useEffect(() => {
    const session = readSession();
    if (!session) {
      redirectToLogin();
      return;
    }
    setUsername(session.user.username);
    const oauthLink = searchParams.get("oauth_link");
    const provider = searchParams.get("provider");
    if (oauthLink === "success" && provider) {
      setMessage(`Compte ${provider} lié avec succès.`);
      router.replace("/settings");
    }
    if (oauthLink === "error" && provider) {
      setError(`Impossible de lier le compte ${provider}.`);
      router.replace("/settings");
    }

    void api<OAuthProviderRead[]>("/auth/oauth/providers")
      .then((providers) => setEnabledOAuthProviders(providers.map(({ provider }) => provider)))
      .catch(() => setEnabledOAuthProviders([]));

    void api<AuditPage>("/auth/audit-logs?page=1&size=12")
      .then((result) => setLogs(result.items))
      .catch(() => setLogs([]));

  }, []);

  async function startOAuthLink(provider: string): Promise<void> {
    setLinkingProvider(provider);
    setError(null);
    setMessage(null);
    try {
      const result = await api<OAuthLinkStartResponse>(`/auth/oauth/${provider}/link`, {
        method: "POST",
      });
      window.location.assign(
        `${backendOrigin}/auth/oauth/${provider}/link/start?code=${encodeURIComponent(result.code)}`,
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Liaison OAuth impossible.");
      setLinkingProvider(null);
    }
  }


  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const session = readSession();
    if (!session) {
      redirectToLogin();
      return;
    }
    const payload: { current_password: string; username?: string; new_password?: string } = {
      current_password: currentPassword,
    };
    if (username.trim() !== session.user.username) payload.username = username.trim();
    if (newPassword) payload.new_password = newPassword;
    if (!payload.username && !payload.new_password) {
      setError("Modifiez au moins un champ avant d’enregistrer.");
      return;
    }

    setSubmitting(true);
    setError(null);
    setMessage(null);
    try {
      const result = await api<UpdateResponse>("/auth/me", {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      saveSession({
        accessToken: result.access_token,
        expiresIn: result.expires_in,
        user: result.user,
      });
      setCurrentPassword("");
      setNewPassword("");
      setUsername(result.user.username);
      setMessage("Paramètres enregistrés. Votre session a été actualisée.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Mise à jour impossible.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="settings-shell">
      <a href="/" className="admin-back"><ArrowLeft size={16} />Tableau de bord</a>
      <section className="settings-card">
        <span className="settings-mark"><UserRound size={24} /></span>
        <p className="eyebrow">COMPTE UTILISATEUR</p>
        <h1>Paramètres</h1>
        <p>Pour modifier vos informations, confirmez toujours votre mot de passe actuel.</p>
        {error && <p className="login-error" role="alert">{error}</p>}
        {message && <p className="settings-success" role="status">{message}</p>}
        <form className="settings-form" onSubmit={submit}>
          <label htmlFor="settings-username">Nom d’utilisateur</label>
          <input id="settings-username" value={username} onChange={(event) => setUsername(event.target.value)} required />
          <label htmlFor="settings-current-password"><KeyRound size={15} />Mot de passe actuel</label>
          <input id="settings-current-password" type="password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} autoComplete="current-password" required />
          <label htmlFor="settings-new-password">Nouveau mot de passe <small>(facultatif)</small></label>
          <input id="settings-new-password" type="password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} autoComplete="new-password" />
          <button disabled={submitting}><Save size={16} />{submitting ? "Enregistrement…" : "Enregistrer"}</button>
        </form>
        <section className="settings-oauth" aria-labelledby="settings-oauth-title">
          <h2 id="settings-oauth-title">Comptes de connexion</h2>
          <p>Liez un fournisseur pour pouvoir vous connecter à ce même compte.</p>
          {enabledOAuthProviders.includes("google") && (
            <button
              type="button"
              onClick={() => void startOAuthLink("google")}
              disabled={linkingProvider !== null}
            >
              {linkingProvider === "google" ? "Redirection Google…" : "Lier Google"}
            </button>
          )}
          {enabledOAuthProviders.includes("facebook") && (
            <button
              type="button"
              onClick={() => void startOAuthLink("facebook")}
              disabled={linkingProvider !== null}
            >
              {linkingProvider === "facebook" ? "Redirection Facebook…" : "Lier Facebook"}
            </button>
          )}
        </section>


          {enabledOAuthProviders.includes("twitter") && (
            <button
              type="button"
              onClick={() => void startOAuthLink("twitter")}
              disabled={linkingProvider !== null}
            >
              {linkingProvider === "twitter"
                ? "Redirection X/Twitter…"
                : "Lier X (Twitter)"}
            </button>
          )}

        <section className="settings-audit" aria-labelledby="settings-audit-title">
          <h2 id="settings-audit-title">Activité récente</h2>
          {logs.length === 0
            ? <p>Aucun événement récent.</p>
            : <ul>{logs.map((log) => <li key={log.id}><span><strong>{log.action}</strong><small>{new Date(log.created_at).toLocaleString("fr-FR")}</small></span><em>{log.ip_address ?? "—"}</em></li>)}</ul>}
        </section>

      </section>
    </main>
  );
}

