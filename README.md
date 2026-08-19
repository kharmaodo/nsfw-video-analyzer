# NSFW Video Analyzer

Application fullstack de collecte, validation et analyse NSFW échantillonnée de vidéos distantes.

## Architecture

| Composant | Technologie | Port |
|---|---|---:|
| Dashboard | React 19, TypeScript, Vinext | 3000 |
| API | FastAPI, SQLAlchemy 2 | 8000 |
| Worker | Celery, FFmpeg, Transformers | — |
| Broker | Redis 7 | 6379 interne |
| Données | SQLite en mode WAL | volume partagé |

Le pipeline extrait une fenêtre centrale de cinq minutes, prélève une image toutes les dix secondes et utilise le modèle `Falconsai/nsfw_image_detection`. Une vidéo courte est analysée sur toute sa durée.

> `SAMPLED_SAFE` signifie uniquement que les images échantillonnées n’ont pas déclenché la règle configurée. Ce statut ne garantit pas que toute la vidéo est sûre.

## Démarrage complet

Prérequis : Docker avec le plugin Compose.

```bash
cp backend/.env.example backend/.env
docker compose up --build -d
docker compose ps
```

- Dashboard : <http://localhost:3000>
- Swagger : <http://localhost:8000/docs>
- Vivacité : <http://localhost:8000/health/live>
- Disponibilité : <http://localhost:8000/health/ready>
- Métriques : <http://localhost:8000/metrics>

Le premier traitement télécharge les poids du modèle dans le volume `model-cache`. Il est donc plus long que les suivants.

## Parcours utilisateur

1. Soumettre l’URL d’une page autorisée depuis le dashboard.
2. Valider les vidéos au statut `DISCOVERED`.
3. Lancer l’analyse des vidéos au statut `READY`.
4. Suivre `QUEUED`, `PROCESSING`, puis `SAMPLED_SAFE` ou `SAMPLED_NSFW`.
5. Examiner manuellement les résultats et les erreurs.

## API principale

| Méthode | Route | Description |
|---|---|---|
| `POST` | `/api/v1/scraping/discover` | Collecter les vidéos d’une page |
| `POST` | `/api/v1/videos` | Enregistrer une vidéo |
| `GET` | `/api/v1/videos` | Paginer, filtrer et rechercher |
| `GET` | `/api/v1/videos/{id}` | Consulter une vidéo |
| `POST` | `/api/v1/videos/{id}/validate` | Valider taille, MIME et Range |
| `POST` | `/api/v1/videos/{id}/enqueue` | Mettre l’analyse en file |
| `PATCH` | `/api/v1/videos/{id}/status` | Changer un statut autorisé |
| `DELETE` | `/api/v1/videos/{id}` | Supprimer une entrée |

## Configuration importante

```env
VIDEO_MAX_SIZE_BYTES=5368709120
VIDEO_CLIP_DURATION_SECONDS=300
VIDEO_FRAME_INTERVAL_SECONDS=10
NSFW_THRESHOLD=0.60
NSFW_MIN_POSITIVE_FRAMES=1
NSFW_BATCH_SIZE=8
NSFW_DEVICE=-1
API_ALLOWED_HOSTS=localhost,127.0.0.1,testserver,api
```

Pour utiliser un GPU, adaptez l’image backend, installez la version CUDA de PyTorch et définissez `NSFW_DEVICE=0`.

## Développement local

Backend :

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev,ml]'
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

Frontend :

```bash
cd frontend
npm install
BACKEND_API_URL=http://localhost:8000 npm run dev
```

Redis et worker :

```bash
docker compose up -d redis
cd backend
celery -A app.workers.celery_app:celery_app worker --loglevel=INFO --concurrency=1 --prefetch-multiplier=1
```

## Tests

```bash
cd backend && pytest --cov=app
cd ../frontend && npm run lint && npm run build
```

Le projet contient des tests unitaires, API, sécurité, repository, worker et un scénario d’intégration couvrant création → validation → mise en file.

## Sécurité intégrée

- protection SSRF et validation DNS à chaque redirection applicative ;
- rejet des réseaux privés, loopback, link-local et réservés ;
- protocoles HTTP/HTTPS uniquement ;
- limites de taille et délais réseau/processus ;
- commandes FFmpeg sans shell ;
- image conteneur exécutée sans privilèges root ;
- poids du modèle chargés au format `safetensors` ;
- en-têtes de sécurité et identifiant par requête ;
- liste explicite des hôtes HTTP autorisés.

Une politique egress réseau reste recommandée en production pour empêcher FFmpeg de joindre des réseaux internes après une redirection distante.

## Limite SQLite

Le worker utilise `--concurrency=1` et `--prefetch-multiplier=1`. Pour plusieurs workers ou un volume important, migrez vers PostgreSQL.

Consultez [le guide d’exploitation](docs/OPERATIONS.md) pour les sauvegardes, la supervision, le diagnostic et les procédures d’incident.
