// API client for the cookie transport. Tokens live in httpOnly cookies the
// browser sends automatically — this code never sees or stores them, so an
// XSS payload has nothing to read (unlike the old localStorage approach).
//
// State-changing requests echo the readable csrf_token cookie back in an
// X-CSRF-Token header (double-submit CSRF defense). A 401 triggers one
// automatic refresh + retry. The SSE chat stream is parsed off fetch()
// (EventSource can't POST).

function getCookie(name) {
  const hit = document.cookie
    .split("; ")
    .find((row) => row.startsWith(name + "="));
  return hit ? decodeURIComponent(hit.slice(name.length + 1)) : null;
}

// The access/refresh cookies are httpOnly (invisible here); the csrf cookie
// is readable and is set for the life of the session, so its presence is our
// "logged in" hint. Real authorization is always enforced server-side.
export function isAuthed() {
  return Boolean(getCookie("csrf_token"));
}

function csrfHeader() {
  const token = getCookie("csrf_token");
  return token ? { "X-CSRF-Token": token } : {};
}

export async function login(email, password) {
  const body = new URLSearchParams({ username: email, password });
  const res = await fetch("/auth/login", { method: "POST", body });
  if (!res.ok) throw new Error((await res.json()).detail || "Login failed");
  return res.json(); // cookies are set by the server; body is ignored here
}

export async function signup(organizationName, email, password) {
  const res = await fetch("/auth/signup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      organization_name: organizationName,
      email,
      password,
    }),
  });
  if (!res.ok) throw new Error((await res.json()).detail || "Signup failed");
  return res.json();
}

export async function logout() {
  // Best-effort server-side revocation of the whole refresh family; the
  // server clears the cookies on its response.
  try {
    await fetch("/auth/logout", { method: "POST", headers: csrfHeader() });
  } catch {
    /* even if offline, the UI drops to the logged-out state */
  }
}

async function tryRefresh() {
  const res = await fetch("/auth/refresh", {
    method: "POST",
    headers: csrfHeader(),
  });
  return res.ok; // on success the server rotated the cookies for us
}

// fetch with the cookie session; adds CSRF header on state-changing calls,
// and on a 401 refreshes once and retries.
export async function apiFetch(path, options = {}) {
  const isMutating = (options.method || "GET").toUpperCase() !== "GET";
  const doFetch = () =>
    fetch(path, {
      ...options,
      headers: {
        ...(options.headers || {}),
        ...(isMutating ? csrfHeader() : {}),
      },
    });

  let res = await doFetch();
  if (res.status === 401) {
    if (!(await tryRefresh())) throw new Error("Session expired");
    res = await doFetch();
  }
  return res;
}

export async function fetchDocuments() {
  const res = await apiFetch("/documents");
  if (!res.ok) throw new Error("Could not load documents");
  return res.json();
}

export async function uploadPdf(file) {
  const form = new FormData();
  form.append("file", file);
  const res = await apiFetch("/documents/upload", {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error((await res.json()).detail || "Upload failed");
  return res.json();
}

// Yields {event, data} objects parsed from the SSE stream:
// several {event: "token", data: {text}} then {event: "done",
// data: {sources, confidence}}.
export async function* streamChat(question) {
  const res = await apiFetch("/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    // top_k omitted on purpose: the server owns the default (settings
    // .DEFAULT_TOP_K), so there's one source of truth, not a copy here.
    body: JSON.stringify({ question }),
  });
  if (!res.ok) throw new Error((await res.json()).detail || "Chat failed");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let sep;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      let event = "message";
      let data = "";
      for (const line of frame.split("\n")) {
        if (line.startsWith("event: ")) event = line.slice(7);
        else if (line.startsWith("data: ")) data += line.slice(6);
      }
      if (data) yield { event, data: JSON.parse(data) };
    }
  }
}
