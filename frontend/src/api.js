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

async function fetchDownload(path) {
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
  return { blob, filename: match ? match[1] : 'document.pdf' }
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
  profils: () => request('/profils'),
  drivers: {
    list: ({ includeArchived = false } = {}) =>
      request(`/drivers?include_archived=${includeArchived}`),
    create: (payload) => request('/drivers', { method: 'POST', body: payload }),
    update: (id, payload) => request(`/drivers/${id}`, { method: 'PATCH', body: payload }),
    archive: (id) => request(`/drivers/${id}/archive`, { method: 'POST' }),
    syncRequirements: (id, documentTypeIds) =>
      request(`/drivers/${id}/requirements`, {
        method: 'PUT',
        body: { document_type_ids: documentTypeIds },
      }),
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
    validate: (versionId) =>
      request(`/documents/${versionId}/validate`, { method: 'POST' }),
    reject: (versionId, reason) =>
      request(`/documents/${versionId}/reject`, { method: 'POST', body: { reason } }),
  },
  documentRequests: {
    create: ({ driverId, documentTypeId }) =>
      request('/document-requests', {
        method: 'POST',
        body: { driver_id: driverId, document_type_id: documentTypeId },
      }),
    bulk: (driverId) =>
      request('/document-requests/bulk', {
        method: 'POST',
        body: { driver_id: driverId },
      }),
  },
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
