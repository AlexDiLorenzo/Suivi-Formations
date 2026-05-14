import { useEffect, useState } from 'react'
import { api, clearToken, getToken, setToken } from './api.js'

const STATUS_LABEL = {
  green: 'Vert',
  orange: 'Orange',
  red: 'Rouge',
  grey: 'Non applicable',
}

const REASON_LABEL = {
  expired: 'Perime',
  never_received: 'Jamais transmis',
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

function MatrixCell({ cell }) {
  const sub = cellSubLabel(cell)
  return (
    <td className={`cell ${cell.status}`}>
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

function DashboardView({ me, onLogout }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.dashboard().then(setData).catch((e) => setError(e.detail || String(e)))
  }, [])

  return (
    <>
      <header className="app-header">
        <h1>Tableau de bord — Habilitations</h1>
        <div>
          <span className="who">{me?.email}</span>
          <button className="btn btn-ghost" onClick={onLogout}>
            Deconnexion
          </button>
        </div>
      </header>
      <div className="dashboard">
        {error && <div className="error">{error}</div>}
        {!data && !error && <div className="empty">Chargement…</div>}
        {data && (
          <>
            <SummaryBar summary={data.summary} />
            {data.drivers.length === 0 ? (
              <div className="empty">
                Aucun depanneur actif. Ajoute-en via <code>POST /api/drivers</code>
                {' '}ou lance <code>scripts.seed_demo</code> en dev.
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
                          <MatrixCell key={c.document_type_id} cell={c} />
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>
    </>
  )
}

export default function App() {
  const [authed, setAuthed] = useState(Boolean(getToken()))
  const [me, setMe] = useState(null)

  useEffect(() => {
    if (!authed) return
    api.me().then(setMe).catch(() => {})
  }, [authed])

  function handleLogout() {
    clearToken()
    setMe(null)
    setAuthed(false)
  }

  if (!authed) {
    return <LoginView onLogin={() => setAuthed(true)} />
  }
  return <DashboardView me={me} onLogout={handleLogout} />
}
