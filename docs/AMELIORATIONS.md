Voici le prompt d’implémentation réécrit et structuré.

````markdown
# Évolution : authentification, autorisation et administration

## Contexte

Projet `nsfw-video-analyzer`, branche `develop`.

Architecture actuelle :

- Frontend : React 19, TypeScript, Vinext ;
- Backend : FastAPI, SQLAlchemy 2, Alembic, SQLite WAL ;
- Asynchrone : Celery + Redis ;
- Analyse : FFmpeg/FFprobe et `Falconsai/nsfw_image_detection` ;
- Médias locaux et distants déjà pris en charge ;
- Entité principale actuelle : `Video`, utilisée comme média analysable.

L’objectif est d’ajouter une authentification JWT robuste, une gestion des rôles, la propriété des médias, un espace d’administration et les fondations OAuth2.

---

## Règles fonctionnelles

### Rôles

Introduire au minimum les rôles suivants :

| Rôle | Droits |
|---|---|
| `GUEST` | Créer, consulter, analyser et supprimer uniquement ses propres médias ; soumis aux limites standard. |
| `SUPER_POWER` | Accès total à tous les médias, tous les utilisateurs, profils et journaux ; non soumis au rate limiting d’analyse. |

Un utilisateur invité n’est pas un accès HTTP anonyme : il est authentifié avec un compte de rôle `GUEST` et reçoit un JWT. Cela permet de conserver la règle « tous les endpoints métier exigent un JWT valide ».

### Propriété des médias

Ajouter `owner_user_id` à l’entité actuelle `Video` / Media.

- Tout média créé via upload, découverte URL ou API est associé à l’utilisateur connecté.
- Un `GUEST` ne peut lire, modifier, supprimer ou analyser que ses propres médias.
- Un `SUPER_POWER` peut réaliser le CRUD sur tous les médias.
- Les anciens médias existants doivent rester compatibles : `owner_user_id` est nullable à la migration, puis attribuable par un `SUPER_POWER`.
- Les requêtes de liste et détail doivent filtrer automatiquement selon l’identité authentifiée.

### Authentification JWT

Tous les endpoints sont protégés par JWT, sauf :

- `GET /health`
- `POST /auth/login`

Exceptions OAuth2 nécessaires lorsque cette fonctionnalité est activée :

- `GET /auth/oauth2/{provider}/start`
- `GET /auth/oauth2/{provider}/callback`

Le JWT doit contenir au minimum :

- `sub` : identifiant utilisateur ;
- `username` ;
- `roles` ;
- `iat`, `exp`, `jti`.

Prévoir :

- access token à durée courte configurable ;
- algorithme et clé de signature configurables exclusivement par variables d’environnement ;
- réponse `401` uniforme pour token absent, invalide ou expiré ;
- réponse `403` pour permissions insuffisantes ;
- ne jamais inclure mot de passe, hash ou information sensible dans le JWT.

### Compte administrateur

Créer une entité `User` avec au minimum :

- `id` ;
- `username` unique ;
- `password_hash` ;
- `roles` ;
- `is_active` ;
- `created_at`, `updated_at` ;
- `last_login_at`.

Exigences :

- mot de passe stocké uniquement avec BCrypt ;
- aucun mot de passe ou hash retourné par l’API ;
- créer un utilisateur initial `SUPER_POWER` par commande de bootstrap documentée, jamais avec un mot de passe codé en dur ;
- désactiver un utilisateur doit invalider son accès aux endpoints protégés.

### Changement d’identifiants

Ajouter un endpoint sécurisé permettant à l’utilisateur connecté de modifier :

- son nom d’utilisateur ;
- son mot de passe.

Le mot de passe actuel est obligatoire pour toute modification sensible.

Exemple :

```http
PUT /api/v1/auth/credentials
Authorization: Bearer <token>

{
  "current_password": "…",
  "username": "nouveau-nom-optionnel",
  "new_password": "nouveau-mot-de-passe-optionnel"
}
````

Après changement de mot de passe, invalider les sessions ou tokens existants de cet utilisateur.

### Protection contre force brute

Protéger `POST /auth/login` avec Redis :

* limite par adresse IP ;
* blocage après `N` tentatives échouées configurables ;
* fenêtre de blocage configurable ;
* limite globale de tentatives sur une fenêtre glissante ;
* réponse `429` avec en-tête `Retry-After` ;
* message générique : ne pas révéler si le compte existe ;
* journaliser les succès, échecs, blocages et tentatives globalement limitées.

Le `SUPER_POWER` ne contourne jamais ces protections de connexion.

### Rate limiting d’analyse

* `GUEST` : rate limiting actuel appliqué aux uploads et à la mise en file d’analyse.
* `SUPER_POWER` : exempté uniquement du quota métier d’analyse.
* Les limites de sécurité restent actives pour tous : taille de fichier, types MIME, validation du contenu, protection brute-force, autorisation, stockage.

---

## OAuth2

Prévoir une architecture extensible OAuth2/OIDC avec Authorization Code Flow + PKCE.

Contraintes :

* ne pas coder de secret fournisseur dans le dépôt ;
* fournisseurs configurables par environnement ;
* lier un compte OAuth à un utilisateur local ;
* conserver `provider`, `provider_subject`, `user_id`, dates de liaison ;
* une connexion OAuth doit produire le même JWT applicatif que `/auth/login` ;
* prévoir les fournisseurs futurs sans couplage au frontend : Google, Facebook, TikTok, LinkedIn, Instagram, ChatGPT, Claude ;
* implémenter d’abord le socle générique et un fournisseur de référence seulement si les identifiants sont fournis.

---

## API à créer ou faire évoluer

### Public

```http
GET  /health
POST /auth/login
GET  /auth/oauth2/{provider}/start
GET  /auth/oauth2/{provider}/callback
```

### Authentifié

```http
GET  /api/v1/auth/me
PUT  /api/v1/auth/credentials

