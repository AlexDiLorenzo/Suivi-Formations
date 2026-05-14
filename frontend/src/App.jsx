import { useEffect, useState } from 'react'
import { api, clearToken, getToken, setToken } from './api.js'

const STATUS_LABEL = {
  green: 'Vert',
  orange: 'Orange',
  red: 'Rouge',
  grey: 'Non applicable',
}

function formatDateFr(iso) {
  if (!iso) return ''
  const [y, m, d] = iso.split('-')
  return `${d}/${m}/${y}`
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
  return ''
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

function SummaryBar({ summary }) {
  const order = ['green', 'orange', 'red', 'grey']
  return (
    <div className="summary">
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
  const sub = cellSubLabel(cell)
  const clickable = cell.status !== 'grey'
  return (
    <td
      className={`cell ${cell.status} ${clickable ? 'clickable' : ''}`}
      onClick={clickable ? onClick : undefined}
      title={clickable ? 'Cliquer pour uploader / consulter' : 'Non applicable'}
    >
      {cell.has_pending_version && (
        <span className="pending-dot" title="Une version est en attente de validation">●</span>
      )}
      {cell.status === 'grey' ? (
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

  function reload() {
    api.dashboard().then(setData).catch((e) => setError(e.detail || String(e)))
  }

  useEffect(reload, [])

  if (error) return <div className="error" style={{ padding: 24 }}>{error}</div>
  if (!data) return <div className="empty">Chargement…</div>

  const docTypeById = Object.fromEntries(docTypes.map((dt) => [dt.id, dt]))

  function openUpload(driver, cell) {
    setUploadCtx({
      driver,
      docType: docTypeById[cell.document_type_id] || data.doc_types.find((d) => d.id === cell.document_type_id),
      currentVersionId: cell.current_version_id,
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
        <div className="matrix-wrap">
          <table className="matrix">
            <thead>
              <tr>
                <th className="driver-col">Depanneur</th>
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
          onClose={() => setUploadCtx(null)}
          onUploaded={() => {
            setUploadCtx(null)
            reload()
          }}
        />
      )}
    </>
  )
}

function UploadModal({ driver, docType, currentVersionId, onClose, onUploaded }) {
  const [file, setFile] = useState(null)
  const [dateEmission, setDateEmission] = useState('')
  const [datePeremption, setDatePeremption] = useState('')
  const [peremptionTouched, setPeremptionTouched] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const [requesting, setRequesting] = useState(false)
  const [magicLink, setMagicLink] = useState(null)
  const [linkCopied, setLinkCopied] = useState(false)
  const [error, setError] = useState('')

  async function handleCreateRequest() {
    setError('')
    setRequesting(true)
    try {
      const created = await api.documentRequests.create({
        driverId: driver.id,
        documentTypeId: docType.id,
      })
      setMagicLink(created.magic_link)
    } catch (err) {
      setError(err.detail || 'Erreur lors de la creation de la demande')
    } finally {
      setRequesting(false)
    }
  }

  async function handleCopyLink() {
    if (!magicLink) return
    try {
      await navigator.clipboard.writeText(magicLink)
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
      await api.documents.openInNewTab(currentVersionId)
    } catch (err) {
      setError(err.detail || 'Erreur lors du telechargement')
    } finally {
      setDownloading(false)
    }
  }

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

          <div className="section">
            <h3>Demander au depanneur</h3>
            <p className="hint">
              Genere un lien a usage unique (valide 7 jours) que tu peux envoyer
              au depanneur par WhatsApp / SMS / email pour qu'il uploade lui-meme
              son document. La version sera creee en attente de ta validation.
            </p>
            {!magicLink ? (
              <button
                type="button"
                className="btn btn-ghost"
                onClick={handleCreateRequest}
                disabled={requesting}
              >
                {requesting ? 'Generation…' : 'Generer un lien magique'}
              </button>
            ) : (
              <div className="magic-link">
                <input type="text" readOnly value={magicLink} onFocus={(e) => e.target.select()} />
                <button type="button" className="btn btn-sm" onClick={handleCopyLink}>
                  {linkCopied ? 'Copie ✓' : 'Copier'}
                </button>
              </div>
            )}
          </div>

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
              <div className="field">
                <label>Date de peremption *</label>
                <input
                  type="date"
                  value={datePeremption}
                  onChange={(e) => handlePeremptionChange(e.target.value)}
                  required
                />
              </div>
            </div>
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
}

function DriverFormModal({ driver, docTypes, onClose, onSaved }) {
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
            <h3>Documents applicables</h3>
            <p className="hint">
              Coche les types de documents que ce depanneur doit detenir. Les non-coches
              s'afficheront en gris dans le tableau de bord.
            </p>
            <div className="checks">
              {docTypes.map((dt) => (
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

function DriversView({ docTypes }) {
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
          <div className="field">
            <label>Date de peremption *</label>
            <input
              type="date"
              value={datePeremption}
              onChange={(e) => handlePeremptionChange(e.target.value)}
              required
            />
          </div>
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

  useEffect(() => {
    if (!authed) return
    api.me().then(setMe).catch(() => {})
    api.docTypes().then(setDocTypes).catch(() => {})
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
        {view === 'drivers' && <DriversView docTypes={docTypes} />}
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
