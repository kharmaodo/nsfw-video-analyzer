# Guide d’exploitation

## Contrôles de santé

- `GET /health/live` : le processus API répond ;
- `GET /health/ready` : SQLite et Redis sont accessibles ;
- `GET /metrics` : métriques Prometheus de volume et de latence HTTP ;
- `GET /api/health` sur le frontend : serveur web disponible.

Une alerte est recommandée si `/health/ready` échoue pendant deux minutes ou si le taux de réponses HTTP 5xx augmente.

## Journaux

```bash
docker compose logs -f api
docker compose logs -f worker
docker compose logs -f frontend
```

Chaque réponse API expose `X-Request-ID`. Utilisez cette valeur pour rapprocher une erreur utilisateur des journaux correspondants.

## Sauvegarde SQLite cohérente

```bash
docker compose exec api python -c \
  "import sqlite3; s=sqlite3.connect('/app/storage/database/videos.db'); d=sqlite3.connect('/app/storage/database/videos.backup.db'); s.backup(d); d.close(); s.close()"
docker compose cp api:/app/storage/database/videos.backup.db ./videos.backup.db
```

## Restauration

1. Arrêter l’API et le worker.
2. Conserver une copie de la base courante.
3. Copier la sauvegarde dans le volume sous le nom `videos.db`.
4. Redémarrer l’API, attendre son healthcheck, puis démarrer le worker.
5. Vérifier `alembic current` et `/health/ready`.

## Nettoyage

Les frames sont supprimées après l’inférence. Pour inspecter temporairement les images lors d’un diagnostic contrôlé, utilisez `NSFW_CLEANUP_FRAMES=false`. Réactivez immédiatement le nettoyage et purgez le volume, car ces images peuvent contenir du contenu sensible.

## Ajustement du modèle

Constituez un jeu de validation représentatif et mesurez faux positifs et faux négatifs avant de modifier : `NSFW_THRESHOLD`, `NSFW_MIN_POSITIVE_FRAMES`, `VIDEO_FRAME_INTERVAL_SECONDS` ou `VIDEO_CLIP_DURATION_SECONDS`.

Toute modification doit être versionnée et accompagnée des métriques de validation. Une décision sensible doit rester soumise à une revue humaine.

## Montée en charge

SQLite accepte un seul écrivain simultané. Avant d’augmenter la concurrence :

1. migrer la base vers PostgreSQL ;
2. utiliser un stockage objet pour les fichiers temporaires ;
3. séparer les workers CPU et GPU ;
4. configurer les limites de tâches par worker ;
5. ajouter une politique egress interdisant les réseaux internes.

## Arrêt et suppression

```bash
docker compose down
```

`docker compose down --volumes` détruit les volumes et leurs données. Ne l’utilisez qu’après une sauvegarde vérifiée.
