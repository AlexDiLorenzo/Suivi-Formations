import { useEffect, useRef, useState } from 'react'
import { api, clearToken, getToken, setToken } from './api.js'

const STATUS_LABEL = {
  green: 'Vert',
  orange: 'Orange',
  red: 'Rouge',
  grey: 'Non applicable',
}

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

const CATEGORIE_ORDER = [
  'permis_conduite',
  'caces_autorisations',
  'formations_internes',
  'diplomes',
  'administratif',
]

const CATEGORIE_LABEL = {
  permis_conduite: 'Permis & conduite',
  caces_autorisations: 'CACES & autorisations',
  formations_internes: 'Formations internes',
  diplomes: 'Diplomes',
  administratif: 'Administratif RH',
}

function formatDateFr(iso) {
  if (!iso) return ''
  const [y, m, d] = iso.split('-')
  return `${d}/${m}/${y}`
}

function daysSinceIso(iso) {
  if (!iso) return null
  const then = new Date(iso)
  const now = new Date()
  return Math.max(0, Math.floor((now.getTime() - then.getTime()) / 86400000))
}

function cellSubLabel(cell) {
  if (cell.status === 'grey') return ''
  if (cell.status === 'red') {
    if (cell.reason === 'never_received') return 'Jamais transmis'
    if (cell.reason === 'expired') {
      const days = -cell.days_until_expiry
      return `Perime depuis ${days}j`
    }
  }
  if (cell.days_until_expiry != null) {
    return `J-${cell.days_until_expiry}`
  }
  if (cell.status === 'green') return 'Valide'
  return ''
}

