import { useCallback, useEffect, useState } from 'react'
import { api, clearToken, getToken, setToken } from './api.js'

const MONTHS_FR = [
  'JANVIER', 'FÉVRIER', 'MARS', 'AVRIL', 'MAI', 'JUIN',
  'JUILLET', 'AOÛT', 'SEPTEMBRE', 'OCTOBRE', 'NOVEMBRE', 'DÉCEMBRE',
]

const DS_STATUS_LABEL = {
  created: 'Créée',
  sent: 'Envoyée, en attente de signature',
  delivered: 'Ouverte par le dépanneur',
  signed: 'Signée',
  completed: 'Signée et archivée',
  declined: 'Refusée par le dépanneur',
  voided: 'Annulée',
}

const DS_TERMINAL = ['completed', 'declined', 'voided']
const DS_IN_PROGRESS = ['created', 'sent', 'delivered', 'signed']

// Les quatre familles : qui detient le document. La premiere releve du service
// RH, les trois autres de l'exploitation.
const CATEGORIE_ORDER = [
  'conduite_permis',
  'habilitations_caces',
  'formations_internes',
  'rh_administratif',
]

const CATEGORIE_LABEL = {
  conduite_permis: 'Conduite & permis',
  habilitations_caces: 'Habilitations & CACES',
  formations_internes: 'Formations internes',
  rh_administratif: 'RH & administratif',
}

const CATEGORIE_DEFAUT = 'rh_administratif'

const POLE_LABEL = {
  conduite_permis: 'Exploitation',
  habilitations_caces: 'Exploitation',
  formations_internes: 'Exploitation',
  rh_administratif: 'RH',
}

// Ce qui decide de l'ordre de la fiche : le socle d'abord, le reste replie.
const NIVEAU_ORDER = ['obligatoire', 'profil', 'complementaire']

const NIVEAU_LABEL = {
  obligatoire: 'Socle obligatoire',
  profil: 'Selon le profil',
  complementaire: 'Complementaire',
}

const NIVEAU_AIDE = {
  obligatoire: 'Attendu de tout depanneur, sans exception.',
  profil: 'Attendu selon le permis et les engins conduits.',
  complementaire: 'Utile a conserver ; son absence n\'est pas un manquement.',
}

// Seul le socle est deplie d'entree : c'est ce qu'on vient verifier en premier.
const NIVEAU_OUVERT_PAR_DEFAUT = { obligatoire: true, profil: true, complementaire: false }

function formatDateFr(iso) {
  if (!iso) return ''
  const [y, m, d] = iso.split('-')
  return `${d}/${m}/${y}`
}

function scoreClass(score) {
  if (score == null) return 'grey'
  if (score >= 90) return 'green'
  if (score >= 60) return 'orange'
  return 'red'
}

function nomComplet(driver) {
  return [driver?.nom, driver?.prenom].filter(Boolean).join(' ')
}

function formatTaille(octets) {
  if (!octets && octets !== 0) return ''
  if (octets < 1024) return `${octets} o`
  if (octets < 1024 * 1024) return `${Math.round(octets / 1024)} ko`
  return `${(octets / (1024 * 1024)).toFixed(1)} Mo`
}

// Compteurs d'une ligne de la liste : ce qui manque, ce qui va expirer.
function compterCellules(cells, docTypeById) {
  const total = { manquants: 0, perimes: 0, expirent: 0, applicables: 0, valides: 0 }
  for (const c of cells) {
    if (c.status === 'grey') continue
    total.applicables += 1
    if (c.status === 'red') {
      if (c.reason === 'expired') total.perimes += 1
      else total.manquants += 1
    } else {
      total.valides += 1
      if (c.status === 'orange') total.expirent += 1
    }
  }
  // Un manque sur le socle obligatoire ne pese pas comme un manque sur un
  // document complementaire : on le remonte a part pour la liste.
  total.manquantsObligatoires = cells.filter((c) => {
    if (c.status !== 'red') return false
    const dt = docTypeById[c.document_type_id]
    return dt?.niveau_exigence === 'obligatoire'
  }).length
  return total
}

// Date de peremption calculee depuis l'emission et la duree de validite du type.
function peremptionCalculee(dateEmission, dureeJours) {
  if (!dateEmission || !dureeJours) return ''
  const d = new Date(`${dateEmission}T00:00:00`)
  if (Number.isNaN(d.getTime())) return ''
  d.setDate(d.getDate() + dureeJours)
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

function dureeLisible(jours) {
  if (!jours) return null
  if (jours % 365 === 0) return `${jours / 365} an${jours / 365 > 1 ? 's' : ''}`
  if (jours % 30 === 0) return `${jours / 30} mois`
  return `${jours} jours`
}

// =====================================================================
// Login
// =====================================================================

function LoginView({ onLogin }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const { access_token } = await api.login(email, password)
      setToken(access_token)
      onLogin()
    } catch (err) {
      setError(err.detail || 'Erreur de connexion')
    } finally {
      setLoading(false)
    }
  }

  // Gabarit commun a toutes les applications :
  // PLATEFORME_APPLICATIONS/brand/patterns/ecran-connexion.jsx
  const T = {
    fond: '#F1EFE8', carte: '#fff', bord: '#D3D1C7', encre: '#1A190F',
    gris: '#888780', grisFonce: '#5F5E5A', vert: '#2C6126',
    jaune: '#E4E13C', rouge: '#A32D2D',
    titre: "'Space Mono', monospace", corps: "'DM Sans', sans-serif",
  }
  const styleChamp = {
    width: '100%', padding: '10px 12px', borderRadius: 8,
    border: `1px solid ${T.bord}`, fontSize: 14, fontFamily: T.corps,
    margin: '6px 0 12px', boxSizing: 'border-box',
  }
  const styleLabel = {
    fontSize: 10, fontWeight: 700, color: T.gris,
    textTransform: 'uppercase', letterSpacing: '0.07em',
  }

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center',
      justifyContent: 'center', background: T.fond,
      fontFamily: T.corps, padding: 20,
    }}>
      <form onSubmit={handleSubmit} style={{
        background: T.carte, borderRadius: 12, padding: 36,
        width: 360, maxWidth: '100%', border: `1px solid ${T.bord}`,
        boxShadow: '0 10px 40px rgba(26,25,15,0.15)',
      }}>
        <div style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center',
          gap: 12, marginBottom: 24,
        }}>
          <img src="/logo.png" alt="Montpellier Depannage"
               style={{ width: 168, maxWidth: '100%', height: 'auto' }} />
          <div style={{ textAlign: 'center' }}>
            <div style={{
              fontSize: 22, fontWeight: 700, fontFamily: T.titre,
              color: T.encre, letterSpacing: '-0.02em',
            }}>Habilitation</div>
            <div style={{
              fontSize: 10, color: T.gris, textTransform: 'uppercase',
              letterSpacing: '0.1em', fontWeight: 700,
            }}>Formations et conformité</div>
          </div>
        </div>
        <div className="field">
          <label htmlFor="login-email">Email</label>
          <input
            id="login-email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            required
          />
        </div>
        <div className="field">
          <label htmlFor="login-password">Mot de passe</label>
          <input
            id="login-password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </div>
        {error && <p style={{ color: T.rouge, fontSize: 12, marginBottom: 12 }}>{error}</p>}
        <button type="submit" disabled={loading} style={{
          width: '100%', padding: '12px 0', borderRadius: 8, border: 'none',
          background: T.vert, color: '#fff', fontWeight: 700, fontSize: 14,
          fontFamily: T.corps, cursor: loading ? 'wait' : 'pointer',
          boxShadow: '0 4px 14px rgba(44,97,38,0.30)',
        }}>
          {loading ? 'Connexion…' : 'Se connecter'}
        </button>

        <div style={{
          marginTop: 18, padding: '8px 12px', background: T.jaune,
          borderRadius: 6, fontSize: 11, color: T.encre, fontWeight: 700,
          textAlign: 'center',
        }}>
          24 / 7 · DÉPANNAGE MONTPELLIER
        </div>
      </form>
    </div>
  )
}

