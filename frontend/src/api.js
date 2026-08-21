const TOKEN_KEY = 'habilitation-token'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
}

export class ApiError extends Error {
  constructor(status, detail) {
    super(detail || `HTTP ${status}`)
    this.status = status
    this.detail = detail
  }
}

async function request(path, { method = 'GET', body, auth = true } = {}) {
  const headers = { 'Content-Type': 'application/json' }
  if (auth) {
    const token = getToken()
    if (token) headers.Authorization = `Bearer ${token}`
  }
  const res = await fetch(`/api${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (res.status === 401 && auth) {
    clearToken()
    window.location.reload()
    throw new ApiError(401, 'Session expiree')
  }
  const text = await res.text()
  let data = null
  try {
    data = text ? JSON.parse(text) : null
  } catch {
    // Reponse non-JSON (page d'erreur nginx, timeout proxy...) : texte brut conserve.
  }
  if (!res.ok) {
    throw new ApiError(res.status, data?.detail || text?.trim()?.slice(0, 300) || res.statusText)
  }
  return data
}

async function uploadFormData(path, formData, { auth = true } = {}) {
  const token = auth ? getToken() : null
  const res = await fetch(`/api${path}`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: formData,
  })
  if (res.status === 401 && auth) {
    clearToken()
    window.location.reload()
    throw new ApiError(401, 'Session expiree')
  }
  const text = await res.text()
  let data = null
  try {
    data = text ? JSON.parse(text) : null
  } catch {
    /* reponse non-JSON */
  }
  if (!res.ok) {
    throw new ApiError(res.status, data?.detail || text?.trim()?.slice(0, 300) || res.statusText)
  }
  return data
}

async function fetchDownload(path, { fallbackName = 'document.pdf' } = {}) {
  const token = getToken()
  const res = await fetch(`/api${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (res.status === 401) {
    clearToken()
    window.location.reload()
    throw new ApiError(401, 'Session expiree')
  }
  if (!res.ok) {
    const text = await res.text()
    let detail = res.statusText
    try { detail = JSON.parse(text)?.detail || detail } catch { /* noop */ }
    throw new ApiError(res.status, detail)
  }
  const blob = await res.blob()
  // Nom de fichier propre fourni par le backend (Content-Disposition).
  const cd = res.headers.get('Content-Disposition') || ''
  const match = cd.match(/filename="?([^"]+)"?/i)
  return { blob, filename: match ? match[1] : fallbackName }
}

function triggerBlobDownload(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 60_000)
}

export const api = {
  login: (email, password) =>
    request('/auth/login', { method: 'POST', body: { email, password }, auth: false }),
  me: () => request('/auth/me'),
  dashboard: () => request('/dashboard'),
  docTypes: () => request('/document-types'),
  // Les depanneurs sont en lecture seule : la liste, l'identite, l'equipe et le
  // type de vehicule viennent de DepanTime et de Flotte, et ce qu'on exige de
  // chacun en decoule. Il n'y a plus ni synchro manuelle (le cron s'en charge)
  // ni reglage d'applicabilite : les routes correspondantes ont ete retirees.
  drivers: {
    list: ({ includeArchived = false } = {}) =>
      request(`/drivers?include_archived=${includeArchived}`),
    get: (id) => request(`/drivers/${id}`),
  },
  documents: {
    get: (versionId) => request(`/documents/${versionId}`),
    upload: ({ driverId, documentTypeId, dateEmission, datePeremption, file }) => {
      const fd = new FormData()
      fd.append('driver_id', driverId)
      fd.append('document_type_id', documentTypeId)
      fd.append('date_emission', dateEmission)
      if (datePeremption) fd.append('date_peremption', datePeremption)
      fd.append('file', file)
      return uploadFormData('/documents/upload', fd)
    },
    download: async (versionId) => {
      const { blob, filename } = await fetchDownload(`/documents/${versionId}/download`)
      triggerBlobDownload(blob, filename)
    },
    // L'API exige le JWT : un <iframe src> ou un window.open sur l'URL ne peut
    // pas fonctionner. On recupere le blob et on visualise l'URL objet.
    openBlob: async (versionId) => {
      const { blob, filename } = await fetchDownload(`/documents/${versionId}/download`)
      return { url: URL.createObjectURL(blob), filename, type: blob.type, size: blob.size }
    },
    exportZip: async ({ driverId } = {}) => {
      const query = driverId ? `?driver_id=${encodeURIComponent(driverId)}` : ''
      const { blob, filename } = await fetchDownload(`/documents/export${query}`, {
        fallbackName: 'habilitations.zip',
      })
      triggerBlobDownload(blob, filename)
      return blob.size
    },
    validate: (versionId) =>
      request(`/documents/${versionId}/validate`, { method: 'POST' }),
    reject: (versionId, reason) =>
      request(`/documents/${versionId}/reject`, { method: 'POST', body: { reason } }),
  },
  // Les demandes par magic link ne sont plus proposees dans l'interface (retire
  // le 2026-08-19). Les routes backend restent en place : la relance passera
  // par un mail automatique des documents manquants, a cadrer.
  docusign: {
    getEnvelope: (driverId, documentTypeId) =>
      request(`/docusign/envelope?driver_id=${driverId}&document_type_id=${documentTypeId}`),
    send: ({ driverId, documentTypeId, mois, annee }) =>
      request('/docusign/send', {
        method: 'POST',
        body: {
          driver_id: driverId,
          document_type_id: documentTypeId,
          mois,
          annee,
        },
      }),
    refresh: (envelopeId) =>
      request(`/docusign/envelopes/${envelopeId}/refresh`, { method: 'POST' }),
  },
  publicRequests: {
    get: (token) => request(`/public/document-requests/${token}`, { auth: false }),
    upload: (token, { dateEmission, datePeremption, file }) => {
      const fd = new FormData()
      fd.append('date_emission', dateEmission)
      if (datePeremption) fd.append('date_peremption', datePeremption)
      fd.append('file', file)
      return uploadFormData(`/public/document-requests/${token}/upload`, fd, { auth: false })
    },
  },
}
