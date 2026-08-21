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

- **22 types de documents** rangés sur **trois axes** (étape 14) :
  - `categorie` = la **famille**, qui dit qui détient le document : `conduite_permis`, `habilitations_caces`, `formations_internes` (les trois relèvent de l'exploitation) et `rh_administratif` (le RH — les diplômes y ont été rapatriés).
  - `niveau_exigence` = ce qu'on en attend, et il n'a plus que **deux** valeurs (étape 14) : `socle` (sans lui, le dépanneur ne roule pas — **seul niveau à compter dans le taux de conformité**) et `complementaire` (valorise le profil, suivi par un second indicateur, jamais un manquement). L'ancien niveau `profil` a disparu, et avec lui la pondération `POIDS_NIVEAU` : tous les documents du socle pèsent pareil, il n'y a pas de demi-manquement.
  - `perimetre` = à qui un document du socle s'applique : `tous`, `asf`, `poids_lourd`. **Dérivé** des attributs synchronisés, jamais coché (voir « Socle et périmètres »). Sans effet sur un complémentaire, proposé à tout le monde.
  - Les trois sont **imposés par le code** et ne sont **pas** réglables depuis l'application (`PATCH /api/document-types/{id}` et le bouton « ⚙ Niveaux » ont été retirés en 2026-08-20). Ils se règlent dans `scripts/seed_doctypes.py`, qui les réapplique tels quels à chaque passage — l'option `--reset-niveaux` n'a plus lieu d'être et a été retirée.
  - Chaque `DocumentType` porte aussi `est_perimable` et `mode_acquisition` (upload/docusign). Seed dans `scripts/seed_doctypes.py`.
- **Pièce d'identité** (`PIECE_IDENTITE`) : CNI **ou** passeport — c'est un justificatif d'identité qui est demandé, pas une pièce précise. Renommage en place de l'ancien `CNI` (migration 0004), pour ne pas détacher les documents déjà déposés.
- **Écran d'accueil = la liste des dépanneurs** (étape 12) : une ligne par dépanneur avec son score, ses manques sur le socle, ses manquants / périmés / expirations sous 90 j. La matrice dépanneurs × 20 types a été retirée : illisible passé quelques dizaines de lignes.
- **Fiche dépanneur** = la surface de travail. Documents groupés par `niveau_exigence` (socle déplié, complémentaire replié) puis par famille à l'intérieur. Par ligne : état, date de péremption, `J-xx`, **aperçu dans l'application** (blob → `<iframe>`, le JWT interdit un `<iframe src>` direct), dépôt d'une nouvelle version, **glisser-déposer** d'un PDF sur la ligne. Les cellules grises (non applicables) ne sont pas affichées : il n'y a rien à y déposer.
- **Export ZIP** (`GET /api/documents/export`) : le dossier d'un dépanneur, ou toute la flotte avec un dossier par dépanneur. Seules les **versions courantes validées** y figurent — c'est le dossier « à jour » qu'on remet, pas l'historique. Noms de fichiers via `_download_filename` (`CODE_NOM_PRENOM_JJ.MM.AAAA.pdf`). `zipfile` de la stdlib, `ZIP_STORED` (les PDF sont déjà compressés).
- **Demandes par magic link retirées de l'interface** (2026-08-19). Le backend (`document_requests.py`, `PublicUploadView`) reste en place et fonctionnel ; la relance repassera plus tard par un **mail automatique des documents manquants**, à cadrer.
- Le code couleur historique de la matrice reste la base du calcul :
  - **Vert** : doc validé, > 90j de validité restante
  - **Orange** : doc validé, ≤ 90j de validité restante
  - **Rouge** : doc périmé OU applicable et jamais transmis
  - **Gris** : non applicable pour ce dépanneur
  - Documents **non-périmables** (RIB, CV, diplômes…) : pas de date → vert si validé, rouge si applicable et absent (jamais orange)
- **Socle et périmètres** (`app/socle.py`, refondu à l'étape 14) — la ligne de partage de toute l'applicabilité. **Plus rien ne se coche nulle part.**
  - **Socle commun** (`perimetre = tous`) : permis, pièce d'identité, contrat de travail ou de mise à disposition, DPAE, carte vitale / mutuelle, formation interne 1MDP, formation initiale. Identique pour tout le monde, intérimaires compris.
  - **Socle élargi** : `perimetre = asf` (VINCI AVA, VINCI EMA — pas d'AVA, pas d'autoroute) et `perimetre = poids_lourd` (permis C/CE, revalidé tous les 5 ans avec visite médicale). Il s'ouvre selon `equipe == "asf"` et `profil_vehicule == "plateau_pl"`, **dérivés de DepanTime** (cf. `perimetres_du_driver`).
  - **Complémentaires** : FIMO/FCO, B2XL, B1VL, CACES R490/R489, autorisation de conduite, formation sécurité VINCI, autorisation de travail, CV, diplômes, RIB, justificatif de domicile. Proposés à **tout le monde** quel que soit le périmètre : il faut pouvoir déposer un CACES à quelqu'un qui vient de le passer, sans l'avoir déclaré grutier au préalable.
  - `reconcilier()` est appelée **à chaque passage de la synchro** et **retire** autant qu'elle ajoute : quitter l'équipe ASF doit cesser de compter l'AVA comme un manquement. Le seul garde-fou : un type qui porte déjà un `Document` n'est jamais retiré — l'exigence disparaît, la trace de conformité non.
  - `PATCH /api/drivers/{id}`, `PUT /api/drivers/{id}/requirements`, `POST`/`DELETE /api/requirements`, `GET /api/profils`, `app/profils.py` et `DriverProfilModal` **n'existent plus**. L'ancien réglage document par document dérivait dès la première mutation oubliée, sans que rien ne le signale : la fiche restait verte.
- **Deux indicateurs, jamais mélangés** (étape 14) :
  - **Conformité** = % du **socle applicable** acquis, code couleur rouge/orange/vert. C'est le « il roule ou il ne roule pas ». Le socle ASF n'entre au dénominateur que des ASF : un dépanneur ville n'est pas pénalisé faute d'AVA.
  - **Qualification** = fraction `n/N` des complémentaires acquis, teinte neutre. **Jamais un pourcentage** : « 4/11 » se lit comme un acquis en cours, « 36 % » comme une note ratée alors qu'aucun complémentaire n'est un manquement.
  - Acquis = cellule **verte ou orange** (le document est valide) ; rouge = manquant ou périmé ; gris (hors périmètre) exclu des deux.
- **Saisie des dates manuelle** (pas d'OCR — décision explicite, à reprendre plus tard)
- Workflow validation : `pending` → `validated` / `rejected` par l'admin
- Versions archivées, **jamais d'écrasement** (impératif compliance URSSAF / Inspection du travail)
- Dépanneur : **magic link à usage unique par demande**, pas de compte permanent. ⏸️ Flux conservé mais dormant (décision étape 10) — tout est admin-uploadé.
- ~~**Attestation sur l'honneur** (`ATTESTATION_PERMIS`)~~ : **abandonnée** (étape 12). Le type est supprimé par la migration 0004 — mais **seulement** si aucun document ni enveloppe n'y est rattaché, la FK `RESTRICT` protégeant les pièces de conformité. La machinerie DocuSign (`app/docusign.py`, `DocusignSection`) reste en place et branchée sur `mode_acquisition=docusign` : plus aucun type ne l'utilise, elle resservira au règlement intérieur (étape 11).
- **La liste des dépanneurs est le strict reflet de ses deux sources** (étape 12, durcie les 2026-08-19 et 2026-08-20). L'équipe est répartie entre deux applications et **aucune ne la connaît en entier** : **DepanTime** tient les sociétés suivies au relevé de temps (site `mtp`), **Flotte** tient l'équipe de **Pérols** (sa feuille de présence, table `presence_drivers`). La liste d'ici est l'**union des deux** ; cette application n'en est qu'un consommateur — rien n'est jamais renvoyé vers DepanTime, et **rien ne se crée ni ne se modifie ici** :
  - **Les dépanneurs sont en lecture seule, sans exception** (étape 14). `POST /api/drivers`, `POST /api/drivers/{id}/archive` et `PATCH /api/drivers/{id}` n'existent plus : il ne reste que `GET`. Tout ce qui décrit la personne vient des sources et y est réécrit à chaque passage ; ce qu'on attend d'elle en découle.
  - Sources : `GET /api/habilitation-public/depanneurs` **côté DepanTime** (site `mtp`, secrets `HABILITATION_SECRET` / `DEPANTIME_SECRET`) **et côté Flotte** (toute l'équipe de Pérols, secrets `FL_HABILITATION_SECRET` / `FLOTTE_SECRET`), toutes deux sur le modèle de `pilotage-public`. Une source dont le secret est vide est simplement ignorée.
  - **DepanTime porte `equipe`, `profil` et `interim` sur `employees`** — champs de la grille de paie (`asf`/`ville`/`reliv` ; `fourgon`/`4x4`/`plateau_vl`/`plateau_pl`), exposés par l'endpoint depuis 2026-08-21. Ce sont eux qui ouvrent le socle élargi. Vides, ils ne provoquent pas d'erreur : seulement un socle réduit au commun.
  - **Flotte ne les porte pas** : l'équipe de Pérols est réputée entièrement poids lourd, **sauf l'atelier** (`poste == "mecanicien"`, qui vaut `presence_drivers.categorie`) — un mécanicien n'a pas à produire un permis C. Règle tenue dans `_profil_vehicule`, pas dans `app/socle.py`, pour qu'elle reste visible là où elle s'applique.
  - **Si une source répond mal, la synchro échoue sans rien écrire.** Sinon toute son équipe passerait pour disparue, donc supprimée — c'est l'invariant qui protège la base.
  - Clés externes : `mtp:<id>` et `perols:<id>`. Côté Pérols, `presence_drivers.id` est un entier de séquence ; côté DepanTime la clé primaire est composite, d'où le préfixe de site des deux côtés.
  - Pérols n'a **ni prénom ni notion d'archive** : retirer quelqu'un de l'équipe efface sa ligne, donc sa fiche ici (et ses documents) à la synchro suivante. C'est le point de vigilance de ce montage.
  - **Déclenchement : le cron n8n, et lui seul** (`POST /api/internal/sync/depantime`, header `X-Internal-Secret`). Le bouton « ⟳ Synchroniser » et la route `/api/sync/depantime` ont été retirés à l'étape 14 : l'alignement de la liste et des exigences ne doit dépendre de personne, encore moins d'un clic dont l'absence se voit d'autant moins que tout a l'air à jour.
  - Ce que les sources possèdent et **écrasent** à chaque passage : nom, prénom, email, date d'entrée, actif/archivé, **équipe, type de véhicule, intérim**. Ce qui reste à HABILITATION : les documents eux-mêmes, et eux seuls.
  - **Une fiche absente des deux sources est supprimée, avec ses documents** (décision de l'exploitant, 2026-08-20). Moins brutal qu'il n'y paraît côté DepanTime, qui *archive* les partants au lieu de les effacer : ne disparaissent vraiment que les fiches erronées ou de test. Le détail, nombre de pièces perdues compris, remonte dans `hors_depantime`.
  - Un dépanneur créé par la synchro reçoit immédiatement son socle (`socle.reconcilier`) : sans cela il s'afficherait 100 % conforme faute de document applicable.
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
| 14 | Refonte au standard métier : socle / complémentaire (fin du niveau `profil`), périmètres `asf` et `poids_lourd` dérivés de DepanTime, deux indicateurs (conformité au socle + qualification), fin de tout réglage manuel, synchro sans bouton | ✅ livré (2026-08-21) |

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
- **En prod, toujours `-f docker-compose.prod.yml`.** Le compose par défaut est celui de dev : il ne déclare **que** `postgres` et `backend`. Un `docker compose up -d --build` sans le `-f` en prod reconstruit le backend, laisse `habilitation-frontend` en **orphelin** sur son ancienne image (seul un `WARN ... Found orphan containers` le signale) et expose Postgres sur le port 5432. Le front continue alors de servir l'ancien bundle : l'application répond 200 mais affiche des fiches vides, l'ancien JavaScript ne connaissant pas le niveau `socle`. Arrivé le 2026-08-21 lors du déploiement de l'étape 14.
- **`REMINDERS_SECRET` est devenu indispensable** (étape 14). Il garde tout `/api/internal/*`, synchro comprise (`deps.verify_internal_secret` répond 503 s'il est vide). Tant qu'il servait aux seules relances — désactivées par décision — le laisser vide était sans conséquence ; maintenant que le bouton a disparu, un secret vide veut dire **plus aucune synchronisation possible**, sans le moindre message dans l'application : la liste se fige et personne ne le voit.
- **Ordre de déploiement de l'étape 14** : DepanTime d'abord (l'endpoint doit exposer `equipe`/`profil`), puis HABILITATION, puis `seed_doctypes`, puis la synchro. Dans le désordre, `equipe` et `profil` arrivent vides et personne n'obtient le socle élargi — sans erreur visible, les fiches ASF s'affichent simplement conformes à tort.
- **`equipe` et `profil` sont du texte libre côté HABILITATION**, pas des enums : seules les valeurs `asf` et `plateau_pl` portent une conséquence (`EQUIPE_ASF`, `PROFIL_VEHICULE_POIDS_LOURD` dans `models.py`). DepanTime reste libre d'ajouter une équipe ou un type de véhicule sans rien casser ici.
- **La synchro retire des exigences, désormais.** `socle.reconcilier` supprime les `DriverRequiredDocument` hors périmètre — sauf si un `Document` y est rattaché. Toute évolution de cette fonction doit garder ce garde-fou : sans lui, une mutation d'équipe effacerait la trace d'un CACES réellement détenu.

## Commandes utiles

```powershell
# Déploiement en prod (VPS) — le -f n'est PAS optionnel, cf. pièges connus.
# Sans lui, seul le backend est reconstruit et le frontend reste sur l'ancienne image.
#   cd /srv/habilitation && git pull && docker compose -f docker-compose.prod.yml up -d --build
#   docker compose -f docker-compose.prod.yml exec backend python -m scripts.seed_doctypes
#   curl -X POST -H "X-Internal-Secret: $REMINDERS_SECRET" \
#        https://formations.alex-worksmart.com/api/internal/sync/depantime
# Le compose de prod n'expose aucun port sur l'hôte : la synchro s'appelle par le
# domaine, pas par localhost:8000 (qui répond « connexion refusée »).

# Build et démarrage local
docker compose up -d --build

# Logs backend (suivre)
docker compose logs -f backend

# Seed des types de documents (22, idempotent — repose niveau et périmètre à
# chaque passage, et supprime les types obsolètes sauf ceux qui portent encore
# des documents réels). À relancer AVANT la synchro : c'est elle qui pose ensuite
# les exigences correspondantes sur chaque dépanneur.
docker compose exec backend python -m scripts.seed_doctypes

# Synchronisation de l'équipe : plus de bouton dans l'app, le cron n8n s'en
# charge. Ce curl reste la seule façon de la déclencher à la main.
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