// =====================================================================
// Dashboard
// =====================================================================

function ScoreBadge({ score }) {
  if (score == null) return <span className="score-badge grey">—</span>
  return <span className={`score-badge ${scoreClass(score)}`}>{score}%</span>
}

// =====================================================================
// Aperçu d'un document (sans quitter l'application)
// =====================================================================

function DocViewerModal({ versionId, titre, onClose }) {
  const [doc, setDoc] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let objectUrl = null
    let annule = false
    api.documents
      .openBlob(versionId)
      .then((r) => {
        if (annule) {
          URL.revokeObjectURL(r.url)
          return
        }
        objectUrl = r.url
        setDoc(r)
      })
      .catch((e) => setError(e.detail || String(e)))
    return () => {
      annule = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [versionId])

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card modal-viewer" onClick={(e) => e.stopPropagation()}>
        <header className="modal-header">
          <h2>{titre}</h2>
          <div className="viewer-actions">
            {doc && (
              <>
                <span className="muted">{formatTaille(doc.size)}</span>
                <a className="btn btn-ghost btn-sm" href={doc.url} target="_blank" rel="noreferrer">
                  Ouvrir dans un onglet
                </a>
                <a className="btn btn-ghost btn-sm" href={doc.url} download={doc.filename}>
                  Télécharger
                </a>
              </>
            )}
            <button type="button" className="icon-btn" onClick={onClose} aria-label="Fermer">×</button>
          </div>
        </header>
        <div className="viewer-body">
          {error && <div className="error">{error}</div>}
          {!doc && !error && <div className="empty">Chargement du document…</div>}
          {doc && (
            doc.type.startsWith('image/') ? (
              <img src={doc.url} alt={doc.filename} />
            ) : (
              <iframe src={doc.url} title={doc.filename} />
            )
          )}
        </div>
      </div>
    </div>
  )
}

// =====================================================================
// Liste des dépanneurs (écran d'accueil)
// =====================================================================

function PastilleEtat({ compte, ton, libelle }) {
  if (!compte) return <span className="pastille vide">—</span>
  return (
    <span className={`pastille ${ton}`} title={libelle}>
      {compte}
    </span>
  )
}

function DriversListView({ docTypes, onOuvrirFiche, rafraichir, data, onSync, syncStatut, syncEnCours }) {
  const [recherche, setRecherche] = useState('')
  const [filtre, setFiltre] = useState('tous')
  const [exportEnCours, setExportEnCours] = useState(false)
  const [message, setMessage] = useState('')

  const docTypeById = Object.fromEntries(docTypes.map((dt) => [dt.id, dt]))

  async function exporterTout() {
    setMessage('')
    setExportEnCours(true)
    try {
      await api.documents.exportZip({})
    } catch (err) {
      setMessage(err.detail || 'Erreur lors de l\'export')
    } finally {
      setExportEnCours(false)
    }
  }

  if (!data) return <div className="empty">Chargement…</div>

  const lignes = data.drivers.map((d) => ({ driver: d, compte: compterCellules(d.cells, docTypeById) }))
  const q = recherche.trim().toLowerCase()
  const visibles = lignes.filter(({ driver, compte }) => {
    if (q && !nomComplet(driver).toLowerCase().includes(q)) return false
    if (filtre === 'incomplets') return compte.manquants + compte.perimes > 0
    if (filtre === 'socle') return compte.manquantsObligatoires > 0
    if (filtre === 'expirent') return compte.expirent > 0
    return true
  })

  const compteurs = {
    incomplets: lignes.filter((l) => l.compte.manquants + l.compte.perimes > 0).length,
    socle: lignes.filter((l) => l.compte.manquantsObligatoires > 0).length,
    expirent: lignes.filter((l) => l.compte.expirent > 0).length,
  }

  return (
    <>
      <div className="entete-page">
        <div>
          <h2>Dépanneurs</h2>
          <p className="muted">
            {data.drivers.length} actifs · conformité globale{' '}
            {data.summary.score_global != null ? `${data.summary.score_global}%` : '—'}
          </p>
        </div>
        <div className="entete-actions">
          {syncStatut?.active && (
            <button className="btn btn-ghost" onClick={onSync} disabled={syncEnCours}
              title="Aligner la liste sur l'équipe du dépannage dans DepanTime">
              {syncEnCours ? 'Synchronisation…' : '⟳ Synchroniser DepanTime'}
            </button>
          )}
          <button className="btn btn-ghost" onClick={exporterTout} disabled={exportEnCours}
            title="Archive ZIP de tous les documents à jour, un dossier par dépanneur">
            {exportEnCours ? 'Préparation…' : '⬇ Tout exporter (ZIP)'}
          </button>
        </div>
      </div>

      {message && <div className="error">{message}</div>}

      <div className="barre-filtres">
        <input
          className="recherche"
          type="search"
          placeholder="Rechercher un dépanneur…"
          value={recherche}
          onChange={(e) => setRecherche(e.target.value)}
        />
        {[
          { cle: 'tous', libelle: 'Tous' },
          { cle: 'socle', libelle: 'Socle incomplet', compte: compteurs.socle, ton: 'red' },
          { cle: 'incomplets', libelle: 'Manquants ou périmés', compte: compteurs.incomplets, ton: 'red' },
          { cle: 'expirent', libelle: 'Expirent sous 90 j', compte: compteurs.expirent, ton: 'orange' },
        ].map((f) => (
          <button
            key={f.cle}
            type="button"
            className={`filter-btn ${filtre === f.cle ? 'active' : ''}`}
            onClick={() => setFiltre(f.cle)}
          >
            {f.libelle}
            {f.compte != null && <span className="filter-count">{f.compte}</span>}
          </button>
        ))}
        <button type="button" className="btn btn-ghost btn-sm" onClick={rafraichir}>Actualiser</button>
      </div>

      {visibles.length === 0 ? (
        <div className="empty">Aucun dépanneur ne correspond.</div>
      ) : (
        <div className="liste-depanneurs">
          <div className="ligne-depanneur entete">
            <span>Dépanneur</span>
            <span>Conformité</span>
            <span className="col-num">Socle</span>
            <span className="col-num">Manquants</span>
            <span className="col-num">Périmés</span>
            <span className="col-num">Expirent</span>
            <span />
          </div>
          {visibles.map(({ driver, compte }) => (
            <button
              type="button"
              key={driver.id}
              className="ligne-depanneur"
              onClick={() => onOuvrirFiche(driver.id)}
            >
              <span className="nom">
                <strong>{driver.nom}</strong> {driver.prenom || ''}
              </span>
              <span className="conformite">
                <ScoreBadge score={driver.score} />
                <span className="barre-score">
                  <span
                    className={`remplissage ${scoreClass(driver.score)}`}
                    style={{ width: `${driver.score ?? 0}%` }}
                  />
                </span>
              </span>
              <span className="col-num">
                <PastilleEtat compte={compte.manquantsObligatoires} ton="red"
                  libelle="documents du socle obligatoire manquants" />
              </span>
              <span className="col-num">
                <PastilleEtat compte={compte.manquants} ton="red" libelle="jamais transmis" />
              </span>
              <span className="col-num">
                <PastilleEtat compte={compte.perimes} ton="red" libelle="périmés" />
              </span>
              <span className="col-num">
                <PastilleEtat compte={compte.expirent} ton="orange" libelle="expirent sous 90 jours" />
              </span>
              <span className="chevron">→</span>
            </button>
          ))}
        </div>
      )}
    </>
  )
}

