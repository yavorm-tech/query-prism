# frontend-react

The Query Prism web app: Vite + React 19 + TypeScript, Flowbite + Tailwind UI,
TanStack Query/Table/Form, React Router, Axios.

In production it is the `frontend` service in `docker-compose.yml` (profile `ssl`):
the Dockerfile builds the static bundle and nginx serves it
(`gateway/frontend-react.conf`), behind Traefik. See
[docs/services.md](../docs/services.md).

## Local development

Prerequisites: Node.js 22+ and the backend running locally
(`docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d` from the
repository root), which puts the API gateway on `http://localhost:8000`.

```bash
npm install
cp .env.example .env   # VITE_API_URL=http://localhost:8000
npm run dev            # http://localhost:5173
```

With `API_ENV=development` in the backend's `.env`, the API accepts requests from
the local Vite ports (CORS).

| Variable | Default | Description |
|---|---|---|
| `VITE_API_URL` | empty (same origin) | Base URL of the API. Set it for local dev; leave it empty for production builds, where Traefik serves the app and the API on one origin. Baked in at build time. |

## Scripts

| Command | What it does |
|---|---|
| `npm run dev` | Vite dev server with hot reload |
| `npm run build` | Type-check (`tsc -b`) and build into `dist/` |
| `npm run preview` | Serve the built `dist/` locally |
| `npm test` | Run the Vitest suite once |
| `npm run test:watch` | Vitest in watch mode |
| `npm run lint` | ESLint |

## Authentication

- The access token (short-lived JWT) is kept in `localStorage` under `token`; one
  Axios instance (`src/lib/api/client.ts`) attaches it to every request.
- The refresh token is an httpOnly cookie scoped to `/auth`, so requests are sent
  `withCredentials`. On a 401 the client calls `POST /auth/refresh` once (shared
  between concurrent requests), retries, and goes to `/login` if that fails.
- `/chat/stream` (Server-Sent Events) uses a separate fetch-based helper
  (`src/lib/api/stream.ts`) with the same refresh logic.

The endpoints the app uses are documented in [docs/api/](../docs/api/).
