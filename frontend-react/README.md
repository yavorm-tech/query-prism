# frontend-react

A Vite + React + TypeScript single-page app (Flowbite + Tailwind UI, TanStack
Query/Table/Form) that talks to the same backend gateway as the legacy Next.js
`frontend`. It is a drop-in replacement built during the React migration.

## Prerequisites

- Node.js 18+ and npm
- The backend gateway running and reachable (default `http://localhost:8000`)

## Setup

```bash
npm install
cp .env.example .env   # then edit if your gateway is not on localhost:8000
```

### Environment

| Variable       | Default                 | Description                          |
|----------------|-------------------------|--------------------------------------|
| `VITE_API_URL` | `http://localhost:8000` | Base URL of the backend nginx gateway |

`.env` is git-ignored; `.env.example` documents the contract.

## Scripts

| Command          | What it does                                              |
|------------------|----------------------------------------------------------|
| `npm run dev`    | Start the Vite dev server (hot reload)                    |
| `npm run build`  | Type-check (`tsc -b`) and produce a production build in `dist/` |
| `npm run preview`| Serve the built `dist/` locally                          |
| `npm test`       | Run the Vitest suite once                                |
| `npm run test:watch` | Run Vitest in watch mode                             |
| `npm run lint`   | Run ESLint                                                |

## Auth & storage contract

This app reads and writes the JWT bearer token in `localStorage` under the key
`token` — the **exact same contract** as the legacy `frontend`. A user logged
in via either app is recognized by the other. A single axios instance attaches
the token to every REST call and redirects to `/login` on a 401; the `/chat/stream`
SSE endpoint is handled by a separate fetch-based helper.

See `../api-endpoints.md` for the full list of gateway-exposed endpoints this
app consumes.

## Relationship to docker-compose

`docker-compose.yml` is intentionally **not** yet pointed at this app — the
legacy `frontend` remains the wired-up service. This project runs standalone via
`npm run dev` / a static `dist/` build against the same gateway until the
migration is cut over.
