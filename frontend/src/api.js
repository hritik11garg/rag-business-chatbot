// Thin API client: token storage, one automatic refresh retry on 401,
// and an async-generator SSE reader for the streaming chat endpoint
// (EventSource can't POST, so the stream is parsed off fetch()).

const STORAGE_KEY = "rag-chat-tokens";

export function loadTokens() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY)) || null;
  } catch {
    return null;
  }
}

export function saveTokens(tokens) {
  if (tokens) localStorage.setItem(STORAGE_KEY, JSON.stringify(tokens));
  else localStorage.removeItem(STORAGE_KEY);
}

export async function login(email, password) {
  const body = new URLSearchParams({ username: email, password });
  const res = await fetch("/auth/login", { method: "POST", body });
  if (!res.ok) throw new Error((await res.json()).detail || "Login failed");
  const tokens = await res.json();
  saveTokens(tokens);
  return tokens;
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

async function tryRefresh() {
  const tokens = loadTokens();
  if (!tokens?.refresh_token) return null;
  const res = await fetch("/auth/refresh", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: tokens.refresh_token }),
  });
  if (!res.ok) {
    saveTokens(null);
    return null;
  }
  const fresh = await res.json();
  saveTokens(fresh);
  return fresh;
}

// fetch with Authorization; on 401 refreshes once and retries.
export async function apiFetch(path, options = {}) {
  const doFetch = (token) =>
    fetch(path, {
      ...options,
      headers: {
        ...(options.headers || {}),
        Authorization: `Bearer ${token}`,
      },
    });

  let tokens = loadTokens();
  if (!tokens) throw new Error("Not logged in");
  let res = await doFetch(tokens.access_token);
  if (res.status === 401) {
    tokens = await tryRefresh();
    if (!tokens) throw new Error("Session expired");
    res = await doFetch(tokens.access_token);
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
    body: JSON.stringify({ question, top_k: 5 }),
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
