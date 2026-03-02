# ADR-001: Full-Stack Application Architecture

## Status: Proposed

## Context

RedlineAI requires a full-stack web application that can:
- Accept DOCX (Phase 1) and PDF (Phase 2) file uploads up to 50MB / 500 pages
- Perform CPU-intensive document parsing and diff computation
- Integrate with LLM APIs for AI-powered summaries and risk analysis
- Render complex interactive UIs (side-by-side diff views, synchronized scrolling, inline annotations)
- Generate formatted DOCX and PDF output documents
- Handle concurrent users with potentially long-running comparison jobs

The architecture must balance development velocity (single developer via Claude Code), runtime performance, Python ecosystem access (critical for document processing), and rich frontend interactivity.

## Options Considered

### Option A: Python (FastAPI) + React SPA + Celery Task Queue

**How it works:** Decoupled architecture with a Python FastAPI backend serving a REST API, a React (TypeScript) single-page application for the frontend, and Celery with Redis for async document processing tasks.

- **Frontend:** React 18+ with TypeScript
- **Backend:** Python 3.12+ with FastAPI
- **Task Queue:** Celery + Redis
- **Deployment:** Docker Compose (dev), Docker containers on cloud (prod)
- **File Processing:** Async via Celery workers

| Dimension | Assessment |
|---|---|
| Implementation Effort | High - two apps, WebSocket coordination, Celery infra |
| Performance | Excellent - async I/O, dedicated workers, smooth React UI |
| Limitations | Two codebases, CORS config, Celery+Redis adds infra complexity |
| Dependencies | fastapi, uvicorn, celery, redis, python-docx, react, vite |

---

### Option B: Next.js Full-Stack (TypeScript) + Python Microservice

**How it works:** Next.js handles frontend (React SSR/CSR) and API routes. A separate Python FastAPI microservice handles document parsing and LLM calls since Python has far superior libraries for both.

- **Frontend:** Next.js 14+ with React and TypeScript
- **Backend:** Next.js API routes + Python FastAPI microservice
- **Task Queue:** BullMQ + Redis (Node side) or FastAPI background tasks (Python side)
- **Deployment:** Vercel (Next.js) + Docker (Python service)

| Dimension | Assessment |
|---|---|
| Implementation Effort | High - two services in two languages, split deployment |
| Performance | Good - SSR initial load, but network hop to Python service |
| Limitations | Two languages anyway, network latency, deployment complexity, SSR overkill for auth'd app |
| Dependencies | next, react, typescript, fastapi, python-docx, bullmq, redis |

---

### Option C: Python (Django) + HTMX + Alpine.js

**How it works:** Django monolith serves HTML pages and API endpoints. HTMX provides dynamic interactivity without a JS build step. Alpine.js handles small client-side interactions.

- **Frontend:** Django templates + HTMX + Alpine.js
- **Backend:** Python 3.12+ with Django 5+
- **Task Queue:** Django-Q2 or Huey
- **Deployment:** Single Docker container

| Dimension | Assessment |
|---|---|
| Implementation Effort | Low-Medium - single codebase, single language, mature framework |
| Performance | Good for server ops, limited for complex client-side interactions |
| Limitations | HTMX cannot handle synchronized side-by-side scrolling, real-time diff navigation, or inline expanding panels without significant custom JS |
| Dependencies | django, django-q2, python-docx, htmx, alpinejs |

---

### Option D: Python (FastAPI) + React SPA (Monorepo, No Celery)

**How it works:** FastAPI backend and React frontend in a single monorepo. Uses FastAPI's built-in BackgroundTasks for lightweight jobs and asyncio + ProcessPoolExecutor for CPU-heavy document processing. WebSocket for real-time progress updates. Single Docker Compose deployment.

- **Frontend:** React 18+ with TypeScript (Vite)
- **Backend:** Python 3.12+ with FastAPI
- **Task Queue:** FastAPI BackgroundTasks + ProcessPoolExecutor
- **Deployment:** Single Docker Compose (nginx + fastapi + frontend static)

