// Thin API client: handles auth token storage, optional development auto-login,
// and JSON request/response. All calls are relative to the Vite dev proxy (/api).

const TOKEN_KEY = "flyyy_token";
const LOGOUT_FLAG_KEY = "flyyy_logged_out";

// Development-only convenience. These are read from Vite env vars so they are
// NEVER baked into a production bundle by default and can be disabled entirely.
const DEV_AUTOLOGIN = import.meta.env.DEV && import.meta.env.VITE_AUTH_DEV_AUTOLOGIN !== "false";
const DEV_ADMIN_USER = import.meta.env.VITE_DEV_ADMIN_USER || "admin";
const DEV_ADMIN_PASSWORD = import.meta.env.VITE_DEV_ADMIN_PASSWORD || "CHANGE_ME_admin_2025";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.removeItem(LOGOUT_FLAG_KEY);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

// Decodes the JWT token to extract the username (sub field).
export function getCurrentUser() {
  const token = getToken();
  if (!token) {
    if (DEV_AUTOLOGIN && !localStorage.getItem(LOGOUT_FLAG_KEY)) {
      return DEV_ADMIN_USER;
    }
    return null;
  }
  const parts = token.split(".");
  if (parts.length < 2) return DEV_AUTOLOGIN && !localStorage.getItem(LOGOUT_FLAG_KEY) ? DEV_ADMIN_USER : null;
  try {
    const payload = JSON.parse(atob(parts[1]));
    return payload.sub || (DEV_AUTOLOGIN && !localStorage.getItem(LOGOUT_FLAG_KEY) ? DEV_ADMIN_USER : null);
  } catch {
    return DEV_AUTOLOGIN && !localStorage.getItem(LOGOUT_FLAG_KEY) ? DEV_ADMIN_USER : null;
  }
}

// Clears the auth token, sets a logout flag so ensureAuth() won't re-login,
// and dispatches a logout event so App.jsx can redirect to login.
export function logout() {
  clearToken();
  localStorage.setItem(LOGOUT_FLAG_KEY, "1");
  window.dispatchEvent(new Event("auth:logout"));
}

export function devAutologinEnabled() {
  return DEV_AUTOLOGIN;
}

export async function login(username, password) {
  const res = await fetch("/api/v1/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    let detail = "Login failed";
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  const data = await res.json();
  setToken(data.access_token);
  return data;
}

// Silent development login so the demo works out-of-the-box. Disabled when
// VITE_AUTH_DEV_AUTOLOGIN=false or in a production build. Respects the logout
// flag so a user-initiated logout is not immediately undone.
export async function ensureAuth() {
  if (getToken()) return;
  if (localStorage.getItem(LOGOUT_FLAG_KEY)) return;
  if (!DEV_AUTOLOGIN) return;
  try {
    await login(DEV_ADMIN_USER, DEV_ADMIN_PASSWORD);
  } catch {
    /* ignore - the UI will present a manual login */
  }
}

async function request(path, options = {}) {
  const token = getToken();
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`/api/v1${path}`, { ...options, headers });
  if (res.status === 401) {
    clearToken();
    throw new Error("Unauthorized");
  }
  if (!res.ok) {
    let detail = `${res.status}`;
    try {
      const body = await res.text();
      detail = body ? `${res.status}: ${body}` : detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  get: (path) => request(path),
  post: (path, body) =>
    request(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  patch: (path, body) =>
    request(path, { method: "PATCH", body: body ? JSON.stringify(body) : undefined }),
};
