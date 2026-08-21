# HABILITATION

Module 1MDP de suivi des habilitations des depanneurs (B2XL, CACES, permis, carte conducteur).

## Stack

- Backend : FastAPI + SQLAlchemy + Alembic + PostgreSQL (toutes les routes prefixees par `/api`)
- Frontend : React 18 + Vite, servi en prod par nginx (qui proxie aussi `/api/*` vers le backend)
- Auth admin : JWT + TOTP (2FA optionnel)
- Stockage fichiers : filesystem chiffre (Fernet) — utilise des l'etape 3
- Orchestration : docker compose (dev = `docker-compose.yml`, prod VPS = `docker-compose.prod.yml`)

## Demarrage local

### Backend + Postgres (Docker)

1. Copier `.env.example` vers `.env`, puis generer les secrets :

   ```
   python -c "import secrets; print(secrets.token_urlsafe(64))"
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

   Coller les valeurs dans `JWT_SECRET` et `FILE_ENCRYPTION_KEY`.

2. Lancer Postgres + backend :

   ```
   docker compose up -d --build
   ```

   Les migrations Alembic s'appliquent automatiquement au demarrage.

3. Seeder les 4 types de documents MVP :

   ```
   docker compose exec backend python -m scripts.seed_doctypes
   ```

4. Creer un premier admin :

   ```
   docker compose exec backend python -m scripts.create_admin \
       --email <VOTRE_EMAIL> --name "<VOTRE_NOM>" --password '<MOT_DE_PASSE>'
   ```

5. (Optionnel, pour visualiser le tableau de bord avec de la fake data) seed demo :

   ```
   docker compose exec backend python -m scripts.seed_demo
   ```

   Cree 3 depanneurs avec des cellules de chaque couleur. **Ne pas executer en prod.**

6. API sur http://localhost:8000 (endpoints sous `/api/...`) — doc OpenAPI sur http://localhost:8000/docs

### Frontend (Vite, hors Docker en dev)

```
cd frontend
npm install
npm run dev
```

Front dispo sur http://localhost:5173. Vite proxie automatiquement `/api/*` vers
`http://localhost:8000`, donc pas de souci de CORS.

## Endpoints disponibles

- `POST /api/auth/login` — email + password (+ totp_code si 2FA active)
- `GET  /api/auth/me` — profil admin courant
- `POST /api/auth/totp/setup` / `POST /api/auth/totp/enable` — enrolement TOTP
- `GET /api/drivers`, `GET /api/drivers/{id}` — **lecture seule** : la liste,
  l'identite, l'equipe et le type de vehicule viennent de DepanTime et de Flotte,
  et les documents attendus en decoulent (cf. `backend/app/socle.py`). Ni creation,
  ni modification, ni reglage d'applicabilite.
- `GET /api/document-types` — les 22 types, avec `niveau_exigence`
  (socle / complementaire) et `perimetre` (tous / asf / poids_lourd)
- `GET /api/dashboard` — etat de chaque document par depanneur, plus les deux
  indicateurs : conformite au socle (%) et qualification (fraction)
- `POST /api/documents/upload` — upload PDF (admin) pour un (driver, doc_type) applicable, chiffre en Fernet, cree DocumentVersion validated
- `GET /api/documents/{version_id}/download` — telecharge la version dechiffree (admin uniquement)
- `POST /api/document-requests` — admin : cree une demande, renvoie le magic link (TTL 7 jours, usage unique)
- `GET /api/public/document-requests/{token}` — public : resout un magic link, renvoie le contexte (driver, type)
- `POST /api/public/document-requests/{token}/upload` — public : upload du PDF par le depanneur, cree DocumentVersion pending
- `GET /api/documents/{version_id}` — admin : details d'une version (uploaded_by, dates, statut, motif rejet, etc.)
- `DELETE /api/documents/{version_id}` — admin : supprime une piece deposee par
  erreur (fichier chiffre compris), trace dans `audit_log`. La version validee
  precedente redevient courante ; s'il n'en reste aucune, le document disparait.
- `POST /api/documents/{version_id}/validate` — admin : pending -> validated, devient current_version
- `POST /api/documents/{version_id}/reject` body `{reason}` — admin : pending -> rejected (motif obligatoire)

### Endpoint interne (auth header `X-Internal-Secret: $REMINDERS_SECRET`)

- `POST /api/internal/sync/depantime` — force une synchronisation immediate de
  l'equipe depuis DepanTime et Flotte. Ce n'est **pas** ce qui la fait tourner :
  elle est portee par l'application elle-meme (`backend/app/scheduler.py`, toutes
  les `SYNC_INTERVAL_MINUTES`). Cet endpoint sert a ne pas attendre le tour
  suivant, apres avoir corrige une equipe dans DepanTime par exemple.
- `GET /api/health` (public) expose l'etat de la derniere synchronisation :
  c'est le seul endroit ou une synchro muette peut se voir.

## Synchronisation de l'equipe

Elle etait declenchee par un cron n8n ; il n'y a plus de workflow n8n
(2026-08-21). Le backend s'en charge lui-meme au demarrage puis en boucle, ce
qui enleve la dependance a un service tiers : un conteneur qui tourne est un
conteneur qui synchronise. Les relances par email qui passaient aussi par n8n
ont ete supprimees — elles n'avaient jamais servi.

## Deploiement (VPS Hetzner)

L'app tourne sur le VPS dans `/srv/habilitation/`, derriere Traefik (`/srv/stack/`)
qui gere TLS auto (Cloudflare DNS challenge). Domaine :
`https://formations.alex-worksmart.com`.

Architecture en prod : Traefik → service `frontend` (nginx) qui sert le SPA et
proxie `/api/*` vers le service `backend` (FastAPI). Le backend n'est PAS expose
directement par Traefik.

### Bootstrap initial (a faire une seule fois)

1. **DNS Cloudflare** : creer un enregistrement A `formations` -> IP du VPS,
   proxy Cloudflare active (orange cloud).

2. **Sur le VPS** :

   ```
   sudo mkdir -p /srv/habilitation
   sudo chown $USER:$USER /srv/habilitation
   cd /srv/habilitation
   git clone https://github.com/AlexDiLorenzo/Suivi-Formations.git .
   cp .env.prod.example .env
   ```

3. **Editer `.env`** : generer les secrets et coller les valeurs (cf.
   commentaires dans le fichier).

4. **Premier demarrage** :

   ```
   sudo docker compose -f docker-compose.prod.yml up -d --build
   ```

   Les migrations Alembic s'appliquent automatiquement. Traefik detecte
   le service `frontend` via les labels et expose le domaine en HTTPS.

5. **Seed des types de documents + creation admin** :

   ```
   sudo docker compose -f docker-compose.prod.yml exec backend python -m scripts.seed_doctypes
   sudo docker compose -f docker-compose.prod.yml exec backend python -m scripts.create_admin \
       --email <VOTRE_EMAIL> --name "<VOTRE_NOM>" --password '<MOT_DE_PASSE>'
   ```

   ATTENTION : remplacer les `<...>` par les vraies valeurs avant d'executer.
   Mettre le mot de passe entre quotes simples si jamais il contient `$`, `!`
   ou autres caracteres interpretes par le shell.

### Workflow de deploiement (changements ulterieurs)

Sur la machine de dev : `git push` vers `main`.

Sur le VPS :

```
cd /srv/habilitation
sudo git pull
sudo docker compose -f docker-compose.prod.yml up -d --build
```

## Roadmap

Voir la roadmap MVP (etapes 1 a 9) dans `CLAUDE.md`.