function scoreClass(score) {
  if (score == null) return 'grey'
  if (score >= 90) return 'green'
  if (score >= 60) return 'orange'
  return 'red'
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

  return (
    <div className="login-shell">
      <form className="login-card" onSubmit={handleSubmit}>
        <h1>Habilitations</h1>
        <p className="subtitle">Espace administrateur — 1MDP</p>
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
        {error && <div className="error">{error}</div>}
        <button className="btn" type="submit" disabled={loading}>
          {loading ? 'Connexion…' : 'Se connecter'}
        </button>
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

function SummaryBar({ summary }) {
  const order = ['green', 'orange', 'red', 'grey']
  return (
    <div className="summary">
      {summary.score_global != null && (
        <span className={`summary-pill score-pill ${scoreClass(summary.score_global)}`}>
          Conformité globale
          <span className="count">{summary.score_global}%</span>
        </span>
      )}
      {order.map((s) => (
        <span className="summary-pill" key={s}>
          <span className={`dot ${s}`} />
          {STATUS_LABEL[s]}
          <span className="count">{summary.by_status[s] ?? 0}</span>
        </span>
      ))}
    </div>
  )
}

function MatrixCell({ cell, onClick }) {
  const clickable = cell.status !== 'grey'
  const pending = cell.has_pending_version
  const requested = !pending && cell.open_request_sent_at != null
  const requestedDays = requested ? daysSinceIso(cell.open_request_sent_at) : null
  const signing = !pending && !requested && DS_IN_PROGRESS.includes(cell.signature_status)

  let visualStatus = cell.status
  let sub = cellSubLabel(cell)
  let tooltip = clickable ? 'Cliquer pour uploader / consulter' : 'Non applicable'

  if (pending) {
    visualStatus = 'pending'
    sub = 'A valider'
    tooltip = 'Version en attente de validation — clique pour valider'
  } else if (requested) {
    visualStatus = 'requested'
    sub = requestedDays === 0 ? 'Demande aujourd\'hui' : `Demande il y a ${requestedDays}j`
    tooltip = `Demande envoyee il y a ${requestedDays}j, en attente de reponse — clique pour relancer ou uploader`
  } else if (signing) {
    visualStatus = 'requested'
    sub = 'Signature en cours'
    tooltip = 'Attestation envoyee pour signature DocuSign — clique pour suivre le statut'
  }

  return (
    <td
      className={`cell ${visualStatus} ${clickable ? 'clickable' : ''}`}
      onClick={clickable ? onClick : undefined}
      title={tooltip}
    >
      {cell.status === 'grey' && !pending && !requested ? (
        <span>—</span>
      ) : (
        <>
          <span className="date">{cell.date_peremption ? formatDateFr(cell.date_peremption) : '—'}</span>
          {sub && <span className="sub">{sub}</span>}
        </>
      )}
    </td>
  )
}

function DashboardView({ docTypes }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [uploadCtx, setUploadCtx] = useState(null)
  const matrixRef = useRef(null)

  function reload() {
    api.dashboard().then(setData).catch((e) => setError(e.detail || String(e)))
  }

  useEffect(reload, [])

  // Permet de defiler la matrice horizontalement avec une simple molette
  // verticale (souris sans scroll lateral). Listener natif non-passif :
  // React enregistre onWheel en passif, preventDefault y serait ignore.
  useEffect(() => {
    const el = matrixRef.current
    if (!el) return undefined
    function onWheel(e) {
      if (el.scrollWidth <= el.clientWidth || e.deltaY === 0) return
      // Si la matrice peut defiler verticalement (beaucoup de lignes), on
      // laisse la molette faire son travail naturel : defiler vers le bas,
      // en-tete fige. La conversion horizontale ne sert que sans debordement vertical.
      if (el.scrollHeight > el.clientHeight) return
      const atStart = el.scrollLeft <= 0
      const atEnd = el.scrollLeft + el.clientWidth >= el.scrollWidth - 1
      // Au bord, on laisse la page defiler verticalement comme d'habitude.
      if ((e.deltaY < 0 && atStart) || (e.deltaY > 0 && atEnd)) return
      el.scrollLeft += e.deltaY * (e.deltaMode === 1 ? 16 : 1)
      e.preventDefault()
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [data])

  if (error) return <div className="error" style={{ padding: 24 }}>{error}</div>
  if (!data) return <div className="empty">Chargement…</div>

  const docTypeById = Object.fromEntries(docTypes.map((dt) => [dt.id, dt]))

  function openUpload(driver, cell) {
    setUploadCtx({
      driver,
      docType: docTypeById[cell.document_type_id] || data.doc_types.find((d) => d.id === cell.document_type_id),
      currentVersionId: cell.current_version_id,
      pendingVersionId: cell.pending_version_id,
    })
  }

  return (
    <>
      <SummaryBar summary={data.summary} />
      {data.drivers.length === 0 ? (
        <div className="empty">
          Aucun depanneur actif. Ajoute-en depuis l'onglet Depanneurs ou lance{' '}
          <code>scripts.seed_demo</code> en dev.
        </div>
      ) : (
        <div className="matrix-wrap" ref={matrixRef}>
          <table className="matrix">
            <thead>
              <tr>
                <th className="driver-col">Depanneur</th>
                <th className="score-col">Score</th>
                {data.doc_types.map((dt) => (
                  <th key={dt.id}>{dt.libelle}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.drivers.map((d) => (
                <tr key={d.id}>
                  <td className="driver-col">
                    <strong>{d.nom}</strong> {d.prenom}
                  </td>
                  <td className="score-col">
                    <ScoreBadge score={d.score} />
                  </td>
                  {d.cells.map((c) => (
                    <MatrixCell
                      key={c.document_type_id}
                      cell={c}
                      onClick={() => openUpload(d, c)}
                    />
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {uploadCtx && (
        <UploadModal
          driver={uploadCtx.driver}
          docType={uploadCtx.docType}
          currentVersionId={uploadCtx.currentVersionId}
          pendingVersionId={uploadCtx.pendingVersionId}
          onClose={() => {
            setUploadCtx(null)
            reload()
          }}
          onUploaded={() => {
            setUploadCtx(null)
            reload()
          }}
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

function UploadModal({ driver, docType, currentVersionId, pendingVersionId, onClose, onUploaded }) {
  const [file, setFile] = useState(null)
  const [dateEmission, setDateEmission] = useState('')
  const [datePeremption, setDatePeremption] = useState('')
  const [peremptionTouched, setPeremptionTouched] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const [requesting, setRequesting] = useState(false)
  const [requestResult, setRequestResult] = useState(null)
  const [linkCopied, setLinkCopied] = useState(false)
  const [error, setError] = useState('')
  const [pendingVersion, setPendingVersion] = useState(null)
  const [reviewing, setReviewing] = useState(false)
  const [downloadingPending, setDownloadingPending] = useState(false)

  useEffect(() => {
    if (!pendingVersionId) {
      setPendingVersion(null)
      return
    }
    api.documents.get(pendingVersionId).then(setPendingVersion).catch(() => {})
  }, [pendingVersionId])

  async function handleDownloadPending() {
    setDownloadingPending(true)
    try {
      await api.documents.download(pendingVersionId)
    } catch (err) {
      setError(err.detail || 'Erreur lors du telechargement')
    } finally {
      setDownloadingPending(false)
    }
  }

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
    const reason = prompt('Motif du rejet (sera communique au depanneur lors de la nouvelle demande) :')
    if (reason === null) return
    if (reason.trim().length < 3) {
      alert('Le motif doit contenir au moins 3 caracteres.')
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

  async function handleCreateRequest() {
    setError('')
    setRequesting(true)
    try {
      const created = await api.documentRequests.create({
        driverId: driver.id,
        documentTypeId: docType.id,
      })
      setRequestResult(created)
    } catch (err) {
      setError(err.detail || 'Erreur lors de la creation de la demande')
    } finally {
      setRequesting(false)
    }
  }

  async function handleCopyLink() {
    if (!requestResult?.magic_link) return
    try {
      await navigator.clipboard.writeText(requestResult.magic_link)
      setLinkCopied(true)
      setTimeout(() => setLinkCopied(false), 2000)
    } catch {
      /* clipboard refusee, l'utilisateur peut copier manuellement */
    }
  }

  function handleEmissionChange(value) {
    setDateEmission(value)
    if (!peremptionTouched && value && docType?.duree_validite_jours_default) {
      const d = new Date(value)
      d.setDate(d.getDate() + docType.duree_validite_jours_default)
      const iso = d.toISOString().slice(0, 10)
      setDatePeremption(iso)
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
      setError('Selectionne un fichier PDF')
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

  async function handleDownload() {
    if (!currentVersionId) return
    setDownloading(true)
    try {
      await api.documents.download(currentVersionId)
    } catch (err) {
      setError(err.detail || 'Erreur lors du telechargement')
    } finally {
      setDownloading(false)
    }
  }

  const perimable = docType?.est_perimable !== false

  return (
    <div className="modal-overlay" onClick={onClose}>
      <form className="modal-card" onClick={(e) => e.stopPropagation()} onSubmit={handleSubmit}>
        <header className="modal-header">
          <h2>Document — {docType?.libelle}</h2>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Fermer">×</button>
        </header>

        <div className="modal-body">
          <p className="hint">
            <strong>{driver.nom} {driver.prenom}</strong>
            {' · '}{docType?.code}
          </p>

          {pendingVersionId && (
            <div className="pending-block">
              <div className="pending-header">
                <span className="tag tag-pending">⏳ Version en attente de validation</span>
              </div>
              {pendingVersion ? (
                <ul className="pending-meta">
                  <li>
                    Uploade par <strong>{pendingVersion.uploaded_by === 'driver' ? 'le depanneur' : 'admin'}</strong>
                    {' '}le {formatDateFr(pendingVersion.uploaded_at.slice(0, 10))}
                  </li>
                  <li>
                    Emission : <strong>{formatDateFr(pendingVersion.date_emission)}</strong>
                    {' · '}
                    {pendingVersion.date_peremption ? (
                      <>Peremption : <strong>{formatDateFr(pendingVersion.date_peremption)}</strong></>
                    ) : (
                      <span className="hint">Non perimable</span>
                    )}
                  </li>
                  <li>Fichier : {pendingVersion.original_filename} ({Math.round(pendingVersion.file_size_bytes / 1024)} ko)</li>
                </ul>
              ) : (
                <p className="hint">Chargement des details…</p>
              )}
              <div className="pending-actions">
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  onClick={handleDownloadPending}
                  disabled={downloadingPending}
                >
                  {downloadingPending ? '…' : 'Telecharger'}
                </button>
                <button
                  type="button"
                  className="btn btn-sm"
                  onClick={handleValidate}
                  disabled={reviewing}
                >
                  Valider
                </button>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm danger"
                  onClick={handleReject}
                  disabled={reviewing}
                >
                  Rejeter
                </button>
              </div>
            </div>
          )}

          {currentVersionId && (
            <div className="info-block">
              <span>Une version est deja en base.</span>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={handleDownload}
                disabled={downloading}
              >
                {downloading ? '…' : 'Telecharger la version actuelle'}
              </button>
            </div>
          )}

          {docType?.mode_acquisition === 'docusign' ? (
            <DocusignSection driver={driver} docType={docType} />
          ) : (
          <div className="section">
            <h3>Demander au depanneur</h3>
            <p className="hint">
              Genere une demande a usage unique (valide 7 jours). Si le
              depanneur a un email enregistre, il recoit automatiquement
              le lien securise. Sinon le lien s'affiche ici, copiable pour
              envoi WhatsApp / SMS.
            </p>
            {!requestResult ? (
              <button
                type="button"
                className="btn btn-ghost"
                onClick={handleCreateRequest}
                disabled={requesting}
              >
                {requesting ? 'Envoi…' : 'Envoyer la demande'}
              </button>
            ) : (
              <>
                {requestResult.email_sent ? (
                  <div className="email-status success">
                    ✓ Email envoye a <strong>{requestResult.driver_email}</strong>
                  </div>
                ) : (
                  <div className="email-status warn">
                    {requestResult.email_error || 'Email non envoye'} — copie le lien ci-dessous :
                  </div>
                )}
                <div className="magic-link">
                  <input
                    type="text"
                    readOnly
                    value={requestResult.magic_link}
                    onFocus={(e) => e.target.select()}
                  />
                  <button type="button" className="btn btn-sm" onClick={handleCopyLink}>
                    {linkCopied ? 'Copie ✓' : 'Copier'}
                  </button>
                </div>
              </>
            )}
          </div>
          )}

          <div className="section">
            <h3>{currentVersionId ? 'Nouvelle version (admin)' : 'Premier upload (admin)'}</h3>
            <p className="hint">
              Si tu as deja le PDF, tu peux l'uploader directement. La version
              sera creee comme validee. L'ancienne reste archivee en base
              (jamais d'ecrasement).
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
              {perimable && (
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
            {!perimable && (
              <p className="hint">Ce document n'est pas perimable : aucune date de peremption a saisir.</p>
            )}
          </div>

          {error && <div className="error">{error}</div>}
        </div>

        <footer className="modal-footer">
          <button type="button" className="btn btn-ghost" onClick={onClose}>Annuler</button>
          <button type="submit" className="btn" disabled={uploading}>
            {uploading ? 'Envoi…' : 'Uploader'}
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
    .map((cat) => ({ cat, items: docTypes.filter((dt) => (dt.categorie || 'administratif') === cat) }))
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

function DriversView({ docTypes, profils }) {
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
    if (!confirm(`Archiver ${driver.prenom} ${driver.nom} ?`)) return
    try {
      await api.drivers.archive(driver.id)
      reload()
    } catch (err) {
      alert(err.detail || 'Erreur lors de l\'archivage')
    }
  }

  async function handleBulkRequest(driver) {
    const ok = confirm(
      `Envoyer une demande pour tous les documents manquants ou perimes de ${driver.prenom} ${driver.nom} ?\n\n` +
      `Si ${driver.prenom} a un email enregistre, un mail recap sera envoye automatiquement.`
    )
    if (!ok) return
    try {
      const r = await api.documentRequests.bulk(driver.id)
      if (r.count === 0) {
        alert(r.email_error || 'Aucun document a demander')
        return
      }
      const emailLine = r.email_sent
        ? `\n\nEmail envoye a ${r.driver_email}.`
        : `\n\n${r.email_error || 'Email non envoye.'} Liens disponibles dans le retour API.`
      alert(`${r.count} demande(s) creee(s).${emailLine}`)
    } catch (err) {
      alert(err.detail || 'Erreur lors de l\'envoi des demandes')
    }
  }

  const docTypeById = Object.fromEntries(docTypes.map((dt) => [dt.id, dt]))

  return (
    <>
      <div className="toolbar">
        <button className="btn" onClick={() => setEditing('new')}>+ Nouveau depanneur</button>
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
        <div className="empty">Aucun depanneur. Clique sur "+ Nouveau" pour commencer.</div>
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
                    <strong>{d.nom}</strong> {d.prenom}
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
                      Editer
                    </button>
                    {d.statut !== 'archived' && d.required_document_type_ids.length > 0 && (
                      <button
                        className="btn btn-ghost btn-sm"
                        onClick={() => handleBulkRequest(d)}
                        title="Envoyer une demande pour tous les docs manquants ou perimes"
                      >
                        Envoyer demandes
                      </button>
                    )}
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
            className={`tab ${view === 'dashboard' ? 'active' : ''}`}
            onClick={() => onChangeView('dashboard')}
          >
            Tableau de bord
          </button>
          <button
            className={`tab ${view === 'drivers' ? 'active' : ''}`}
            onClick={() => onChangeView('drivers')}
          >
            Depanneurs
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
  const [view, setView] = useState('dashboard')
  const [docTypes, setDocTypes] = useState([])
  const [profils, setProfils] = useState([])

  useEffect(() => {
    if (!authed) return
    api.me().then(setMe).catch(() => {})
    api.docTypes().then(setDocTypes).catch(() => {})
    api.profils().then(setProfils).catch(() => {})
  }, [authed])

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
      <NavBar view={view} onChangeView={setView} me={me} onLogout={handleLogout} />
      <main className="dashboard">
        {view === 'dashboard' && <DashboardView docTypes={docTypes} />}
        {view === 'drivers' && <DriversView docTypes={docTypes} profils={profils} />}
      </main>
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
