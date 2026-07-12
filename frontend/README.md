# Frontend — minimal React demo UI

A small Vite + React SPA over the FastAPI backend: organization
signup/login (JWT with automatic refresh), PDF upload, and a chat view
that consumes the `/chat/stream` SSE endpoint token-by-token, showing
the confidence badge and source filenames on every answer.

## Run (dev)

Backend running on `:8000` (see ../SETUP.md), then:

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
```

The Vite dev server proxies `/auth`, `/chat`, `/documents`, `/me` to
`http://127.0.0.1:8000` (see vite.config.js), so there is no CORS
setup — the browser only ever talks to one origin.

## Notes

- `EventSource` can't send POST bodies or Authorization headers, so
  the SSE stream is read from `fetch()` with a small frame parser
  (src/api.js) — same wire format, no library.
- Tokens live in localStorage; `apiFetch` retries exactly once through
  `/auth/refresh` on a 401, then gives up and returns to the login
  screen.
- `npm run build` produces a static `dist/` (gitignored); serving it
  in production would need either a reverse proxy on the same origin
  or CORS middleware on the API.
