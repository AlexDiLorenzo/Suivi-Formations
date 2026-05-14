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
  const data = text ? JSON.parse(text) : null
  if (!res.ok) {
    throw new ApiError(res.status, data?.detail || res.statusText)
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
  const data = text ? JSON.parse(text) : null
  if (!res.ok) throw new ApiError(res.status, data?.detail || res.statusText)
  return data
}

async function downloadAsBlob(path) {
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
  return res.blob()
}

export const api = {
  login: (email, password) =>
    request('/auth/login', { method: 'POST', body: { email, password }, auth: false }),
  me: () => request('/auth/me'),
  dashboard: () => request('/dashboard'),
  docTypes: () => request('/document-types'),
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
      fd.append('date_peremption', datePeremption)
      fd.append('file', file)
      return uploadFormData('/documents/upload', fd)
    },
    openInNewTab: async (versionId) => {
      const blob = await downloadAsBlob(`/documents/${versionId}/download`)
      const url = URL.createObjectURL(blob)
      window.open(url, '_blank', 'noopener')
      setTimeout(() => URL.revokeObjectURL(url), 60_000)
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
  publicRequests: {
    get: (token) => request(`/public/document-requests/${token}`, { auth: false }),
    upload: (token, { dateEmission, datePeremption, file }) => {
      const fd = new FormData()
      fd.append('date_emission', dateEmission)
      fd.append('date_peremption', datePeremption)
      fd.append('file', file)
      return uploadFormData(`/public/document-requests/${token}/upload`, fd, { auth: false })
    },
  },
}
