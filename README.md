# RedlineAI

AI-powered contract redlining tool. Upload two or more contract versions and get a visual diff with inline markup, clause-level change tracking, and optional AI-generated risk analysis — all exportable as a Word document.

## Features

- **Visual diff viewer** — side-by-side comparison with word-level inline highlighting
- **Multi-document support** — compare original → each version, sequential, or cumulative
- **AI risk analysis** — clause-level risk scoring powered by Claude (optional)
- **DOCX export** — download a redlined Word document with tracked changes markup
- **Keyboard navigation** — move through changes without touching the mouse

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.13, FastAPI, python-docx |
| Diff engine | Hybrid LCS + semantic matching |
| AI | Anthropic Claude (claude-sonnet-4-5) |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS v4 |

## Deployment

### Vercel (frontend) + Render (backend)

**1. Deploy the backend to Render**

- Create a new **Web Service** on [Render](https://render.com), connect this repo, and select `render.yaml` — Render will auto-configure from it.
- In the Render dashboard, set these environment variables:
  - `CORS_ORIGINS` → `["https://your-app.vercel.app"]` *(fill in after step 2)*
  - `ANTHROPIC_API_KEY` → your key *(optional — users can also supply their own via the UI)*
- Note your Render service URL: `https://your-service.onrender.com`

**2. Deploy the frontend to Vercel**

- Import this repo on [Vercel](https://vercel.com). The `vercel.json` points it at the `frontend/` directory automatically.
- Add this environment variable in the Vercel dashboard:
  - `VITE_API_BASE_URL` → `https://your-service.onrender.com/api`
- Deploy — note your Vercel URL: `https://your-app.vercel.app`

**3. Finish wiring CORS**

- Go back to Render and set `CORS_ORIGINS` → `["https://your-app.vercel.app"]`
- Render will redeploy automatically.

> **Render free tier note:** the backend spins down after 15 min of inactivity; the first request after idle takes ~30s. Upgrade to the $7/mo Starter plan for always-on hosting.

---

## Local Development

### Prerequisites

- Python 3.13+
- Node.js 22+

### Backend

```bash
cd backend
pip install -r requirements.txt
PYTHONPATH=. python -m uvicorn app.main:app --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The Vite dev server proxies `/api` to the local backend automatically.

### API Key

AI features (change summaries, risk analysis) require an Anthropic API key. Two options:

- **Per-user via the UI** — click "Add API key" in the header. Stored in your browser only, never on the server.
- **Server-wide** — set `ANTHROPIC_API_KEY` as an environment variable on Render (or in a local `.env` file in `backend/`).

The app works without any key — the diff viewer and DOCX export are unaffected.

## API Routes

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/documents/upload` | Upload a DOCX file |
| `GET` | `/api/documents/` | List uploaded documents |
| `POST` | `/api/comparison/sessions` | Create a comparison session |
| `POST` | `/api/comparison/sessions/{id}/run` | Run the diff |
| `GET` | `/api/comparison/sessions/{id}/result` | Get diff results |
| `POST` | `/api/export/sessions/{id}/export` | Download redlined DOCX |

## Project Structure

```
contract_redliner/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI routers
│   │   ├── core/         # Config / settings
│   │   ├── models/       # Pydantic schemas
│   │   └── services/     # Parser, diff engine, AI, export
│   ├── tests/
│   │   └── fixtures/     # Sample NDA documents for testing
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── components/   # DiffViewer, ChangeDetailPanel, RiskBadge
│       ├── pages/        # UploadPage, ComparisonPage
│       ├── services/     # API client
│       └── types/        # TypeScript types
└── docs/
    └── adr/              # Architecture Decision Records (ADR-001 – ADR-006)
```

## Architecture Decisions

See [`docs/adr/`](docs/adr/) for the full set of ADRs covering stack selection, diff strategy, LLM integration, output generation, UI framework, and multi-document data model.
