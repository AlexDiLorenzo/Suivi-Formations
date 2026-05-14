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
- `GET/POST /api/drivers`, `GET/PATCH /api/drivers/{id}`, `POST /api/drivers/{id}/archive`
- `GET /api/document-types`
- `GET /api/requirements/driver/{driver_id}`, `POST /api/requirements`, `DELETE /api/requirements/{id}`
- `GET /api/dashboard` — matrice depanneurs × types avec statut colore par cellule
- `POST /api/documents/upload` — upload PDF (admin) pour un (driver, doc_type) applicable, chiffre en Fernet, cree DocumentVersion validated
- `GET /api/documents/{version_id}/download` — telecharge la version dechiffree (admin uniquement)
- `POST /api/document-requests` — admin : cree une demande, renvoie le magic link (TTL 7 jours, usage unique)
- `GET /api/public/document-requests/{token}` — public : resout un magic link, renvoie le contexte (driver, type)
- `POST /api/public/document-requests/{token}/upload` — public : upload du PDF par le depanneur, cree DocumentVersion pending
- `GET /api/documents/{version_id}` — admin : details d'une version (uploaded_by, dates, statut, motif rejet, etc.)
- `POST /api/documents/{version_id}/validate` — admin : pending -> validated, devient current_version
- `POST /api/documents/{version_id}/reject` body `{reason}` — admin : pending -> rejected (motif obligatoire)

### Endpoints internes (auth header `X-Internal-Secret: $REMINDERS_SECRET`)

- `GET  /api/internal/reminders/due` — calcule les rappels du jour, cree
  les `Reminder` (sent_at=null) + `DocumentRequest` + magic_link, et
  retourne `{items: [...], skipped: [...]}`. Idempotent dans la journee.
- `POST /api/internal/reminders/mark-sent` body `{reminder_ids: [uuid, ...]}`
  — appele par n8n apres l'envoi des emails pour cocher `sent_at`.

## Workflow n8n (etape 6 : relances)

Workflow JSON pret a importer dans **`n8n/relances-quotidiennes.json`**.
Voir `n8n/README.md` pour la procedure d'import + creation des credentials.

n8n est l'orchestrateur (cron + envoi email via Resend). Le backend
fournit la liste de qui relancer et l'audit du sent_at. Pre-requis :
`REMINDERS_SECRET` et `FRONTEND_BASE_URL` dans le `.env` du backend,
**redemarrer le service** apres modification.

### Flux

```
[Cron Trigger] (tous les jours a 8h00)
    |
    v
[HTTP Request] GET https://formations.alex-worksmart.com/api/internal/reminders/due
    Headers: X-Internal-Secret: <REMINDERS_SECRET>
    |
    v
[Loop Over Items] sur "items"
    |
    v
[Email Send] (Brevo / SMTP)
    To: {{ $json.driver_email }}
    Subject: Habilitation {{ $json.document_type_libelle }} a renouveler
    Body: HTML avec {{ $json.magic_link }} comme bouton
    |
    v (apres la boucle)
[HTTP Request] POST .../api/internal/reminders/mark-sent
    Headers: X-Internal-Secret: <...>
    Body JSON: { "reminder_ids": [tous les reminder_id de la batch] }
```

### Exemple de reponse `GET /api/internal/reminders/due`

```json
{
  "items": [
    {
      "reminder_id": "fc1a...",
      "type": "j_minus_30",
      "driver_email": "marc.aubert@example.com",
      "driver_prenom": "Marc",
      "driver_nom": "Aubert",
      "document_type_code": "B2XL",
      "document_type_libelle": "B2XL (permis poids lourd)",
      "days_until_expiry": 30,
      "date_peremption": "2026-06-13",
      "magic_link": "https://formations.alex-worksmart.com/upload/abcdef...",
      "magic_link_expires_at": "2026-05-21T08:00:00+00:00"
    }
  ],
  "skipped": [
    { "driver_id": "...", "driver_nom": "Lucie Bernard",
      "document_type_code": "PERMIS", "type": "never_received",
      "reason": "no_email" }
  ]
}
```

Les `type` possibles : `j_minus_90`, `j_minus_30`, `j_minus_7`,
`never_received`. Adapte le sujet et le corps de l'email selon le type
(par ex. "Premier envoi" pour never_received vs "Renouvellement urgent"
pour j_minus_7).

### Test manuel sans n8n (depuis ton poste)

```bash
curl -H "X-Internal-Secret: $REMINDERS_SECRET" \
     https://formations.alex-worksmart.com/api/internal/reminders/due | jq
```

Important : **chaque appel reussi cree des Reminder en base** (pour
l'idempotence intra-journee). Si tu testes plusieurs fois dans la meme
journee, le 2eme appel renverra `items: []` car deja deduplique. Pour
re-tester, supprimer les Reminder du jour en base ou attendre le
lendemain.

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
