# HABILITATION

Module 1MDP de suivi des habilitations et documents des dépanneurs (permis, FCO, B2XL, CACES, formations, documents administratifs). Cadrage fait le 2026-05-13, étape 1 (scaffold backend) livrée le même jour. Voir `README.md` pour le démarrage local.

## Stack

- **Backend** : FastAPI + SQLAlchemy 2.0 + Alembic + PostgreSQL 16. **Toutes les routes sont préfixées par `/api`** (servies sous le même domaine que le frontend via le proxy nginx).
- **Auth admin** : JWT (python-jose) + bcrypt + TOTP (pyotp, optionnel)
- **Stockage fichiers** (dès étape 3) : filesystem chiffré Fernet
- **Relances** (étape 6) : n8n appelle le backend (cron)
- **Frontend** : React 18 + Vite (single-file `src/App.jsx` à la DepanTime). En prod, servi par nginx qui proxie aussi `/api/*` vers le backend (un seul domaine, pas de CORS).
- **Hébergement prod** : VPS Hetzner Ubuntu, voir [memory reference-vps]

## Périmètre fonctionnel

- **18 types de documents** rangés sur **deux axes** (étape 12) :
  - `categorie` = la **famille**, qui dit qui détient le document : `conduite_permis`, `habilitations_caces`, `formations_internes` (les trois relèvent de l'exploitation) et `rh_administratif` (le RH — les diplômes y ont été rapatriés).
  - `niveau_exigence` = ce qu'on en attend : `obligatoire` (socle de tout dépanneur) / `profil` (selon le permis et les engins) / `complementaire`. Il **remplace** l'ancien `criticite` et porte à la fois le poids du score (3 / 2 / 1) et l'ordre d'affichage de la fiche.
  - Le niveau est **réglable depuis l'application** (`PATCH /api/document-types/{id}`, bouton « ⚙ Niveaux » de la fiche) : la liste des documents exigés n'était pas arrêtée au moment de la refonte. `seed_doctypes.py` ne repose donc **pas** le niveau d'un type existant, sauf `--reset-niveaux`.
  - Chaque `DocumentType` porte aussi `est_perimable` et `mode_acquisition` (upload/docusign). Seed dans `scripts/seed_doctypes.py`.
- **Pièce d'identité** (`PIECE_IDENTITE`) : CNI **ou** passeport — c'est un justificatif d'identité qui est demandé, pas une pièce précise. Renommage en place de l'ancien `CNI` (migration 0004), pour ne pas détacher les documents déjà déposés.
- **Écran d'accueil = la liste des dépanneurs** (étape 12) : une ligne par dépanneur avec son score, ses manques sur le socle, ses manquants / périmés / expirations sous 90 j. La matrice dépanneurs × 20 types a été retirée : illisible passé quelques dizaines de lignes.
- **Fiche dépanneur** = la surface de travail. Documents groupés par `niveau_exigence` (socle et « selon profil » dépliés, complémentaire replié) puis par famille à l'intérieur. Par ligne : état, date de péremption, `J-xx`, **aperçu dans l'application** (blob → `<iframe>`, le JWT interdit un `<iframe src>` direct), dépôt d'une nouvelle version, **glisser-déposer** d'un PDF sur la ligne. Les cellules grises (non applicables) ne sont pas affichées : il n'y a rien à y déposer.
- **Export ZIP** (`GET /api/documents/export`) : le dossier d'un dépanneur, ou toute la flotte avec un dossier par dépanneur. Seules les **versions courantes validées** y figurent — c'est le dossier « à jour » qu'on remet, pas l'historique. Noms de fichiers via `_download_filename` (`CODE_NOM_PRENOM_JJ.MM.AAAA.pdf`). `zipfile` de la stdlib, `ZIP_STORED` (les PDF sont déjà compressés).
- **Demandes par magic link retirées de l'interface** (2026-08-19). Le backend (`document_requests.py`, `PublicUploadView`) reste en place et fonctionnel ; la relance repassera plus tard par un **mail automatique des documents manquants**, à cadrer.
- Le code couleur historique de la matrice reste la base du calcul :
  - **Vert** : doc validé, > 90j de validité restante
  - **Orange** : doc validé, ≤ 90j de validité restante
  - **Rouge** : doc périmé OU applicable et jamais transmis
  - **Gris** : non applicable pour ce dépanneur
  - Documents **non-périmables** (RIB, CV, diplômes…) : pas de date → vert si validé, rouge si applicable et absent (jamais orange)
- Applicabilité par dépanneur via `driver_required_documents`. Le champ `profil` du dépanneur (permis B / permis C-CE) pré-coche les documents par défaut via `app/profils.py` ; l'admin ajuste ensuite case par case.
- **Scoring** (étape 10c/10d) : score de conformité par dépanneur (0-100 %), pondéré `obligatoire` ×3 / `profil` ×2 / `complementaire` ×1 (`POIDS_NIVEAU` dans `models.py`), + taux global. Conforme = cellule **verte ou orange** (le doc est valide) ; rouge = non conforme ; gris exclu du calcul.
- **Saisie des dates manuelle** (pas d'OCR — décision explicite, à reprendre plus tard)
- Workflow validation : `pending` → `validated` / `rejected` par l'admin
- Versions archivées, **jamais d'écrasement** (impératif compliance URSSAF / Inspection du travail)
- Dépanneur : **magic link à usage unique par demande**, pas de compte permanent. ⏸️ Flux conservé mais dormant (décision étape 10) — tout est admin-uploadé.
- ~~**Attestation sur l'honneur** (`ATTESTATION_PERMIS`)~~ : **abandonnée** (étape 12). Le type est supprimé par la migration 0004 — mais **seulement** si aucun document ni enveloppe n'y est rattaché, la FK `RESTRICT` protégeant les pièces de conformité. La machinerie DocuSign (`app/docusign.py`, `DocusignSection`) reste en place et branchée sur `mode_acquisition=docusign` : plus aucun type ne l'utilise, elle resservira au règlement intérieur (étape 11).
- **Liste des dépanneurs synchronisée depuis DepanTime** (étape 12). DepanTime tient les fiches de l'équipe, cette application n'en est qu'un consommateur — rien n'est jamais renvoyé vers DepanTime.
  - Source : `GET /api/habilitation-public/depanneurs` côté DepanTime (site `mtp` = le pôle Dépannage), auth par secret partagé `HABILITATION_SECRET` / `DEPANTIME_SECRET`, sur le modèle de `pilotage-public`.
  - Déclenchement : bouton « ⟳ Synchroniser DepanTime » (`POST /api/sync/depantime`) **et** cron n8n (`POST /api/internal/sync/depantime`, header `X-Internal-Secret`).
  - Ce que DepanTime possède et **écrase** à chaque passage : nom, prénom, email, date d'entrée, actif/archivé. Ce qui reste à HABILITATION : le profil de permis, l'applicabilité des documents, les documents eux-mêmes.
  - **Rien n'est supprimé** : un dépanneur archivé ou disparu de DepanTime est archivé ici, ses pièces restent consultables (rétention post-départ).
  - Un dépanneur créé par la synchro reçoit le **socle par défaut** (`profils.DOCUMENTS_PAR_DEFAUT`) : sans cela il s'afficherait 100 % conforme faute de document applicable.
  - `scripts/import_drivers_from_depantime.py` (import CSV ponctuel) reste utilisable mais est **supplanté** par la synchro.
- Rétention par défaut 5 ans post-départ (configurable)

## État actuel de la roadmap

| # | Étape | Statut |
|---|---|---|
| 1 | Schéma Postgres + scaffold FastAPI + auth admin + CRUD basics | ✅ livré |
| 2 | Frontend React + endpoint `GET /dashboard` (matrice + statuts) | ✅ livré (2026-05-14) |
| 3 | Upload admin de documents (avec chiffrement Fernet) | ✅ livré (2026-05-14) |
| 4 | Flux dépanneur (demande → magic link → upload) | ✅ livré (2026-05-14, sans envoi email — link copiable côté admin) |
| 5 | Validation admin (pending → validated/rejected) | ✅ livré (2026-05-14) |
| 6 | Relances automatiques (n8n) | ⏸️ infra backend en place mais désactivée (REMINDERS_SECRET=vide). Décision 2026-05-14 : avec ~40 dépanneurs, relance téléphone manuelle préférée. Remplacé par fonctionnalité "demande groupée par dépanneur". |
| 7 | Historique versions + export PDF "état à date T" | à faire |
| 8 | RGPD : purge configurable post-départ, log d'accès | à faire |
| 9 | Déploiement prod (sous-domaine, TLS, sauvegardes) | 🟡 backend en ligne sur https://formations.alex-worksmart.com (TLS OK), sauvegardes Postgres restant à mettre en place |
| 10 | Évolution modèle documentaire (~20 types, profils, scoring, attestation DocuSign) | ✅ livré — 10a schéma (2026-05-15), 10b profil + applicabilité (2026-05-16), docs non-périmables (2026-05-18), 10c scoring + 10d affichage dashboard (2026-05-18), 10e intégration DocuSign (2026-05-18) |
| 11 | Règlement intérieur : nouveau type (famille `rh_administratif`, pré-coché pour tous via `_COMMUNS`), signé via DocuSign avec un **2ᵉ template**. Prérequis : faire porter le template ID par chaque `DocumentType` (le code n'en gère qu'un seul, `DOCUSIGN_TEMPLATE_ID`) au lieu d'un template global. | à faire |
| 12 | Lisibilité + synchro DepanTime : liste & fiche à la place de la matrice, 4 familles × 3 niveaux d'exigence, aperçu dans l'app, export ZIP, pièce d'identité générique, retrait de l'attestation sur l'honneur et des demandes par magic link | ✅ livré (2026-08-19) |
| 13 | Mail automatique des documents manquants (remplace les demandes par magic link retirées à l'étape 12) | à cadrer |

## Conventions

- **Langue** : français pour tout ce qui est user-facing (libellés UI, messages d'erreur API, README). Code et noms techniques en anglais (variables, fonctions, classes, tables).
- **Pas de commentaires par défaut** : seulement si le WHY est non-évident (contrainte cachée, workaround, invariant subtil).
- **Pas d'over-engineering** : on construit ce qui est dans le périmètre de l'étape en cours. Pas d'abstractions anticipées pour les étapes suivantes.
- **Schéma complet dès l'étape 1** : toutes les tables MVP sont créées dans `alembic/versions/0001_initial.py`, même celles utilisées dans les étapes 3+. Cohérence du schéma > granularité des migrations. Les évolutions post-MVP (ex: `0002` à l'étape 10) ajoutent leurs propres migrations additives.
- **Pas d'écrasement de documents** : un renouvellement = une nouvelle ligne dans `document_versions`, l'ancienne reste. C'est l'invariant compliance, ne pas le casser.

## Pièges connus

- **FK circulaire** `documents.current_version_id` ↔ `document_versions.document_id` : la migration la crée en deux temps (`use_alter=True` côté modèle + `op.create_foreign_key` après les deux tables côté migration).
- **bcrypt 72 octets** : `hash_password` lève `ValueError` si le password encodé UTF-8 dépasse 72 octets. Limite native de bcrypt, pas un bug.
- **Migrations auto au démarrage** : `docker-compose.yml` lance `alembic upgrade head` avant `uvicorn`. Toute migration commitée s'applique au prochain `docker compose up`.
- **JWT subject = UUID** : `payload["sub"]` est une string ; `db.get(AdminUser, payload["sub"])` fonctionne grâce à la conversion automatique de SQLAlchemy/psycopg.
- **Préfixe `/api` côté FastAPI** : toutes les routes sont déclarées sous `/api/...` dans `app/main.py`. Le frontend tape `/api/...` directement, et nginx proxie côté prod. Si tu ajoutes un router, n'oublie pas le préfixe `/api/...`.
- **Endpoint pilotage** : `GET /api/pilotage/snapshot` (router `pilotage.py`, auth header `X-Pilotage-Secret` / variable `PILOTAGE_SECRET`) expose `score_global` au dashboard de pilotage du site web Montpellier Dépannage. Il réutilise `dashboard.get_dashboard` pour ne pas dupliquer le scoring ; désactivé (503) si `PILOTAGE_SECRET` est vide.
- **`current_version` peut pointer vers une `pending`** en théorie. Le calcul du dashboard filtre explicitement sur `statut == VALIDATED` pour éviter qu'une version pas encore validée soit considérée comme la version active.
- **Traefik certresolver = `le`** (pas `cloudflare`). Cf [memory reference-vps].
- **`date_peremption` nullable** : depuis l'étape 10, un type non-périmable (`est_perimable=False`) crée des versions sans date de péremption. L'upload rend le champ optionnel et le force à `None` si le type n'est pas périmable ; le dashboard classe ces cellules vert (validé) / rouge (absent), jamais orange. Toute logique touchant `date_peremption` doit tester `is not None`.
- **DocuSign désactivé par défaut** : si une des variables `DOCUSIGN_INTEGRATION_KEY/USER_ID/ACCOUNT_ID/PRIVATE_KEY` est vide, `settings.docusign_enabled` est `False` et les endpoints `/api/docusign/send` et `/refresh` renvoient `503`. La détection de signature est en **polling** (bouton « Rafraîchir »), pas de webhook Connect.
- **Clé privée DocuSign** : `config.docusign_private_key_pem` lit en priorité le fichier `DOCUSIGN_PRIVATE_KEY_FILE` (défaut `/app/docusign-private.key`, monté par `docker-compose.prod.yml` depuis `/srv/habilitation/docusign-private.key` — méthode DepanTime) ; à défaut, la variable `DOCUSIGN_PRIVATE_KEY` (clé sur une ligne, `\n` littéraux reconvertis).
- **Consentement DocuSign** : au premier appel, DocuSign peut exiger un consentement admin (`consent_required`). L'erreur remontée à l'admin contient l'URL à ouvrir une seule fois.
- **`external_id_depantime` = `site:id`** (ex. `mtp:7`). Chez DepanTime, `employees` a une **clé primaire composite `(id, site_id)`** : `id` seul n'est unique que par site, deux sites peuvent porter le même. Le format hérité (id nu, posé par l'ancien import CSV) est encore reconnu par `_driver_existant` et réécrit au bon format au passage.
- **`drivers.prenom` est nullable** depuis la migration 0004 : au dépannage, la fiche DepanTime ne porte souvent qu'un patronyme. Tout affichage doit tolérer `None` (`nomComplet()` côté front, `driver.prenom or ""` côté backend) — l'ancien import CSV *ignorait* ces lignes, ce qui aurait vidé la synchro.
- **`/api/documents/export` est déclarée AVANT `/{version_id}`** dans `routers/documents.py`. FastAPI résout dans l'ordre de déclaration : l'inverse ferait lire `"export"` comme un UUID et répondrait 422.

## Commandes utiles

```powershell
# Build et démarrage local
docker compose up -d --build

# Logs backend (suivre)
docker compose logs -f backend

# Seed des types de documents (18, idempotent — supprime aussi les types obsolètes,
# sauf ceux qui portent encore des documents réels). Ne repose PAS les niveaux
# d'exigence réglés depuis l'app : ajouter --reset-niveaux pour les forcer.
docker compose exec backend python -m scripts.seed_doctypes

# Synchronisation manuelle de l'équipe depuis DepanTime (sinon : bouton dans l'app)
curl -X POST -H "X-Internal-Secret: $REMINDERS_SECRET" \
     https://formations.alex-worksmart.com/api/internal/sync/depantime

# Seed demo (3 dépanneurs avec cellules de chaque couleur — DEV UNIQUEMENT)
docker compose exec backend python -m scripts.seed_demo

# Import des dépanneurs depuis un CSV exporté de DepanTime
docker compose exec backend python -m scripts.import_drivers_from_depantime --csv scripts/data/depantime_employees.csv

# Frontend en dev (hors Docker)
cd frontend && npm install && npm run dev   # http://localhost:5173

# Création d'un admin
docker compose exec backend python -m scripts.create_admin --email a@1mdp.fr --name "X" --password "..."

# Nouvelle migration (autogénérée depuis les modèles)
docker compose exec backend alembic revision --autogenerate -m "message"
docker compose exec backend alembic upgrade head

# Reset complet (PERTE DE DONNÉES)
docker compose down -v
```

## Liens

- **Repo GitHub** : https://github.com/AlexDiLorenzo/Suivi-Formations
- **Domaine prod** : https://formations.alex-worksmart.com (à activer après bootstrap VPS)
- **DepanTime** (outil voisin, source de vérité des fiches dépanneurs) : `C:\Users\alexa\Desktop\BUSINESS\MTP_DEP\DEPANTIME\depantime-project\depantime\`
- Doc OpenAPI locale : `http://localhost:8000/docs` après `docker compose up`