// =====================================================================
// Fiche d'un dépanneur
// =====================================================================

function LigneDocument({ docType, cell, onDeposer, onVoir, reglage, onChangerNiveau }) {
  const [survol, setSurvol] = useState(false)
  const absent = cell.status === 'red'
  const perime = absent && cell.reason === 'expired'

  function onDrop(e) {
    e.preventDefault()
    setSurvol(false)
    const fichier = e.dataTransfer.files?.[0]
    if (fichier) onDeposer(fichier)
  }

  return (
    <div
      className={`ligne-doc ${cell.status} ${survol ? 'survol' : ''}`}
      onDragOver={(e) => { e.preventDefault(); setSurvol(true) }}
      onDragLeave={() => setSurvol(false)}
      onDrop={onDrop}
    >
      <span className="doc-libelle">
        {docType.libelle}
        <span className="doc-categorie">{CATEGORIE_LABEL[docType.categorie] || '—'}</span>
      </span>

      <span className="doc-etat">
        {absent ? (
          <span className={`etat ${perime ? 'perime' : 'manquant'}`}>
            {perime
              ? `Périmé depuis ${-cell.days_until_expiry} j`
              : 'Jamais transmis'}
          </span>
        ) : (
          <>
            <span className={`etat ${cell.status}`}>
              {cell.date_peremption ? formatDateFr(cell.date_peremption) : 'Valide'}
            </span>
            {cell.days_until_expiry != null && (
              <span className="compte-a-rebours">J-{cell.days_until_expiry}</span>
            )}
          </>
        )}
        {cell.has_pending_version && <span className="tag tag-pending">à valider</span>}
      </span>

      {reglage ? (
        <span className="doc-actions">
          <select
            value={docType.niveau_exigence}
            onChange={(e) => onChangerNiveau(docType, e.target.value)}
            title="Niveau d'exigence de ce document"
          >
            {NIVEAU_ORDER.map((n) => (
              <option key={n} value={n}>{NIVEAU_LABEL[n]}</option>
            ))}
          </select>
        </span>
      ) : (
        <span className="doc-actions">
          {cell.current_version_id && (
            <button type="button" className="btn btn-ghost btn-sm"
              onClick={() => onVoir(cell.current_version_id)} title="Voir le document">
              Voir
            </button>
          )}
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => onDeposer(null)}>
            {cell.current_version_id ? 'Remplacer' : 'Déposer'}
          </button>
        </span>
      )}
    </div>
  )
}

