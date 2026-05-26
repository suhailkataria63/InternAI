# InternAI Frontend — Production UI Upgrade

This zip contains the upgraded Next.js frontend only.

## Run locally

```bash
npm install
cp .env.example .env.local
npm run dev
```

Set your backend URL in `.env.local`:

```bash
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

## Backend integration kept intact

The UI still uses the original API paths in `lib/api.ts`:

- `POST /api/orchestrator/analyze-application`
- `POST /api/resume/upload`
- `POST /api/tracker/applications`
- `GET /api/tracker/applications`
- `PATCH /api/tracker/applications/:id/status`
- `DELETE /api/tracker/applications/:id`

## What changed

- Rebuilt visual system with liquid-glass cards, premium dark gradient shell, polished typography, responsive layouts, and animated glow/orb effects.
- Added production polish: accessible focus states, reduced-motion support, smoother buttons, tables, forms, scrollbars, and mobile breakpoints.
- Removed `node_modules`, `.next`, and macOS metadata from the delivery zip.
