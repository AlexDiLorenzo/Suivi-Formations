# HABILITATION

Module 1MDP de suivi des habilitations des depanneurs (B2XL, CACES, permis, carte conducteur).

## Stack

- Backend : FastAPI + SQLAlchemy + Alembic + PostgreSQL
- Auth admin : JWT + TOTP (2FA optionnel)
- Stockage fichiers : filesystem chiffre (Fernet) — utilise des l'etape 3
- Orchestration locale : docker compose

## Demarrage local

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
   docker compose exec backend python -m scripts.create_admin --email vous@1mdp.fr --name "Votre Nom" --password "..."
   ```

5. API sur http://localhost:8000 — doc OpenAPI sur http://localhost:8000/docs

## Endpoints disponibles (etape 1)

- `POST /auth/login` — email + password (+ totp_code si 2FA active)
- `GET /auth/me` — profil admin courant
- `POST /auth/totp/setup` — initie l'enrolement TOTP (renvoie le QR code en data URI)
- `POST /auth/totp/enable` — confirme avec un code pour activer le 2FA
- `GET /drivers` — liste des depanneurs
- `POST /drivers` — creation
- `GET /drivers/{id}` / `PATCH /drivers/{id}` / `POST /drivers/{id}/archive`
- `GET /document-types` — liste des 4 types MVP
- `GET /requirements/driver/{driver_id}` — exigences applicables a un depanneur
- `POST /requirements` — cocher une exigence pour un depanneur
- `DELETE /requirements/{id}` — decocher

## Deploiement (VPS Hetzner)

L'app tourne sur le VPS dans `/srv/habilitation/`, derriere Traefik (`/srv/stack/`)
qui gere TLS auto (Cloudflare DNS challenge). Domaine :
`https://formations.alex-worksmart.com`.

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
   le service via les labels et expose le domaine en HTTPS.

5. **Seed des types de documents + creation admin** :

   ```
   sudo docker compose -f docker-compose.prod.yml exec backend python -m scripts.seed_doctypes
   sudo docker compose -f docker-compose.prod.yml exec backend python -m scripts.create_admin --email vous@1mdp.fr --name "Votre Nom" --password "..."
   ```

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
