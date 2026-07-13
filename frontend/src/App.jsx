import { useEffect, useRef, useState } from "react";
import {
  fetchDocuments,
  isAuthed,
  login,
  logout,
  signup,
  streamChat,
  uploadPdf,
} from "./api.js";

export default function App() {
  const [authed, setAuthed] = useState(isAuthed());
  if (!authed) return <Login onLogin={() => setAuthed(true)} />;
  return (
    <Chat
      onLogout={async () => {
        await logout(); // revoke server-side, then drop local tokens
        setAuthed(false);
      }}
    />
  );
}

function Login({ onLogin }) {
  const [mode, setMode] = useState("login");
  const [org, setOrg] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      if (mode === "signup") await signup(org, email, password);
      await login(email, password);
      onLogin();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-wrap">
      <form className="login-card" onSubmit={submit}>
        <h1>📚 Knowledge Base Chat</h1>
        {mode === "signup" && (
          <input
            placeholder="Organization name"
            value={org}
            onChange={(e) => setOrg(e.target.value)}
            required
          />
        )}
        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        {error && <p className="error">{error}</p>}
        <button disabled={busy}>
          {busy ? "…" : mode === "login" ? "Log in" : "Create organization"}
        </button>
        <p className="switch">
          {mode === "login" ? (
            <>
              New organization?{" "}
              <a onClick={() => setMode("signup")}>Sign up</a>
            </>
          ) : (
            <>
              Have an account? <a onClick={() => setMode("login")}>Log in</a>
            </>
          )}
        </p>
      </form>
    </div>
  );
}

function Chat({ onLogout }) {
  const [documents, setDocuments] = useState([]);
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [notice, setNotice] = useState("");
  const bottomRef = useRef(null);
  const fileRef = useRef(null);

  async function refreshDocuments() {
    try {
      setDocuments(await fetchDocuments());
    } catch {
      onLogout(); // refresh failed twice => session gone
    }
  }

  useEffect(() => {
    refreshDocuments();
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function onUpload(e) {
    const file = e.target.files[0];
    if (!file) return;
    setNotice(`Uploading ${file.name}…`);
    try {
      const result = await uploadPdf(file);
      setNotice(`Ingested ${result.filename} (${result.chunks_stored} chunks)`);
      refreshDocuments();
    } catch (err) {
      setNotice(err.message);
    } finally {
      fileRef.current.value = "";
    }
  }

  async function ask(e) {
    e.preventDefault();
    const q = question.trim();
    if (!q || streaming) return;
    setQuestion("");
    setStreaming(true);
    setMessages((m) => [
      ...m,
      { role: "user", text: q },
      { role: "assistant", text: "", sources: [], confidence: null },
    ]);

    const patchLast = (patch) =>
      setMessages((m) => {
        const copy = m.slice();
        copy[copy.length - 1] = { ...copy[copy.length - 1], ...patch };
        return copy;
      });

    try {
      let text = "";
      for await (const { event, data } of streamChat(q)) {
        if (event === "token") {
          text += data.text;
          patchLast({ text });
        } else if (event === "done") {
          patchLast({ sources: data.sources, confidence: data.confidence });
        }
      }
    } catch (err) {
      patchLast({ text: `⚠ ${err.message}`, confidence: "low" });
    } finally {
      setStreaming(false);
    }
  }

  return (
    <div className="layout">
      <aside>
        <h2>Documents</h2>
        <button
          className="upload"
          onClick={() => fileRef.current.click()}
        >
          + Upload PDF
        </button>
        <input
          ref={fileRef}
          type="file"
          accept="application/pdf"
          hidden
          onChange={onUpload}
        />
        {notice && <p className="notice">{notice}</p>}
        <ul>
          {documents.map((d) => (
            <li key={d.id} title={d.filename}>
              {d.filename}
            </li>
          ))}
        </ul>
        <button className="logout" onClick={onLogout}>
          Log out
        </button>
      </aside>

      <main>
        <div className="messages">
          {messages.length === 0 && (
            <p className="empty">
              Upload a PDF, then ask questions about it.
            </p>
          )}
          {messages.map((m, i) => (
            <div key={i} className={`msg ${m.role}`}>
              <div className="bubble">
                {m.text || (streaming && i === messages.length - 1 ? "…" : "")}
                {m.role === "assistant" && m.confidence && (
                  <div className="meta">
                    <span className={`badge ${m.confidence}`}>
                      {m.confidence} confidence
                    </span>
                    {m.sources?.length > 0 && (
                      <span className="sources">
                        {m.sources.join(", ")}
                      </span>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
        <form className="ask" onSubmit={ask}>
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask about your documents…"
            disabled={streaming}
          />
          <button disabled={streaming || !question.trim()}>Send</button>
        </form>
      </main>
    </div>
  );
}
