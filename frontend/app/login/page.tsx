"use client";

import { FormEvent, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Eye, EyeOff, LockKeyhole, ShieldCheck, UserRound } from "lucide-react";

import { saveSession } from "../auth-session";

type LoginResponse = {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  user: { id: number; username: string; role: "GUEST" | "SUPER_POWER" };
};

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [visiblePassword, setVisiblePassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const expired = searchParams.get("reason") === "expired";

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const response = await fetch("/api/backend/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: username.trim(), password }),
      });
      const body = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(
          typeof body?.detail === "string"
            ? body.detail
            : "Connexion impossible.",
        );
      }
      const result = body as LoginResponse;
      saveSession({
        accessToken: result.access_token,
        expiresIn: result.expires_in,
        user: result.user,
      });
      router.replace("/");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Connexion impossible.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="login-shell">
      <section className="login-card" aria-labelledby="login-title">
        <div className="login-mark"><ShieldCheck size={26} /></div>
        <p className="eyebrow">NSFW VIDEO ANALYZER</p>
        <h1 id="login-title">Connexion sécurisée</h1>
        <p className="login-intro">Accédez à vos médias et à leurs résultats d’analyse.</p>
        {expired && <p className="login-message">Session expirée. Connectez-vous à nouveau.</p>}
        {error && <p className="login-error" role="alert">{error}</p>}
        <form onSubmit={submit} className="login-form">
          <label htmlFor="username"><UserRound size={15} />Nom d’utilisateur</label>
          <input id="username" value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" required />
          <label htmlFor="password"><LockKeyhole size={15} />Mot de passe</label>
          <div className="login-password">
            <input id="password" type={visiblePassword ? "text" : "password"} value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" required />
            <button type="button" onClick={() => setVisiblePassword((value) => !value)} aria-label={visiblePassword ? "Masquer le mot de passe" : "Afficher le mot de passe"}>{visiblePassword ? <EyeOff size={17} /> : <Eye size={17} />}</button>
          </div>
          <button className="login-submit" disabled={submitting}>{submitting ? "Connexion…" : "Se connecter"}</button>
        </form>
      </section>
    </main>
  );
}

