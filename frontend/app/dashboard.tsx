"use client";

import {
  Activity, AlertTriangle, CheckCircle2, ChevronLeft, ChevronRight, CircleOff,
  Clock3, Database, ExternalLink, FileImage, Film, ImagePlus, LoaderCircle,
  Menu, Play, RefreshCw, Search, ShieldCheck, ShieldX, Sparkles, Upload, X,CalendarDays, MapPin
} from "lucide-react";
import {
  DragEvent, FormEvent, KeyboardEvent, useCallback, useEffect, useMemo,
  useRef, useState,
} from "react";

type VideoStatus =
  | "DISCOVERED" | "VALIDATING" | "READY" | "REJECTED" | "QUEUED"
  | "PROCESSING" | "SAMPLED_SAFE" | "SAMPLED_NSFW" | "ERROR";
type MediaType = "IMAGE" | "VIDEO";
type Video = {
  id: number; title: string; page_url: string; video_url: string;
  resolved_video_url: string | null; media_type: MediaType;
  original_filename: string | null; metadata_title: string | null; media_created_at: string | null; gps_latitude: number | null; gps_longitude: number | null; width: number | null; height: number | null;
  content_type: string | null; size_bytes: number | null;
  duration_seconds: number | null; accepts_ranges: boolean | null;
  status: VideoStatus; nsfw_score: number | null; nsfw_average_score: number | null;
  nsfw_positive_frames: number; nsfw_model: string | null; sampled_frames: number;
  task_id: string | null; error_message: string | null; created_at: string;
  updated_at: string;
};
type VideoPage = {
  items: Video[]; page: number; size: number; total: number; pages: number;
};
type UploadFailure = { filename: string; error: string };
type UploadResult = { created: Video[]; failures: UploadFailure[] };
type UploadItem = {
  key: string; filename: string; progress: number; state: "uploading" | "done" | "error";
  media?: Video; error?: string;
};

const acceptedMedia =
  "image/jpeg,image/png,image/webp,video/mp4,video/webm,video/x-matroska,video/quicktime,video/x-msvideo,.jpg,.jpeg,.png,.webp,.mp4,.webm,.mkv,.mov,.avi";
const statusLabels: Record<VideoStatus, string> = {
  DISCOVERED: "Découverte", VALIDATING: "Validation", READY: "Prête",
  REJECTED: "Rejetée", QUEUED: "En file", PROCESSING: "Analyse",
  SAMPLED_SAFE: "Sûre", SAMPLED_NSFW: "NSFW", ERROR: "Erreur",
};
const activeStatuses: VideoStatus[] = ["VALIDATING", "QUEUED", "PROCESSING"];

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (typeof init?.body === "string" && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`/api/backend${path}`, { ...init, headers });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? `Erreur HTTP ${response.status}`);
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

function uploadFailureMessage(status: number, responseText: string): string {
  const fallback = status === 413
    ? "Le fichier dépasse la taille maximale autorisée."
    : `Téléversement refusé (HTTP ${status}).`;
  const body = responseText.trim();
  if (!body) return fallback;
  try {
    const payload = JSON.parse(body) as { detail?: unknown };
    return typeof payload.detail === "string" ? payload.detail : fallback;
  } catch {
    return fallback;
  }
}

function formatBytes(bytes: number | null) {
  if (bytes === null) return "—";
  const units = ["o", "Ko", "Mo", "Go"];
  let value = bytes;
  let index = 0;
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024;
    index += 1;
  }
  return `${value.toFixed(index > 1 ? 1 : 0)} ${units[index]}`;
}

function formatDuration(seconds: number | null) {
  if (seconds === null) return "Image";
  return `${Math.floor(seconds / 60)} min ${Math.round(seconds % 60).toString().padStart(2, "0")} s`;
}

function sourceLabel(media: Video) {
  return media.original_filename
    ?? (media.page_url.startsWith("local://") ? "Média local" : new URL(media.page_url).hostname);
}

