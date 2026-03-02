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

### Prerequisites

- Python 3.13+
- Node.js 22+

### Backend

```bash
cd backend
pip install -r requirements.txt

# Optional: enable AI analysis
cp .env.example .env   # then add your ANTHROPIC_API_KEY

PYTHONPATH=. python -m uvicorn app.main:app --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.

### Environment Variables

Create `backend/.env` to enable AI features:

```
ANTHROPIC_API_KEY=sk-ant-...
```

The app runs without an API key — AI analysis is silently disabled and all other features work normally.

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
