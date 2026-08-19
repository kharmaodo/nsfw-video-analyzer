# NSFW Video Analyzer — Frontend

Dashboard React/TypeScript du pipeline d’analyse échantillonnée des vidéos.

## Fonctionnalités

- collecte d’une page distante ;
- liste paginée et filtrable des vidéos ;
- validation des vidéos découvertes ;
- mise en file des vidéos prêtes ;
- suivi automatique toutes les cinq secondes ;
- affichage des scores, frames positives et erreurs ;
- interface responsive et accessible.

## Prérequis

- Node.js 22.13 ou supérieur ;
- backend FastAPI démarré sur `http://localhost:8000`.

## Démarrage

```bash
npm install
npm run dev
```

Le navigateur appelle une route proxy intégrée au frontend. Par défaut, celle-ci
transmet les requêtes vers `http://localhost:8000`.

Pour utiliser une autre adresse :

```bash
BACKEND_API_URL=http://api:8000 npm run dev
```

## Vérification

```bash
npm run lint
npm run build
```

## Conteneur

```bash
docker build -t nsfw-video-dashboard .
docker run --rm -p 3000:3000 \
  -e BACKEND_API_URL=http://host.docker.internal:8000 \
  nsfw-video-dashboard
```

Healthcheck : `GET /api/health`.

Le statut `SAMPLED_SAFE` signifie uniquement que les images échantillonnées
n’ont pas déclenché la règle NSFW configurée ; ce n’est pas une garantie portant
sur la totalité de la vidéo.
