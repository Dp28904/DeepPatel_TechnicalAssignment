// Thin wrapper around fetch() used by every page.
// - Sends/receives JSON and adds the CSRF header the server requires on writes.
// - Turns error responses into an ApiError carrying {status, code, message, details}.
// - Redirects to the login page when the session has expired (401).
// - Optionally disables a button while the request is in flight (prevents double submits).

export class ApiError extends Error {
  constructor(status, code, message, details) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export async function api(method, url, { body, button, redirectOn401 = true } = {}) {
  const headers = { Accept: "application/json", "X-Requested-With": "fetch" };
  const options = { method, headers, credentials: "same-origin" };

  if (body instanceof FormData) {
    options.body = body; // browser sets the multipart Content-Type
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }

  if (button) button.disabled = true;
  try {
    let response;
    try {
      response = await fetch(url, options);
    } catch {
      throw new ApiError(0, "network_error", "Could not reach the server. Check your connection.");
    }

    const data = response.status === 204 ? null : await response.json().catch(() => null);

    if (response.ok) return data;

    if (response.status === 401 && redirectOn401) {
      window.location.href = `/login?next=${encodeURIComponent(window.location.pathname)}`;
    }
    const error = data?.error ?? {};
    throw new ApiError(
      response.status,
      error.code ?? "http_error",
      error.message ?? `Request failed (${response.status}).`,
      error.details ?? null,
    );
  } finally {
    if (button) button.disabled = false;
  }
}