function MediaMetadata({ media }: { media: Video }) {
  const hasGps = media.gps_latitude !== null && media.gps_longitude !== null;
  const date = media.media_created_at
    ? media.media_created_at.replace("T", " ").slice(0, 16)
    : null;

  if (!media.metadata_title && !date && !hasGps) return null;

  return (
    <span className="media-metadata">
      {media.metadata_title && <span className="metadata-chip">Titre intégré</span>}
      {date && <span className="metadata-date"><CalendarDays size={12} />{date}</span>}
      {hasGps && <span className="metadata-chip gps" title="Ce média contient une localisation GPS"><MapPin size={12} />GPS détecté</span>}
    </span>
  );
}
function StatusBadge({ status }: { status: VideoStatus }) {
  const Icon = status === "SAMPLED_SAFE" ? ShieldCheck
    : status === "SAMPLED_NSFW" ? ShieldX
      : status === "ERROR" || status === "REJECTED" ? CircleOff
        : activeStatuses.includes(status) ? LoaderCircle : CheckCircle2;
  return (
    <span className={`status-badge status-${status.toLowerCase()}`}>
      <Icon size={14} className={activeStatuses.includes(status) ? "spin" : ""} />
      {statusLabels[status]}
    </span>
  );
}

export default function Dashboard() {
  const [data, setData] = useState<VideoPage>({ items: [], page: 1, size: 10, total: 0, pages: 0 });
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<VideoStatus | "">("");
  const [pageUrl, setPageUrl] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [actingId, setActingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const [mobileMenu, setMobileMenu] = useState(false);
  const [uploads, setUploads] = useState<UploadItem[]>([]);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [queueingSelection, setQueueingSelection] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const loadVideos = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true);
    const params = new URLSearchParams({ page: String(page), size: "10" });
    if (search.trim()) params.set("search", search.trim());
    if (status) params.set("status", status);
    try {
      setData(await api<VideoPage>(`/api/v1/media?${params}`));
      setLastRefresh(new Date());
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "API indisponible");
    } finally {
      setLoading(false);
    }
  }, [page, search, status]);

  useEffect(() => {
    const timeout = window.setTimeout(() => loadVideos(), 250);
    return () => window.clearTimeout(timeout);
  }, [loadVideos]);

  useEffect(() => {
    const interval = window.setInterval(() => loadVideos(true), 5000);
    return () => window.clearInterval(interval);
  }, [loadVideos]);

  const metrics = useMemo(() => ({
    safe: data.items.filter((item) => item.status === "SAMPLED_SAFE").length,
    nsfw: data.items.filter((item) => item.status === "SAMPLED_NSFW").length,
    active: data.items.filter((item) => activeStatuses.includes(item.status)).length,
  }), [data.items]);

  async function scrape(event: FormEvent) {
    event.preventDefault();
    if (!pageUrl.trim()) return;
    setSubmitting(true);
    try {
      await api("/api/v1/scraping/discover", {
        method: "POST",
        body: JSON.stringify({ page_url: pageUrl.trim() }),
      });
      setPageUrl("");
      setPage(1);
      await loadVideos();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Scraping impossible");
    } finally {
      setSubmitting(false);
    }
  }

  function uploadOne(file: File) {
    const key = `${file.name}-${crypto.randomUUID()}`;
    setUploads((current) => [
      { key, filename: file.name, progress: 0, state: "uploading" },
      ...current,
    ]);

    const formData = new FormData();
    formData.append("files", file, file.name);
    const request = new XMLHttpRequest();
    request.open("POST", "/api/backend/api/v1/media/uploads");

    request.upload.onprogress = (event) => {
      if (!event.lengthComputable) return;
      const progress = Math.round((event.loaded / event.total) * 100);
      setUploads((current) => current.map((item) =>
        item.key === key ? { ...item, progress } : item,
      ));
    };

    request.onload = async () => {
      try {
        if (request.status < 200 || request.status >= 300) {
          throw new Error(uploadFailureMessage(request.status, request.responseText));
        }
        const result = JSON.parse(request.responseText) as UploadResult;
        const media = result.created[0];
        const failure = result.failures[0];
        if (!media) throw new Error(failure?.error ?? "Aucun média créé.");

        setUploads((current) => current.map((item) =>
          item.key === key ? { ...item, progress: 100, state: "done", media } : item,
        ));
        setSelectedIds((current) => current.includes(media.id) ? current : [...current, media.id]);
        setPage(1);
        await loadVideos(true);
      } catch (reason) {
        setUploads((current) => current.map((item) =>
          item.key === key
            ? { ...item, progress: 100, state: "error", error: reason instanceof Error ? reason.message : "Téléversement impossible" }
            : item,
        ));
      }
    };

    request.onerror = () => {
      setUploads((current) => current.map((item) =>
        item.key === key
          ? { ...item, progress: 100, state: "error", error: "Connexion au backend impossible." }
          : item,
      ));
    };
    request.send(formData);
  }

  function uploadFiles(files: FileList | File[]) {
    [...files].forEach(uploadOne);
  }

  function handleDrop(event: DragEvent<HTMLElement>) {
    event.preventDefault();
    uploadFiles(event.dataTransfer.files);
  }

  function handleUploadKeyboard(event: KeyboardEvent<HTMLElement>) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      inputRef.current?.click();
    }
  }

  async function runAction(media: Video) {
    setActingId(media.id);
    try {
      if (media.status === "DISCOVERED") {
        await api(`/api/v1/videos/${media.id}/validate`, { method: "POST" });
      } else if (media.status === "READY") {
        await api(`/api/v1/media/${media.id}/enqueue`, { method: "POST" });
      }
      await loadVideos(true);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Action impossible");
    } finally {
      setActingId(null);
    }
  }

  async function enqueueSelection() {
    const readyLocalIds = data.items
      .filter((item) =>
        selectedIds.includes(item.id)
        && item.status === "READY"
        && item.page_url.startsWith("local://"),
      )
      .map((item) => item.id);

    if (!readyLocalIds.length) return;
    setQueueingSelection(true);
    try {
      for (const id of readyLocalIds) {
        await api(`/api/v1/media/${id}/enqueue`, { method: "POST" });
      }
      setSelectedIds([]);
      await loadVideos(true);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Mise en file impossible");
    } finally {
      setQueueingSelection(false);
    }
  }

  function toggleSelection(id: number) {
    setSelectedIds((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id],
    );
  }

  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileMenu ? "sidebar-open" : ""}`}>
        <div className="brand"><span className="brand-mark"><ShieldCheck size={20} /></span><span>Sentinel<span>Video</span></span></div>
        <button className="mobile-close" onClick={() => setMobileMenu(false)} aria-label="Fermer le menu"><X /></button>
        <nav aria-label="Navigation principale">
          <a className="nav-item active" href="#dashboard"><Activity size={19} />Vue d’ensemble</a>
          <a className="nav-item" href="#videos"><Film size={19} />Médias <span className="nav-count">{data.total}</span></a>
          <a className="nav-item" href="#import"><Upload size={19} />Importer</a>
          <a className="nav-item" href="#collecte"><Search size={19} />Collecte URL</a>
        </nav>
        <div className="sidebar-spacer" />
        <div className="system-card"><div className="system-icon"><Database size={18} /></div><div><strong>Pipeline actif</strong><span>SQLite · Redis · ViT</span></div><span className="online-dot" /></div>
        <p className="sidebar-foot">Modération échantillonnée<br />Décision assistée par IA</p>
      </aside>

      {mobileMenu && <button className="backdrop" onClick={() => setMobileMenu(false)} aria-label="Fermer" />}

      <main className="main-content" id="dashboard">
        <header className="topbar">
          <button className="menu-button" onClick={() => setMobileMenu(true)} aria-label="Ouvrir le menu"><Menu /></button>
          <div><p className="eyebrow">Centre de contrôle</p><h1>Analyse des médias</h1></div>
          <div className="topbar-actions">
            <span className="refresh-copy"><Clock3 size={15} />{lastRefresh ? `Actualisé à ${lastRefresh.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}` : "Connexion…"}</span>
            <button className="icon-button" onClick={() => loadVideos()} aria-label="Actualiser"><RefreshCw size={18} className={loading ? "spin" : ""} /></button>
          </div>
        </header>

        {error && <div className="error-banner"><AlertTriangle size={18} /><span><strong>Connexion ou traitement interrompu.</strong> {error}</span><button onClick={() => setError(null)} aria-label="Fermer"><X size={17} /></button></div>}

        <section className="metrics-grid" aria-label="Indicateurs">
          <article className="metric-card"><span className="metric-icon total"><Film /></span><div><span>Médias recensés</span><strong>{data.total}</strong><small>dans la base locale</small></div></article>
          <article className="metric-card"><span className="metric-icon safe"><ShieldCheck /></span><div><span>Échantillons sûrs</span><strong>{metrics.safe}</strong><small>sur cette page</small></div></article>
          <article className="metric-card"><span className="metric-icon unsafe"><ShieldX /></span><div><span>Alertes NSFW</span><strong>{metrics.nsfw}</strong><small>à examiner</small></div></article>
          <article className="metric-card"><span className="metric-icon running"><Sparkles /></span><div><span>Traitements actifs</span><strong>{metrics.active}</strong><small>validation ou analyse</small></div></article>
        </section>

        <section className="import-card" id="import">
          <div className="section-heading">
            <span className="section-icon"><Upload /></span>
            <div><h2>Importer des médias locaux</h2><p>Images JPEG, PNG, WebP et vidéos MP4, WebM, MKV, MOV ou AVI.</p></div>
          </div>

          <input
            ref={inputRef}
            className="sr-only"
            id="media-files"
            type="file"
            accept={acceptedMedia}
            multiple
            onChange={(event) => event.target.files && uploadFiles(event.target.files)}
          />
          <div
            className="dropzone"
            role="button"
            tabIndex={0}
            aria-label="Déposer ou sélectionner des médias"
            onDrop={handleDrop}
            onDragOver={(event) => event.preventDefault()}
            onKeyDown={handleUploadKeyboard}
            onClick={() => inputRef.current?.click()}
          >
            <ImagePlus />
            <strong>Déposez vos médias ici</strong>
            <span>ou cliquez pour sélectionner plusieurs fichiers</span>
            <span className="dropzone-formats">Validation du contenu et métadonnées automatiques</span>
          </div>

          {uploads.length > 0 && (
            <div className="upload-list" aria-live="polite">
              {uploads.map((item) => (
                <article className={`upload-item upload-${item.state}`} key={item.key}>
                  <span className="upload-icon">{item.media?.media_type === "IMAGE" ? <FileImage /> : <Film />}</span>
                  <div className="upload-copy">
                    <strong>{item.filename}</strong>
                    {item.state === "uploading" && <><span>Téléversement : {item.progress}%</span><i><b style={{ width: `${item.progress}%` }} /></i></>}
                    {item.state === "done" && item.media && <span>{item.media.media_type} · {item.media.width} × {item.media.height} · {formatBytes(item.media.size_bytes)} · prête à analyser</span>}
                    {item.state === "error" && <span className="upload-error">{item.error}</span>}
                  </div>
                  {item.state === "uploading" && <LoaderCircle className="spin" size={18} />}
                  {item.state === "done" && <CheckCircle2 size={18} />}
                  {item.state === "error" && <AlertTriangle size={18} />}
                </article>
              ))}
            </div>
          )}
        </section>

        <section className="collect-card" id="collecte">
          <div className="section-heading"><span className="section-icon"><Search /></span><div><h2>Collecter une nouvelle page</h2><p>Extrayez les liens vidéo d’une page autorisée, puis lancez leur analyse.</p></div></div>
          <form onSubmit={scrape} className="scrape-form">
            <label htmlFor="page-url">URL de la page source</label>
            <div className="input-row"><div className="url-input"><ExternalLink size={18} /><input id="page-url" type="url" value={pageUrl} onChange={(event) => setPageUrl(event.target.value)} placeholder="https://media.example/catalogue" required /></div><button className="primary-button" disabled={submitting}>{submitting ? <LoaderCircle className="spin" /> : <Search />}Analyser la page</button></div>
            <p className="form-hint"><ShieldCheck size={14} />Les adresses privées et les protocoles non sécurisés sont automatiquement bloqués.</p>
          </form>
        </section>

        <section className="videos-card" id="videos">
          <div className="section-heading table-heading">
            <div><h2>Médias analysables</h2><p>Images locales, vidéos locales et médias distants.</p></div>
            <div className="table-actions">
              <span className="results-count">{data.total} résultat{data.total > 1 ? "s" : ""}</span>
              <button className="selection-button" disabled={!selectedIds.length || queueingSelection} onClick={enqueueSelection}>
                {queueingSelection ? <LoaderCircle className="spin" /> : <Play />}Analyser la sélection
              </button>
            </div>
          </div>

          <div className="filters"><div className="filter-search"><Search size={17} /><input value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} placeholder="Rechercher par titre ou URL…" /></div><select value={status} onChange={(event) => { setStatus(event.target.value as VideoStatus | ""); setPage(1); }} aria-label="Filtrer par statut"><option value="">Tous les statuts</option>{Object.entries(statusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div>

          <div className="table-wrap"><table><thead><tr><th><span className="sr-only">Sélection</span></th><th>Média</th><th>Statut</th><th>Fichier</th><th>Échantillon</th><th>Score NSFW</th><th><span className="sr-only">Action</span></th></tr></thead><tbody>
            {loading && data.items.length === 0 ? <tr><td colSpan={7}><div className="empty-state"><LoaderCircle className="spin" /><strong>Chargement des médias…</strong></div></td></tr>
              : data.items.length === 0 ? <tr><td colSpan={7}><div className="empty-state"><Film /><strong>Aucun média trouvé</strong><span>Importez un fichier ou ajoutez une page source.</span></div></td></tr>
                : data.items.map((media) => {
                  const selectable = media.status === "READY" && media.page_url.startsWith("local://");
                  return <tr key={media.id}>
                    <td>{selectable && <input className="media-checkbox" type="checkbox" checked={selectedIds.includes(media.id)} onChange={() => toggleSelection(media.id)} aria-label={`Sélectionner ${media.title}`} />}</td>
                    <td><div className="video-title"><span className="video-thumb">{media.media_type === "IMAGE" ? <FileImage size={18} /> : <Play size={18} fill="currentColor" />}</span><div><strong>{media.title}</strong><span className="media-source">{sourceLabel(media)}{media.media_type === "VIDEO" && !media.page_url.startsWith("local://") && <ExternalLink size={12} />}</span><MediaMetadata media={media} /></div></div></td>
                    <td><StatusBadge status={media.status} />{media.error_message && <span className="row-error" title={media.error_message}>Voir l’erreur</span>}</td>
                    <td><strong className="cell-main">{formatBytes(media.size_bytes)}</strong><span className="cell-sub">{media.content_type ?? "type inconnu"}{media.width && media.height ? ` · ${media.width}×${media.height}` : ""}</span></td>
                    <td><strong className="cell-main">{formatDuration(media.duration_seconds)}</strong><span className="cell-sub">{media.sampled_frames ? `${media.sampled_frames} frame${media.sampled_frames > 1 ? "s" : ""}` : "non extrait"}</span></td>
                    <td>{media.nsfw_score === null ? <span className="score-empty">—</span> : <div className="score"><strong>{Math.round(media.nsfw_score * 100)}%</strong><span><i style={{ width: `${media.nsfw_score * 100}%` }} /></span><small>{media.nsfw_positive_frames} positive{media.nsfw_positive_frames > 1 ? "s" : ""}</small></div>}</td>
                    <td>{(media.status === "DISCOVERED" || media.status === "READY") && <button className="action-button" onClick={() => runAction(media)} disabled={actingId === media.id}>{actingId === media.id ? <LoaderCircle className="spin" /> : media.status === "DISCOVERED" ? <ShieldCheck /> : <Play />}{media.status === "DISCOVERED" ? "Valider" : "Analyser"}</button>}</td>
                  </tr>;
                })}
          </tbody></table></div>

          <footer className="pagination"><span>Page {data.page} sur {Math.max(data.pages, 1)}</span><div><button onClick={() => setPage((value) => Math.max(1, value - 1))} disabled={page <= 1}><ChevronLeft />Précédent</button><button onClick={() => setPage((value) => value + 1)} disabled={data.pages === 0 || page >= data.pages}>Suivant<ChevronRight /></button></div></footer>
        </section>
      </main>
    </div>
  );
}