function DriverSheetView({ driverId, docTypes, data, onRetour, rafraichir, onModifier }) {
  const [ouvertes, setOuvertes] = useState(NIVEAU_OUVERT_PAR_DEFAUT)
  const [upload, setUpload] = useState(null)   // { docType, cell, fichier }
  const [apercu, setApercu] = useState(null)   // { versionId, titre }
  const [exportEnCours, setExportEnCours] = useState(false)
  const [reglage, setReglage] = useState(false)
  const [message, setMessage] = useState('')

  const driver = data?.drivers.find((d) => d.id === driverId)
  const docTypeById = Object.fromEntries(docTypes.map((dt) => [dt.id, dt]))

  async function exporterFiche() {
    setMessage('')
    setExportEnCours(true)
    try {
      await api.documents.exportZip({ driverId })
    } catch (err) {
      setMessage(err.detail || 'Erreur lors de l\'export')
    } finally {
      setExportEnCours(false)
    }
  }

  async function changerNiveau(docType, niveau) {
    setMessage('')
    try {
      await api.updateDocType(docType.id, { niveau_exigence: niveau })
      rafraichir()
    } catch (err) {
      setMessage(err.detail || 'Erreur lors du changement de niveau')
    }
  }

  if (!driver) {
    return (
      <div className="empty">
        Dépanneur introuvable ou archivé. <button className="btn btn-ghost btn-sm" onClick={onRetour}>Retour</button>
      </div>
    )
  }

  const compte = compterCellules(driver.cells, docTypeById)

  // Cellules applicables uniquement : le gris (non applicable) n'a rien à faire
  // sur la fiche, il n'y a rien à y déposer.
  const applicables = driver.cells
    .map((c) => ({ cell: c, docType: docTypeById[c.document_type_id] }))
    .filter((x) => x.docType && x.cell.status !== 'grey')

  const parNiveau = NIVEAU_ORDER.map((niveau) => {
    const items = applicables.filter((x) => x.docType.niveau_exigence === niveau)
    const parCategorie = CATEGORIE_ORDER.map((cat) => ({
      cat,
      items: items
        .filter((x) => (x.docType.categorie || CATEGORIE_DEFAUT) === cat)
        .sort((a, b) => a.docType.display_order - b.docType.display_order),
    })).filter((g) => g.items.length > 0)
    const ok = items.filter((x) => x.cell.status !== 'red').length
    return { niveau, items, parCategorie, ok }
  }).filter((g) => g.items.length > 0)

  const nonApplicables = driver.cells.filter((c) => c.status === 'grey').length

  return (
    <>
      <div className="fil-ariane">
        <button type="button" className="btn btn-ghost btn-sm" onClick={onRetour}>← Dépanneurs</button>
      </div>

      <div className="entete-fiche">
        <div>
          <h2>{driver.nom} {driver.prenom || ''}</h2>
          <p className="muted">
            {driver.email || 'Pas d\'email'}
            {driver.profil ? ` · ${driver.profil === 'permis_c_ce' ? 'Permis C/CE' : 'Permis B'}` : ' · profil non renseigné'}
            {nonApplicables > 0 && ` · ${nonApplicables} document(s) non applicable(s)`}
          </p>
        </div>
        <div className="entete-actions">
          <span className={`score-badge ${scoreClass(driver.score)}`}>
            {driver.score != null ? `${driver.score}%` : '—'}
          </span>
          <button className="btn btn-ghost" onClick={() => onModifier(driver)}>Modifier la fiche</button>
          <button className="btn btn-ghost" onClick={exporterFiche} disabled={exportEnCours}
            title="Archive ZIP des documents à jour, nommés proprement">
            {exportEnCours ? 'Préparation…' : '⬇ Dossier ZIP'}
          </button>
          <button
            className={`btn btn-ghost ${reglage ? 'actif' : ''}`}
            onClick={() => setReglage((v) => !v)}
            title="Régler quels documents sont obligatoires"
          >
            ⚙ Niveaux
          </button>
        </div>
      </div>

      <div className="resume-fiche">
        <span><strong>{compte.valides}</strong> / {compte.applicables} à jour</span>
        {compte.manquantsObligatoires > 0 && (
          <span className="alerte">{compte.manquantsObligatoires} manque(s) sur le socle</span>
        )}
        {compte.perimes > 0 && <span className="alerte">{compte.perimes} périmé(s)</span>}
        {compte.expirent > 0 && <span className="attention">{compte.expirent} expire(nt) sous 90 j</span>}
      </div>

      {message && <div className="error">{message}</div>}
      {reglage && (
        <div className="bandeau-info">
          Réglage des niveaux : ce choix vaut pour <strong>tous</strong> les dépanneurs, pas
          seulement celui-ci.
        </div>
      )}

      {parNiveau.map(({ niveau, items, parCategorie, ok }) => (
        <section key={niveau} className={`bloc-niveau ${niveau}`}>
          <button
            type="button"
            className="entete-bloc"
            onClick={() => setOuvertes((o) => ({ ...o, [niveau]: !o[niveau] }))}
          >
            <span className="chevron-bloc">{ouvertes[niveau] ? '▼' : '▶'}</span>
            <span className="titre-bloc">{NIVEAU_LABEL[niveau]}</span>
            <span className="aide-bloc">{NIVEAU_AIDE[niveau]}</span>
            <span className={`compteur-bloc ${ok === items.length ? 'complet' : 'incomplet'}`}>
              {ok}/{items.length}
            </span>
          </button>

          {ouvertes[niveau] && (
            <div className="corps-bloc">
              {parCategorie.map(({ cat, items: docs }) => (
                <div key={cat} className="groupe-categorie">
                  <h4>
                    {CATEGORIE_LABEL[cat]}
                    <span className="pole">{POLE_LABEL[cat]}</span>
                  </h4>
                  {docs.map(({ docType, cell }) => (
                    <LigneDocument
                      key={docType.id}
                      docType={docType}
                      cell={cell}
                      reglage={reglage}
                      onChangerNiveau={changerNiveau}
                      onVoir={(versionId) => setApercu({ versionId, titre: docType.libelle })}
                      onDeposer={(fichier) => setUpload({ docType, cell, fichier })}
                    />
                  ))}
                </div>
              ))}
            </div>
          )}
        </section>
      ))}

      {upload && (
        <UploadModal
          driver={driver}
          docType={upload.docType}
          fichierInitial={upload.fichier}
          currentVersionId={upload.cell.current_version_id}
          pendingVersionId={upload.cell.pending_version_id}
          onVoir={(versionId, titre) => setApercu({ versionId, titre })}
          onClose={() => { setUpload(null); rafraichir() }}
          onUploaded={() => { setUpload(null); rafraichir() }}
        />
      )}
      {apercu && (
        <DocViewerModal
          versionId={apercu.versionId}
          titre={apercu.titre}
          onClose={() => setApercu(null)}
        />
      )}
    </>
  )
}

