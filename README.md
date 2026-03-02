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

## Getting Started

### Docker (recommended)

Requires [Docker Desktop](https://www.docker.com/products/docker-desktop/).

```bash
# Optional: add your Anthropic API key (users can also supply their own via the UI)
cp .env.example .env

docker compose up --build
```

Open http://localhost. Uploaded files are stored in a named Docker volume so they persist across restarts.

To stop:
```bash
docker compose down
```

---

### Manual setup (development)

#### Prerequisites

- Python 3.13+
- Node.js 22+

#### Backend

```bash
cd backend
pip install -r requirements.txt

# Optional: enable server-side AI analysis
cp ../.env.example .env   # then add your ANTHROPIC_API_KEY

PYTHONPATH=. python -m uvicorn app.main:app --port 8000
```

#### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.

### API Key

AI features (change summaries, risk analysis) require an Anthropic API key. You can supply it two ways:

- **Per-user via the UI** — click "Add API key" in the header. The key is stored in your browser only, never on the server.
- **Server-wide via `.env`** — set `ANTHROPIC_API_KEY` in `.env`. All users share this key.

The app runs without any key — the diff viewer and DOCX export work normally.

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