| Dimension | Assessment |
|---|---|
| Implementation Effort | Medium - monorepo simplifies dev, no Celery infrastructure |
| Performance | Very good - async I/O, process pool for CPU, React for rich UI |
| Limitations | ProcessPool less robust than Celery at scale (no retry, no distributed). Migration path exists. |
| Dependencies | fastapi, uvicorn, python-docx, react, typescript, vite |

---

## Comparison Matrix

| Criterion (Weight) | Option A: FastAPI+React+Celery | Option B: Next.js+Python | Option C: Django+HTMX | Option D: FastAPI+React Monorepo |
|---|---|---|---|---|
| UI Richness (25%) | 9/10 | 9/10 | 5/10 | 9/10 |
| Doc Processing (20%) | 10/10 | 8/10 | 10/10 | 10/10 |
| Impl Speed (20%) | 6/10 | 5/10 | 8/10 | 8/10 |
| Maintainability (10%) | 6/10 | 5/10 | 9/10 | 8/10 |
| Performance (10%) | 9/10 | 7/10 | 7/10 | 8/10 |
| Extensibility (10%) | 9/10 | 8/10 | 7/10 | 9/10 |
| Deploy Simplicity (5%) | 5/10 | 4/10 | 9/10 | 8/10 |
| **Weighted Score** | **8.15** | **7.05** | **7.35** | **8.65** |

## Decision: Option D - Python (FastAPI) + React SPA (Monorepo, No Celery)

## Rationale

1. **Python backend is non-negotiable** for document processing. `python-docx`, PDF parsing tools (Phase 2), and LLM SDKs (Anthropic, OpenAI) are all Python-first. Option B adds an unnecessary network hop.

2. **React frontend is necessary** for the complex interactive UI. The PRD requires side-by-side synchronized scrolling, inline change navigation, expandable detail panels, version switching tabs, and rich data visualization. HTMX/Alpine.js (Option C) cannot deliver this without reimplementing a JS framework.

3. **Celery is premature** for MVP. FastAPI BackgroundTasks and ProcessPoolExecutor handle async document processing for single-server deployments. Celery+Redis (Option A) adds infrastructure complexity not justified until horizontal scaling is needed. Migration path exists.

4. **Monorepo simplifies development.** Single repository with `backend/` and `frontend/`, single Docker Compose file, reduced context-switching for Claude Code-driven implementation.

5. **Extensibility for Phase 2** is strong. FastAPI backend can add PDF parsing modules without architectural changes. React frontend adds views incrementally. ProcessPoolExecutor handles additional CPU-heavy tasks.

## Consequences

- **Frontend:** React 18+ with TypeScript, Vite build, served as static files via nginx
- **Backend:** FastAPI with Python 3.12+, uvicorn ASGI server
- **Async Processing:** BackgroundTasks + ProcessPoolExecutor for CPU-heavy work
- **Real-time Updates:** WebSocket via FastAPI for progress reporting
- **Database:** SQLite for MVP (session/upload metadata), migration path to PostgreSQL
- **File Storage:** Local filesystem for MVP, abstraction layer for cloud storage later
- **Deployment:** Docker Compose with 2 services (fastapi + nginx serving React static)
- **Trade-off accepted:** At horizontal scale, ProcessPoolExecutor would need replacement with Celery or similar. Acceptable for MVP velocity.

### Project Structure

```
contract_redliner/
├── backend/
│   ├── app/
│   │   ├── api/          # API routes
│   │   ├── core/         # Config, security
│   │   ├── models/       # Pydantic models
│   │   ├── services/     # Business logic (parsing, diff, AI)
│   │   └── main.py
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   └── services/
│   ├── package.json
│   └── Dockerfile
├── docs/
│   └── adr/
├── docker-compose.yml
└── README.md
```
