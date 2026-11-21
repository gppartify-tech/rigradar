// Tiny wrapper around fetch() for our FastAPI backend.
// - adds the JWT token (if logged in)
// - turns query params objects into ?a=1&b=2 (arrays become repeated keys)
// - throws ApiError with the server's error message

const TOKEN_KEY = "partify_token";

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* private mode - ignore */
  }
}

export class ApiError extends Error {
  constructor(status, message, data) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

export function buildQuery(params) {
  const qs = new URLSearchParams();
  for (const [key, value] of Object.entries(params || {})) {
    if (value === undefined || value === null || value === "" || value === false) continue;
    if (Array.isArray(value)) value.forEach((v) => qs.append(key, v));
    else qs.append(key, value);
  }
  const text = qs.toString();
  return text ? `?${text}` : "";
}

export async function api(path, { method = "GET", body, params, form } = {}) {
  const headers = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  let payload;
  if (form) payload = form;
  else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  const res = await fetch(`/api${path}${buildQuery(params)}`, { method, headers, body: payload });
  if (res.status === 204) return null;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = data?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((d) => `${d.loc?.slice(-1)[0] ?? ""}: ${d.msg}`).join(", ")
          : `Request failed (${res.status})`;
    if (res.status === 401 && token) {
      setToken(null);
      window.dispatchEvent(new Event("auth:expired"));
    }
    throw new ApiError(res.status, message, data);
  }
  return data;
}
