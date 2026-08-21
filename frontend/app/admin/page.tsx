"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, RefreshCw, ShieldCheck, Trash2, UserPlus, UsersRound } from "lucide-react";

import { api } from "../api-client";
import { readSession, redirectToLogin } from "../auth-session";

type Role = "GUEST" | "SUPER_POWER";
type User = { id: number; username: string; role: Role; is_active: boolean; last_login_at: string | null };
type UserPage = { items: User[]; total: number };
type AuditLog = { id: number; actor_user_id: number | null; action: string; ip_address: string | null; created_at: string };
type AuditPage = { items: AuditLog[]; total: number };

export default function AdminPage() {
  const router = useRouter();
  const [users, setUsers] = useState<User[]>([]);
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<Role>("GUEST");
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    setLoading(true);
    try {
      const [userPage, auditPage] = await Promise.all([
        api<UserPage>("/api/v1/admin/users?page=1&size=100"),
        api<AuditPage>("/auth/audit-logs?page=1&size=30"),
      ]);
      setUsers(userPage.items);
      setLogs(auditPage.items);
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Administration indisponible.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const session = readSession();
    if (!session) {
      redirectToLogin();
      return;
    }
    if (session.user.role !== "SUPER_POWER") {
      router.replace("/");
      return;
    }
    void refresh();
  }, [router]);

  async function createUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      await api("/api/v1/admin/users", {
        method: "POST",
        body: JSON.stringify({ username: username.trim(), password, role }),
      });
      setUsername("");
      setPassword("");
      setRole("GUEST");
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Création impossible.");
    }
  }

  async function toggleUser(user: User) {
    try {
      await api(`/api/v1/admin/users/${user.id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !user.is_active }),
      });
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Mise à jour impossible.");
    }
  }

  async function deleteUser(user: User) {
    if (!window.confirm(`Supprimer ${user.username} ?`)) return;
    try {
      await api(`/api/v1/admin/users/${user.id}`, { method: "DELETE" });
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Suppression impossible.");
    }
  }

  return (
    <main className="admin-shell">
      <header className="admin-topbar">
        <a href="/" className="admin-back"><ArrowLeft size={16} />Tableau de bord</a>
        <button className="icon-button" onClick={() => void refresh()} aria-label="Actualiser"><RefreshCw size={18} className={loading ? "spin" : ""} /></button>
      </header>
      <section className="admin-heading"><span><ShieldCheck size={24} /></span><div><p className="eyebrow">SUPER_POWER</p><h1>Administration</h1><p>Comptes utilisateurs et journal d’activité.</p></div></section>
      {error && <p className="admin-error" role="alert">{error}</p>}
      <section className="admin-grid">
        <article className="admin-card">
          <h2><UserPlus size={18} />Créer un utilisateur</h2>
          <form className="admin-form" onSubmit={createUser}>
            <input value={username} onChange={(event) => setUsername(event.target.value)} placeholder="Nom d’utilisateur" required />
            <input value={password} onChange={(event) => setPassword(event.target.value)} type="password" placeholder="Mot de passe initial" required />
            <select value={role} onChange={(event) => setRole(event.target.value as Role)}><option value="GUEST">GUEST</option><option value="SUPER_POWER">SUPER_POWER</option></select>
            <button>Créer le compte</button>
          </form>
        </article>
        <article className="admin-card admin-summary"><UsersRound size={22} /><strong>{users.length}</strong><span>comptes sur cette page</span></article>
      </section>
      <section className="admin-card admin-table-card">
        <h2>Utilisateurs</h2>
        <div className="table-wrap"><table><thead><tr><th>Utilisateur</th><th>Rôle</th><th>État</th><th>Dernière connexion</th><th>Actions</th></tr></thead><tbody>
          {users.map((user) => <tr key={user.id}><td>{user.username}</td><td><span className="admin-role">{user.role}</span></td><td><span className={user.is_active ? "admin-active" : "admin-inactive"}>{user.is_active ? "Actif" : "Désactivé"}</span></td><td>{user.last_login_at ? new Date(user.last_login_at).toLocaleString("fr-FR") : "—"}</td><td className="admin-actions"><button onClick={() => void toggleUser(user)}>{user.is_active ? "Désactiver" : "Activer"}</button><button onClick={() => void deleteUser(user)} aria-label={`Supprimer ${user.username}`}><Trash2 size={15} /></button></td></tr>)}
        </tbody></table></div>
      </section>
      <section className="admin-card admin-table-card">
        <h2>Journal d’audit récent</h2>
        <div className="table-wrap"><table><thead><tr><th>Date</th><th>Action</th><th>Utilisateur</th><th>IP</th></tr></thead><tbody>
          {logs.map((log) => <tr key={log.id}><td>{new Date(log.created_at).toLocaleString("fr-FR")}</td><td>{log.action}</td><td>{log.actor_user_id ?? "—"}</td><td>{log.ip_address ?? "—"}</td></tr>)}
        </tbody></table></div>
      </section>
    </main>
  );
}