GET  /api/v1/media
GET  /api/v1/media/{id}
POST /api/v1/media/uploads
POST /api/v1/media/{id}/enqueue
POST /api/v1/media/{id}/requeue
```

### SUPER_POWER uniquement

```http
GET    /api/v1/admin/users
POST   /api/v1/admin/users
GET    /api/v1/admin/users/{id}
PATCH  /api/v1/admin/users/{id}
DELETE /api/v1/admin/users/{id}

GET    /api/v1/admin/roles
GET    /api/v1/admin/audit-logs
GET    /api/v1/admin/media
PATCH  /api/v1/admin/media/{id}
DELETE /api/v1/admin/media/{id}
```

Conserver les endpoints actuels lorsque possible, mais appliquer systématiquement le contrôle d’identité et de propriété.

---

## Frontend

Ajouter :

### Page de connexion

* formulaire nom d’utilisateur / mot de passe ;
* message exact `Session expirée` après expiration JWT ;
* éviter les redirections répétées : une seule redirection vers `/login?reason=session_expired` ;
* `401` : déconnexion et redirection ;
* `403` : afficher une erreur de permission, sans redirection ;
* stockage du token sécurisé selon l’architecture choisie ;
* déconnexion explicite.

### Dashboard utilisateur

* `GUEST` ne voit que ses médias ;
* conserve import, collecte, analyse, pagination et résultats ;
* aucune action sur un média appartenant à un autre utilisateur ;
* affichage du profil connecté et du rôle.

### Interface administration

Visible uniquement à `SUPER_POWER` :

* tableau des utilisateurs ;
* création, modification, activation/désactivation et attribution des rôles ;
* consultation et CRUD sur tous les médias ;
* consultation de tous les logs d’audit ;
* filtres par utilisateur, action, date, rôle et statut ;
* affichage clair du propriétaire de chaque média.

---

## Audit et sécurité

Créer une table d’audit avec au minimum :

* `id` ;
* `actor_user_id` nullable ;
* `action` ;
* `target_type` ;
* `target_id` ;
* `ip_address` ;
* `details` JSON/textuel sans secret ;
* `created_at`.

Journaliser notamment :

* connexion réussie ou échouée ;
* blocage rate limit ;
* changement d’identifiants ;
* création/modification/suppression d’utilisateur ;
* changement de rôle ;
* upload, suppression, mise en file et analyse de média ;
* actions administrateur sur les médias d’un autre utilisateur.

Ne jamais journaliser :

* mots de passe ;
* hashes BCrypt ;
* JWT ;
* cookies ;
* données GPS exactes.

---

## Migration et compatibilité

* Créer les migrations Alembic nécessaires ;
* conserver toutes les données et URLs distantes actuelles ;
* exécuter et vérifier une migration depuis une base existante ;
* exécuter et vérifier une migration depuis une base vide ;
* ne pas casser Docker Compose, SQLite WAL, Redis, Celery, API, frontend ou les médias déjà stockés.

Ajouter les variables documentées dans `.env.example`, notamment :

```env
JWT_SECRET_KEY=
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30

AUTH_LOGIN_MAX_FAILURES=5
AUTH_LOGIN_WINDOW_SECONDS=900
AUTH_LOGIN_BLOCK_SECONDS=900
AUTH_GLOBAL_MAX_ATTEMPTS=100
AUTH_GLOBAL_WINDOW_SECONDS=60

INITIAL_SUPER_POWER_USERNAME=
INITIAL_SUPER_POWER_PASSWORD=
```

Le mot de passe initial ne doit jamais être commité ; prévoir une commande de bootstrap.

---

## Qualité attendue

Implémenter par étapes, backend avant frontend.

1. Modèles, migration, BCrypt, bootstrap et JWT.
2. Tests unitaires et API d’authentification.
3. Contrôles de rôle, propriété des médias et audit.
4. Protection brute-force Redis.
5. Reprise des tests backend existants et couverture au moins égale au niveau actuel.
6. Frontend login, gestion d’expiration et dashboard filtré.
7. Interface `SUPER_POWER`.
8. `npm run lint`, `npm run build` et `npm test` doivent passer.
9. Tests E2E : GUEST, SUPER_POWER, token expiré, média d’autrui, brute-force, changement de mot de passe et relance Celery.

Ne pas démarrer l’implémentation frontend avant que les tests backend d’authentification, rôle, propriété et rate limiting soient validés.

```
```