function DocusignSection({ driver, docType }) {
  const now = new Date()
  const [envelope, setEnvelope] = useState(undefined) // undefined = chargement, null = aucune
  const [mois, setMois] = useState(MONTHS_FR[now.getMonth()])
  const [annee, setAnnee] = useState(now.getFullYear())
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    api.docusign
      .getEnvelope(driver.id, docType.id)
      .then((e) => setEnvelope(e))
      .catch((err) => {
        setEnvelope(null)
        setError(err.detail || String(err))
      })
  }, [driver.id, docType.id])

  const inProgress = envelope && DS_IN_PROGRESS.includes(envelope.status)

  async function handleSend() {
    setError('')
    setBusy(true)
    try {
      const e = await api.docusign.send({
        driverId: driver.id,
        documentTypeId: docType.id,
        mois,
        annee,
      })
      setEnvelope(e)
    } catch (err) {
      setError(err.detail || 'Erreur lors de l\'envoi DocuSign')
    } finally {
      setBusy(false)
    }
  }

  async function handleRefresh() {
    setError('')
    setBusy(true)
    try {
      const e = await api.docusign.refresh(envelope.id)
      setEnvelope(e)
    } catch (err) {
      setError(err.detail || 'Erreur lors du rafraichissement du statut')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="section">
      <h3>Signature DocuSign</h3>
      <p className="hint">
        L'attestation sur l'honneur est signee electroniquement par le
        depanneur via DocuSign : il recoit un email, signe, et le document
        signe est archive automatiquement ici.
      </p>

      {error && <div className="error">{error}</div>}

      {envelope === undefined && <p className="hint">Chargement…</p>}

      {envelope && (
        <div className={`ds-status ds-${envelope.status}`}>
          <strong>{DS_STATUS_LABEL[envelope.status] || envelope.status}</strong>
          <span className="ds-meta">
            {envelope.mois} {envelope.annee} · {envelope.recipient_email}
          </span>
          {inProgress && (
            <button
              type="button"
              className="btn btn-sm"
              onClick={handleRefresh}
              disabled={busy}
            >
              {busy ? '…' : 'Rafraichir le statut'}
            </button>
          )}
        </div>
      )}

      {envelope !== undefined && !inProgress && (
        !driver.email ? (
          <div className="email-status warn">
            Ce depanneur n'a pas d'email — ajoute-le dans sa fiche avant
            d'envoyer l'attestation a signer.
          </div>
        ) : (
          <>
            <div className="grid-2">
              <div className="field">
                <label>Mois</label>
                <select value={mois} onChange={(e) => setMois(e.target.value)}>
                  {MONTHS_FR.map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label>Annee</label>
                <input
                  type="number"
                  value={annee}
                  min="2000"
                  max="2100"
                  onChange={(e) => setAnnee(Number(e.target.value))}
                />
              </div>
            </div>
            <button type="button" className="btn" onClick={handleSend} disabled={busy}>
              {busy
                ? 'Envoi…'
                : envelope
                  ? 'Renvoyer pour signature'
                  : 'Envoyer pour signature'}
            </button>
          </>
        )
      )}
    </div>
  )
}

function UploadModal({
  driver, docType, currentVersionId, pendingVersionId, fichierInitial,
  onVoir, onClose, onUploaded,
}) {
  const [file, setFile] = useState(fichierInitial || null)
  const [dateEmission, setDateEmission] = useState('')
  const [datePeremption, setDatePeremption] = useState('')
  const [peremptionTouched, setPeremptionTouched] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const [pendingVersion, setPendingVersion] = useState(null)
  const [reviewing, setReviewing] = useState(false)

  useEffect(() => {
    if (!pendingVersionId) {
      setPendingVersion(null)
      return
    }
    api.documents.get(pendingVersionId).then(setPendingVersion).catch(() => {})
  }, [pendingVersionId])

  async function handleValidate() {
    if (!confirm('Valider cette version ? Elle deviendra la version courante.')) return
    setError('')
    setReviewing(true)
    try {
      await api.documents.validate(pendingVersionId)
      onUploaded()
    } catch (err) {
      setError(err.detail || 'Erreur lors de la validation')
      setReviewing(false)
    }
  }

  async function handleReject() {
    const reason = prompt('Motif du rejet :')
    if (reason === null) return
    if (reason.trim().length < 3) {
      alert('Le motif doit contenir au moins 3 caractères.')
      return
    }
    setError('')
    setReviewing(true)
    try {
      await api.documents.reject(pendingVersionId, reason.trim())
      onUploaded()
    } catch (err) {
      setError(err.detail || 'Erreur lors du rejet')
      setReviewing(false)
    }
  }

  const duree = docType?.duree_validite_jours_default

  function handleEmissionChange(value) {
    setDateEmission(value)
    if (!peremptionTouched) {
      const calculee = peremptionCalculee(value, duree)
      if (calculee) setDatePeremption(calculee)
    }
  }

  function handlePeremptionChange(value) {
    setPeremptionTouched(true)
    setDatePeremption(value)
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    if (!file) {
      setError('Sélectionne un fichier PDF')
      return
    }
    setUploading(true)
    try {
      await api.documents.upload({
        driverId: driver.id,
        documentTypeId: docType.id,
        dateEmission,
        datePeremption,
        file,
      })
      onUploaded()
    } catch (err) {
      setError(err.detail || 'Erreur lors de l\'upload')
      setUploading(false)
    }
  }

  const perimable = docType?.est_perimable !== false

  return (
    <div className="modal-overlay" onClick={onClose}>
      <form className="modal-card" onClick={(e) => e.stopPropagation()} onSubmit={handleSubmit}>
        <header className="modal-header">
          <h2>{docType?.libelle}</h2>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Fermer">×</button>
        </header>

        <div className="modal-body">
          <p className="hint">
            <strong>{driver.nom} {driver.prenom || ''}</strong>
            {' · '}{CATEGORIE_LABEL[docType?.categorie] || docType?.code}
            {' · '}{NIVEAU_LABEL[docType?.niveau_exigence]}
          </p>

          {pendingVersionId && (
            <div className="pending-block">
              <div className="pending-header">
                <span className="tag tag-pending">⏳ Version en attente de validation</span>
              </div>
              {pendingVersion ? (
                <ul className="pending-meta">
                  <li>
                    Déposée par <strong>{pendingVersion.uploaded_by === 'driver' ? 'le dépanneur' : 'un admin'}</strong>
                    {' '}le {formatDateFr(pendingVersion.uploaded_at.slice(0, 10))}
                  </li>
                  <li>
                    Émission : <strong>{formatDateFr(pendingVersion.date_emission)}</strong>
                    {' · '}
                    {pendingVersion.date_peremption ? (
                      <>Péremption : <strong>{formatDateFr(pendingVersion.date_peremption)}</strong></>
                    ) : (
                      <span className="hint">Non périmable</span>
                    )}
                  </li>
                  <li>{pendingVersion.original_filename} ({formatTaille(pendingVersion.file_size_bytes)})</li>
                </ul>
              ) : (
                <p className="hint">Chargement des détails…</p>
              )}
              <div className="pending-actions">
                <button type="button" className="btn btn-ghost btn-sm"
                  onClick={() => onVoir(pendingVersionId, `${docType.libelle} (en attente)`)}>
                  Voir
                </button>
                <button type="button" className="btn btn-sm" onClick={handleValidate} disabled={reviewing}>
                  Valider
                </button>
                <button type="button" className="btn btn-ghost btn-sm danger" onClick={handleReject} disabled={reviewing}>
                  Rejeter
                </button>
              </div>
            </div>
          )}

          {currentVersionId && (
            <div className="info-block">
              <span>Une version est déjà en base ; le dépôt en crée une nouvelle sans l'écraser.</span>
              <button type="button" className="btn btn-ghost btn-sm"
                onClick={() => onVoir(currentVersionId, docType.libelle)}>
                Voir la version actuelle
              </button>
            </div>
          )}

          {docType?.mode_acquisition === 'docusign' && (
            <DocusignSection driver={driver} docType={docType} />
          )}

          <div className="section">
            <h3>{currentVersionId ? 'Nouvelle version' : 'Dépôt du document'}</h3>

            <div className="field">
              <label>Fichier (PDF, max 10 Mo) *</label>
              <input
                type="file"
                accept="application/pdf"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
                required={!file}
              />
              {file && <p className="hint">{file.name} — {formatTaille(file.size)}</p>}
            </div>

            <div className="grid-2">
              <div className="field">
                <label>Date d'émission *</label>
                <input
                  type="date"
                  value={dateEmission}
                  onChange={(e) => handleEmissionChange(e.target.value)}
                  required
                />
              </div>
              {perimable && (
                <div className="field">
                  <label>Date de péremption *</label>
                  <input
                    type="date"
                    value={datePeremption}
                    onChange={(e) => handlePeremptionChange(e.target.value)}
                    required
                  />
                </div>
              )}
            </div>
            {perimable && duree && (
              <p className="hint">
                Validité habituelle : {dureeLisible(duree)}. La péremption se calcule toute seule
                depuis l'émission — corrige-la si le document dit autre chose.
              </p>
            )}
            {!perimable && (
              <p className="hint">Ce document n'expire pas : aucune date de péremption à saisir.</p>
            )}
          </div>

          {error && <div className="error">{error}</div>}
        </div>

        <footer className="modal-footer">
          <button type="button" className="btn btn-ghost" onClick={onClose}>Annuler</button>
          <button type="submit" className="btn" disabled={uploading}>
            {uploading ? 'Envoi…' : 'Enregistrer'}
          </button>
        </footer>
      </form>
    </div>
  )
}

// =====================================================================
// Drivers
// =====================================================================

const EMPTY_FORM = {
  prenom: '',
  nom: '',
  email: '',
  telephone: '',
  date_entree: '',
  external_id_depantime: '',
  profil: '',
}

function DriverFormModal({ driver, docTypes, profils, onClose, onSaved }) {
  const isEdit = Boolean(driver)
  const [form, setForm] = useState(() => {
    if (!driver) return { ...EMPTY_FORM }
    return {
      prenom: driver.prenom || '',
      nom: driver.nom || '',
      email: driver.email || '',
      telephone: driver.telephone || '',
      date_entree: driver.date_entree || '',
      external_id_depantime: driver.external_id_depantime || '',
      profil: driver.profil || '',
    }
  })
  const [applicableIds, setApplicableIds] = useState(
    () => new Set(driver?.required_document_type_ids || [])
  )
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  function update(field, value) {
    setForm((f) => ({ ...f, [field]: value }))
  }

  function toggleApplicable(id) {
    setApplicableIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function handleProfilChange(value) {
    update('profil', value)
    const profil = profils.find((p) => p.value === value)
    if (!profil) return
    const codes = new Set(profil.document_codes)
    setApplicableIds(new Set(docTypes.filter((dt) => codes.has(dt.code)).map((dt) => dt.id)))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setSaving(true)
    try {
      const payload = {
        prenom: form.prenom,
        nom: form.nom,
        email: form.email || null,
        telephone: form.telephone || null,
        date_entree: form.date_entree || null,
        external_id_depantime: form.external_id_depantime || null,
        profil: form.profil || null,
      }
      let saved
      if (isEdit) {
        saved = await api.drivers.update(driver.id, payload)
      } else {
        saved = await api.drivers.create(payload)
      }
      await api.drivers.syncRequirements(saved.id, Array.from(applicableIds))
      onSaved()
    } catch (err) {
      setError(err.detail || 'Erreur lors de la sauvegarde')
      setSaving(false)
    }
  }

  const groupedDocTypes = CATEGORIE_ORDER
    .map((cat) => ({ cat, items: docTypes.filter((dt) => (dt.categorie || CATEGORIE_DEFAUT) === cat) }))
    .filter((g) => g.items.length > 0)

  return (
    <div className="modal-overlay" onClick={onClose}>
      <form className="modal-card" onClick={(e) => e.stopPropagation()} onSubmit={handleSubmit}>
        <header className="modal-header">
          <h2>{isEdit ? 'Editer le depanneur' : 'Nouveau depanneur'}</h2>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Fermer">×</button>
        </header>

        <div className="modal-body">
          <div className="grid-2">
            <div className="field">
              <label>Prenom *</label>
              <input value={form.prenom} onChange={(e) => update('prenom', e.target.value)} required />
            </div>
            <div className="field">
              <label>Nom *</label>
              <input value={form.nom} onChange={(e) => update('nom', e.target.value)} required />
            </div>
            <div className="field">
              <label>Email</label>
              <input type="email" value={form.email} onChange={(e) => update('email', e.target.value)} />
            </div>
            <div className="field">
              <label>Telephone</label>
              <input value={form.telephone} onChange={(e) => update('telephone', e.target.value)} />
            </div>
            <div className="field">
              <label>Date d'entree</label>
              <input
                type="date"
                value={form.date_entree}
                onChange={(e) => update('date_entree', e.target.value)}
              />
            </div>
            <div className="field">
              <label>ID DepanTime (optionnel)</label>
              <input
                value={form.external_id_depantime}
                onChange={(e) => update('external_id_depantime', e.target.value)}
              />
            </div>
          </div>

          <div className="section">
            <h3>Profil &amp; documents applicables</h3>
            <div className="field">
              <label>Profil de permis</label>
              <select value={form.profil} onChange={(e) => handleProfilChange(e.target.value)}>
                <option value="">— Non defini —</option>
                {profils.map((p) => (
                  <option key={p.value} value={p.value}>{p.label}</option>
                ))}
              </select>
            </div>
            <p className="hint">
              Choisir un profil pre-coche les documents attendus pour ce type de permis.
              Tu peux ensuite ajuster manuellement — les non-coches s'affichent en gris
              dans le tableau de bord.
            </p>
            {groupedDocTypes.map(({ cat, items }) => (
              <div key={cat} className="check-group">
                <h4>{CATEGORIE_LABEL[cat] || cat}</h4>
                <div className="checks">
                  {items.map((dt) => (
                    <label key={dt.id} className="check">
                      <input
                        type="checkbox"
                        checked={applicableIds.has(dt.id)}
                        onChange={() => toggleApplicable(dt.id)}
                      />
                      <span>{dt.libelle}</span>
                    </label>
                  ))}
                </div>
              </div>
            ))}
          </div>

          {error && <div className="error">{error}</div>}
        </div>

        <footer className="modal-footer">
          <button type="button" className="btn btn-ghost" onClick={onClose}>Annuler</button>
          <button type="submit" className="btn" disabled={saving}>
            {saving ? 'Enregistrement…' : isEdit ? 'Enregistrer' : 'Creer'}
          </button>
        </footer>
      </form>
    </div>
  )
}

function DriversView({ docTypes, profils, syncStatut, onApresModification }) {
  const [drivers, setDrivers] = useState(null)
  const [error, setError] = useState('')
  const [includeArchived, setIncludeArchived] = useState(false)
  const [editing, setEditing] = useState(null) // null | 'new' | driver object

  function reload() {
    setDrivers(null)
    api.drivers
      .list({ includeArchived })
      .then(setDrivers)
      .catch((e) => setError(e.detail || String(e)))
  }

  useEffect(reload, [includeArchived])

  async function handleArchive(driver) {
    if (!confirm(`Archiver ${nomComplet(driver)} ?`)) return
    try {
      await api.drivers.archive(driver.id)
      reload()
      onApresModification?.()
    } catch (err) {
      alert(err.detail || 'Erreur lors de l\'archivage')
    }
  }

  const docTypeById = Object.fromEntries(docTypes.map((dt) => [dt.id, dt]))
  const synchronise = syncStatut?.active

  return (
    <>
      <div className="entete-page">
        <div>
          <h2>Équipe & applicabilité</h2>
          <p className="muted">
            Le profil de permis et les documents applicables à chacun se règlent ici.
          </p>
        </div>
      </div>

      {synchronise && (
        <div className="bandeau-info">
          La liste est alimentée par <strong>DepanTime</strong> : un dépanneur ajouté ou archivé
          là-bas l'est aussi ici. Une fiche créée à la main reste possible, mais elle ne sera pas
          suivie par la synchronisation.
        </div>
      )}

      <div className="toolbar">
        <button className="btn" onClick={() => setEditing('new')}>+ Nouveau dépanneur</button>
        <label className="check inline">
          <input
            type="checkbox"
            checked={includeArchived}
            onChange={(e) => setIncludeArchived(e.target.checked)}
          />
          <span>Voir les archives</span>
        </label>
      </div>

      {error && <div className="error">{error}</div>}
      {!drivers && !error && <div className="empty">Chargement…</div>}

      {drivers && drivers.length === 0 && (
        <div className="empty">
          Aucun dépanneur.{' '}
          {synchronise
            ? 'Lance la synchronisation depuis l\'onglet Dépanneurs.'
            : 'Clique sur « + Nouveau » pour commencer.'}
        </div>
      )}

      {drivers && drivers.length > 0 && (
        <div className="matrix-wrap">
          <table className="matrix drivers-table">
            <thead>
              <tr>
                <th>Depanneur</th>
                <th>Email</th>
                <th>Telephone</th>
                <th>Entree</th>
                <th>Documents applicables</th>
                <th>Statut</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {drivers.map((d) => (
                <tr key={d.id} className={d.statut === 'archived' ? 'is-archived' : ''}>
                  <td>
                    <strong>{d.nom}</strong> {d.prenom || ''}
                  </td>
                  <td>{d.email || '—'}</td>
                  <td>{d.telephone || '—'}</td>
                  <td>{formatDateFr(d.date_entree) || '—'}</td>
                  <td>
                    {d.required_document_type_ids.length === 0 ? (
                      <span className="muted">aucun</span>
                    ) : (
                      <div className="badges">
                        {d.required_document_type_ids
                          .map((id) => docTypeById[id])
                          .filter(Boolean)
                          .sort((a, b) => a.display_order - b.display_order)
                          .map((dt) => (
                            <span key={dt.id} className="badge">{dt.code}</span>
                          ))}
                      </div>
                    )}
                  </td>
                  <td>
                    {d.statut === 'archived' ? (
                      <span className="tag tag-archived">Archive</span>
                    ) : (
                      <span className="tag tag-active">Actif</span>
                    )}
                  </td>
                  <td className="actions">
                    <button className="btn btn-ghost btn-sm" onClick={() => setEditing(d)}>
                      Éditer
                    </button>
                    {d.statut !== 'archived' && (
                      <button className="btn btn-ghost btn-sm danger" onClick={() => handleArchive(d)}>
                        Archiver
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {editing && (
        <DriverFormModal
          driver={editing === 'new' ? null : editing}
          docTypes={docTypes}
          profils={profils}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null)
            reload()
          }}
        />
      )}
    </>
  )
}

// =====================================================================
// Layout
// =====================================================================

function NavBar({ view, onChangeView, me, onLogout }) {
  return (
    <header className="app-header">
      <div className="brand">
        <img src="/logo.png" className="brand-logo" alt="1MDP" />
        <h1>Habilitations</h1>
        <nav className="tabs">
          <button
            className={`tab ${view === 'depanneurs' ? 'active' : ''}`}
            onClick={() => onChangeView('depanneurs')}
          >
            Dépanneurs
          </button>
          <button
            className={`tab ${view === 'equipe' ? 'active' : ''}`}
            onClick={() => onChangeView('equipe')}
          >
            Équipe & applicabilité
          </button>
        </nav>
      </div>
      <div>
        <span className="who">{me?.email}</span>
        <button className="btn btn-ghost" onClick={onLogout}>Deconnexion</button>
      </div>
    </header>
  )
}

// =====================================================================
// Public upload (sans authentification)
// =====================================================================

function PublicUploadView({ token }) {
  const [info, setInfo] = useState(null)
  const [loadError, setLoadError] = useState('')
  const [file, setFile] = useState(null)
  const [dateEmission, setDateEmission] = useState('')
  const [datePeremption, setDatePeremption] = useState('')
  const [peremptionTouched, setPeremptionTouched] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState('')
  const [submitted, setSubmitted] = useState(false)

  useEffect(() => {
    api.publicRequests
      .get(token)
      .then(setInfo)
      .catch((e) => setLoadError(e.detail || 'Lien invalide'))
  }, [token])

  function handleEmissionChange(value) {
    setDateEmission(value)
    if (!peremptionTouched && value && info?.duree_validite_jours_default) {
      const d = new Date(value)
      d.setDate(d.getDate() + info.duree_validite_jours_default)
      setDatePeremption(d.toISOString().slice(0, 10))
    }
  }

  function handlePeremptionChange(value) {
    setPeremptionTouched(true)
    setDatePeremption(value)
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setSubmitError('')
    if (!file) {
      setSubmitError('Selectionne un fichier PDF')
      return
    }
    setSubmitting(true)
    try {
      await api.publicRequests.upload(token, { dateEmission, datePeremption, file })
      setSubmitted(true)
    } catch (err) {
      setSubmitError(err.detail || 'Erreur lors de l\'envoi')
      setSubmitting(false)
    }
  }

  if (loadError) {
    return (
      <div className="public-shell">
        <div className="public-card">
          <h1>Lien invalide</h1>
          <p>{loadError}</p>
          <p className="hint">Demande un nouveau lien a ton responsable.</p>
        </div>
      </div>
    )
  }

  if (!info) {
    return <div className="public-shell"><div className="public-card">Chargement…</div></div>
  }

  if (submitted) {
    return (
      <div className="public-shell">
        <div className="public-card">
          <h1>Document envoye ✓</h1>
          <p>Merci {info.driver_prenom}. Ton {info.document_type_libelle} a bien ete recu.</p>
          <p className="hint">Il sera valide par l'administration sous peu. Tu peux fermer cet onglet.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="public-shell">
      <form className="public-card" onSubmit={handleSubmit}>
        <h1>Envoi de document — 1MDP</h1>
        <p className="public-context">
          <strong>{info.driver_prenom} {info.driver_nom}</strong>
          <br />
          Document attendu : <strong>{info.document_type_libelle}</strong>
        </p>

        <div className="field">
          <label>Fichier (PDF, max 10 MB) *</label>
          <input
            type="file"
            accept="application/pdf"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            required
          />
        </div>

        <div className="grid-2">
          <div className="field">
            <label>Date d'emission *</label>
            <input
              type="date"
              value={dateEmission}
              onChange={(e) => handleEmissionChange(e.target.value)}
              required
            />
          </div>
          {info.est_perimable !== false && (
            <div className="field">
              <label>Date de peremption *</label>
              <input
                type="date"
                value={datePeremption}
                onChange={(e) => handlePeremptionChange(e.target.value)}
                required
              />
            </div>
          )}
        </div>

        {submitError && <div className="error">{submitError}</div>}

        <button type="submit" className="btn" disabled={submitting} style={{ width: '100%', marginTop: 8 }}>
          {submitting ? 'Envoi en cours…' : 'Envoyer le document'}
        </button>

        <p className="hint" style={{ marginTop: 16, textAlign: 'center' }}>
          Lien valide jusqu'au {formatDateFr(info.expires_at.slice(0, 10))}
        </p>
      </form>
    </div>
  )
}

// =====================================================================
// App
// =====================================================================

function getPublicToken() {
  const m = window.location.pathname.match(/^\/upload\/([\w-]+)\/?$/)
  return m ? m[1] : null
}

function AdminApp() {
  const [authed, setAuthed] = useState(Boolean(getToken()))
  const [me, setMe] = useState(null)
  const [view, setView] = useState('depanneurs')
  const [ficheId, setFicheId] = useState(null)
  const [docTypes, setDocTypes] = useState([])
  const [profils, setProfils] = useState([])
  const [data, setData] = useState(null)
  const [erreur, setErreur] = useState('')
  const [syncStatut, setSyncStatut] = useState(null)
  const [syncEnCours, setSyncEnCours] = useState(false)
  const [syncMessage, setSyncMessage] = useState('')
  const [editDriver, setEditDriver] = useState(null)

  // Le tableau de bord porte a la fois les types, les depanneurs et l'etat de
  // chaque document : la liste et la fiche s'en servent toutes les deux, on le
  // charge donc ici plutot qu'une fois par vue.
  const recharger = useCallback(() => {
    api.dashboard().then((d) => { setData(d); setErreur('') })
      .catch((e) => setErreur(e.detail || String(e)))
    api.docTypes().then(setDocTypes).catch(() => {})
  }, [])

  useEffect(() => {
    if (!authed) return
    api.me().then(setMe).catch(() => {})
    api.profils().then(setProfils).catch(() => {})
    api.sync.status().then(setSyncStatut).catch(() => setSyncStatut({ active: false }))
    recharger()
  }, [authed, recharger])

  async function lancerSync() {
    setSyncEnCours(true)
    setSyncMessage('')
    try {
      const r = await api.sync.run()
      const parts = []
      if (r.crees) parts.push(`${r.crees} ajouté(s)`)
      if (r.archives) parts.push(`${r.archives} archivé(s)`)
      if (r.reactives) parts.push(`${r.reactives} réactivé(s)`)
      setSyncMessage(
        parts.length
          ? `Synchronisation : ${parts.join(', ')} (${r.mis_a_jour} inchangé(s)).`
          : `Déjà à jour — ${r.mis_a_jour} dépanneur(s) vérifié(s).`
      )
      recharger()
    } catch (err) {
      setSyncMessage(err.detail || 'Erreur de synchronisation')
    } finally {
      setSyncEnCours(false)
    }
  }

  function handleLogout() {
    clearToken()
    setMe(null)
    setAuthed(false)
  }

  if (!authed) {
    return <LoginView onLogin={() => setAuthed(true)} />
  }

  return (
    <>
      <NavBar
        view={view}
        onChangeView={(v) => { setView(v); setFicheId(null) }}
        me={me}
        onLogout={handleLogout}
      />
      <main className="dashboard">
        {erreur && <div className="error">{erreur}</div>}
        {syncMessage && <div className="bandeau-info">{syncMessage}</div>}

        {view === 'depanneurs' && !ficheId && (
          <DriversListView
            docTypes={docTypes}
            data={data}
            rafraichir={recharger}
            onOuvrirFiche={setFicheId}
            onSync={lancerSync}
            syncStatut={syncStatut}
            syncEnCours={syncEnCours}
          />
        )}
        {view === 'depanneurs' && ficheId && (
          <DriverSheetView
            driverId={ficheId}
            docTypes={docTypes}
            data={data}
            rafraichir={recharger}
            onRetour={() => setFicheId(null)}
            onModifier={setEditDriver}
          />
        )}
        {view === 'equipe' && (
          <DriversView
            docTypes={docTypes}
            profils={profils}
            syncStatut={syncStatut}
            onApresModification={recharger}
          />
        )}
      </main>

      {editDriver && (
        <DriverFormModal
          driver={editDriver}
          docTypes={docTypes}
          profils={profils}
          onClose={() => setEditDriver(null)}
          onSaved={() => { setEditDriver(null); recharger() }}
        />
      )}
    </>
  )
}

export default function App() {
  const publicToken = getPublicToken()
  if (publicToken) {
    return <PublicUploadView token={publicToken} />
  }
  return <AdminApp />
}
