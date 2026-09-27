// Talks to the Django backend (same origin). Changes send Django's CSRF token.

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
    /** A reason the app acts on, e.g. "password_needed". */
    readonly code?: string,
  ) {
    super(message);
  }
}

function csrfToken(): string {
  return document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/)?.[1] ?? "";
}

let csrfRequest: Promise<unknown> | null = null;

async function ensureCsrf() {
  if (csrfToken()) return;
  csrfRequest ??= fetch("/api/csrf", { credentials: "same-origin" });
  await csrfRequest;
  csrfRequest = null;
}

export async function api<T>(path: string, options: { method?: string; body?: unknown } = {}): Promise<T> {
  const method = options.method ?? "GET";
  if (method !== "GET") await ensureCsrf();
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      method,
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });
  } catch {
    throw new ApiError(0, "Can't reach the Python Trainer server. Check your internet connection.");
  }
  if (!response.ok) {
    let body: { detail?: unknown; code?: unknown } = {};
    try {
      body = (await response.json()) as typeof body;
    } catch {
      // not JSON
    }
    const message = typeof body.detail === "string" ? body.detail : `Something went wrong (error ${response.status}).`;
    throw new ApiError(response.status, message, typeof body.code === "string" ? body.code : undefined);
  }
  return (await response.json()) as T;
}
