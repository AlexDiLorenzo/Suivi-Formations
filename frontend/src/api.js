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
}
