"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, KeyRound, Save, UserRound } from "lucide-react";

import { api } from "../api-client";
import { readSession, redirectToLogin, saveSession } from "../auth-session";

type UpdateResponse = {
  access_token: string;
  expires_in: number;
  user: { id: number; username: string; role: "GUEST" | "SUPER_POWER" };
};

export default function SettingsPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const session = readSession();
    if (!session) {
      redirectToLogin();
      return;
    }
    setUsername(session.user.username);
  }, []);

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
      </section>
    </main>
  );
}

