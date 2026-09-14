# SCGpipeline

A hallucination detection system for LLM responses based on [SelfCheckGPT](https://github.com/potsawee/selfcheckgpt),
built as an undergraduate thesis project (Software Engineering). Consists of
a FastAPI backend (chat + hallucination evaluation + monitoring dashboard),
a Celery worker for asynchronous evaluation, and a Vue 3 frontend for the
chat and dashboard UI.

## Table of Contents

-   [Architecture](#architecture)
-   [Prerequisites](#prerequisites)
-   [Installation & Setup](#installation--setup)
-   [Running the Application](#running-the-application)
-   [How to Use the Application](#how-to-use-the-application)
-   [Environment Variables](#environment-variables)
-   [Running Without a Tunnel (Pure Local)](#running-without-a-tunnel-pure-local)
-   [Folder Structure](#folder-structure)
-   [Research Materials](#research-materials)
-   [License](#license)

## Architecture

```
┌──────────────┐       ┌───────────────┐       ┌──────────────────┐
│  Frontend    │──────>│   FastAPI     │──────>│  MySQL           │
│  Vue 3 + Vite│  HTTP │  (app/main.py)│       │  (user data,     │
└──────────────┘       └──────┬────────┘       │  chats, feedback)│
                              │                └──────────────────┘
                              ▼
                     ┌───────────────┐       ┌────────────────┐
                     │ Redis (Docker)│──────>│ Celery Worker  │
                     └───────────────┘       │ (evaluate      │
                                             │  SelfCheckGPT) │
                                             └────────┬───────┘
                                                      ▼
                                            ┌─────────────────┐
                                            │ MLflow          │
                                            │ (tracking       │
                                            │  experiment)    │
                                            └─────────────────┘
```

-   **Backend** (`app/`) — FastAPI, runs locally (not in Docker). Handles
    authentication, chat rooms, streaming LLM responses (Ollama/OpenAI/Gemini/Fireworks),
    and dashboard endpoints.
-   **Worker** (`app/services/detection_task.py`) — Celery task that runs the
    SelfCheckGPT evaluation (stochastic sampling + NLI scoring) asynchronously.
    Also runs locally (needs direct GPU/CPU access, so it isn't containerized).
-   **Frontend** (`frontend/`) — Vue 3 + Vite, runs locally via `npm run dev`.
-   **MySQL & Redis** — **the only services that run in Docker**, so you don't
    need to install a database/message broker manually.
-   **MLflow** — logs parameters & metrics for every evaluation, runs locally
    (file-based or `mlflow ui`).
-   **selfcheckgpt/** — a locally modified copy of the SelfCheckGPT library
    (see [`selfcheckgpt/MODIFICATIONS.md`](selfcheckgpt/MODIFICATIONS.md) for
    what was changed from upstream).

## Prerequisites

| Requirement                      | Version  | Notes                                                     |
| -------------------------------- | -------- | --------------------------------------------------------- |
| Python                           | 3.10.x   | Must be exactly 3.10 (see `pyproject.toml`)               |
| Node.js                          | 18+      | For the frontend (Vite 8)                                 |
| [uv](https://docs.astral.sh/uv/) | latest   | Python package manager used by this project               |
| Docker + Docker Compose          | latest   | **MySQL + Redis only** — see below                        |
| GPU + CUDA 12.4                  | optional | For faster NLI model inference. Works on CPU too (slower) |
| [Ollama](https://ollama.com)     | optional | If `LLM_PROVIDER=ollama` (default, no API key needed)     |

## Installation & Setup

1. **Clone the repo**

```bash
   git clone <this-repo-url>
   cd SCGpipeline
```

2. **Set up environment variables**

```bash
   cp .env.example .env
```

Open `.env` and fill in at least:

-   `SECRET_KEY` — generate a new one, e.g. `openssl rand -hex 32`
-   `LLM_PROVIDER` — `ollama` for no API key, or `gemini`/`openai`/`fireworks` + `LLM_API_KEY`
-   `DATABASE_URL` — the default already matches `docker-compose.yml` below
    (`mysql+pymysql://root:root_password@localhost:3306/scgpipeline`)

See [Environment Variables](#environment-variables) for the full reference.

3. **Start MySQL + Redis via Docker**

```bash
   docker compose up -d
```

Lightweight (just two small images), no build required.

4. **Install backend dependencies**

```bash
   uv sync
   uv run python -m spacy download en_core_web_sm
```

> Not using `uv`? There's a `requirements.txt` fallback — read the note at
> the top of that file about installing torch manually first, then:
> `pip install -r requirements.txt --break-system-packages`

5. **Install frontend dependencies**

```bash
   cd frontend && npm install && cd ..
```

6. **Create database tables + default user**

```bash
   uv run python -m app.test_db
```

Creates all tables and a default developer account (`peneliti` / `passpeneliti`).

7. **(Optional) Set up Ollama** if `LLM_PROVIDER=ollama`:

```bash
   ollama pull llama3
```

All the steps above only need to be run once during initial setup.

## Running the Application

### Option A — one command (Windows/PowerShell)

```powershell
.\start.ps1
# or without the MLflow UI:
.\start.ps1 -NoMLflow
```

### Option B — using `make` (if available)

```bash
make start     # backend + celery + frontend + mlflow
```

### Option C — manual, each service in its own terminal

```bash
# Terminal 1 — backend
uv run uvicorn app.main:app --reload

# Terminal 2 — Celery worker
uv run celery -A app.services.detection_task.celery_app worker --loglevel=info --pool=solo

# Terminal 3 — frontend
cd frontend && npm run dev

# Terminal 4 — MLflow UI (optional)
uv run mlflow ui --port 5000
```

Once everything is running:

-   Frontend: http://localhost:5174
-   Backend API: http://127.0.0.1:8000 (interactive docs at `/docs`)
-   MLflow UI: http://127.0.0.1:5000

## How to Use the Application

Once the app is running and you're logged in (default: `peneliti` / `passpeneliti`),
here's how it works:

1. **Chat** (`/chat`) — a regular chatbot-style interface. Every LLM response
   is automatically evaluated in the background by the Celery worker
   (SelfCheckGPT), without blocking or delaying the answer you see.
2. **Dashboard** (`/dashboard`, developer role) — summary statistics across
   all conversations **from users with role `user`** (developer chats are
   intentionally excluded, matching the original research methodology):
   total chats, average hallucination score, category distribution
   (factual/borderline/hallucinated).
3. **Participants** (`/participants`, developer role) — a list of `user`-role
   accounts with their full chat history, expandable per row.
4. **Config** (`/config`, developer role) — change the LLM provider, model,
   number of stochastic samples, temperature, and classification thresholds
   at runtime.

To create additional users, use the `POST /api/developer/create-user` endpoint
(see `/docs`, developer-only) or add them directly via SQL — see also
`app/test_db.py` for an example of seeding several users at once.

## Environment Variables

All variables are fully documented with comments in [`.env.example`](.env.example).

| Variable                    | Required?              | Purpose                                                              |
| --------------------------- | ---------------------- | -------------------------------------------------------------------- |
| `DATABASE_URL`              | yes                    | SQLAlchemy connection to MySQL (Docker, exposed on `localhost:3306`) |
| `SECRET_KEY`                | yes                    | JWT signing key — generate your own, don't use the example           |
| `LLM_PROVIDER`              | yes                    | `ollama` \| `openai` \| `gemini` \| `fireworks` \| `none`            |
| `LLM_API_KEY`               | if not `ollama`/`none` | API key for the LLM provider                                         |
| `REDIS_HOST` / `REDIS_PORT` | yes                    | Celery broker (Docker, exposed on `localhost:6379`)                  |
| `MLFLOW_TRACKING_URI`       | yes                    | MLflow tracking storage location (default: local folder)             |
| `HF_HOME`                   | optional               | Hugging Face model cache location                                    |
| `CORS_ORIGINS`              | yes                    | Frontend origin allowed to access the backend                        |
| `VITE_API_BASE_URL`         | optional               | Set if frontend & backend are on different hosts/ports               |
| `BACKEND_URL`               | yes (dev)              | Vite dev-server proxy target                                         |
| `VITE_ALLOWED_HOSTS`        | optional               | Extra hostnames (e.g. a tunnel domain)                               |

## Running Without a Tunnel (Pure Local)

This project's original setup used [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)
to expose the app to the internet. **The tunnel is entirely optional** — for
local use, just leave:

-   `CORS_ORIGINS=http://localhost:5174` (default)
-   `VITE_ALLOWED_HOSTS=` (empty)

## Folder Structure

```
SCGpipeline/
├── app/ # FastAPI backend (runs locally)
│ ├── main.py # Entry point (uvicorn app.main:app)
│ ├── api_routes.py # Chat, auth, room, feedback endpoints
│ ├── dashboard_routes.py # Dashboard monitoring endpoints
│ ├── core/ # Config, database, security
│ ├── models/ # SQLAlchemy models
│ └── services/ # SelfCheckGPT evaluator, Celery tasks
├── frontend/ # Vue 3 + Vite SPA (runs locally)
├── selfcheckgpt/ # Vendored & modified — see MODIFICATIONS.md
├── research/ # Thesis research materials (dataset, notebook, benchmark script)
├── docker-compose.yml # MySQL + Redis ONLY
├── .gitattributes # Line-ending normalization (LF) across OSes
├── start.ps1 / stop.ps1 # Manual start/stop scripts (Windows)
├── makefile # Cross-platform command shortcuts (requires make)
├── pyproject.toml / uv.lock # Dependency management (uv)
└── .env.example # Config template (backend + frontend)
```

## Research Materials

The [`research/`](research/) folder contains materials for the thesis report,
kept separate from the application source code:

-   `data/dataset_v3.json` — the WikiBio GPT-3 dataset (238 labeled biographies)
-   `run_benchmark.py` — validates the detection module's accuracy against the
    dataset above. Run from inside `research/`:

```bash
  cd research
  uv run python run_benchmark.py
```

-   `research_experiment.ipynb` — exploratory notebook
-   `scripts/` — supporting research scripts (MLflow backfill, Layer-1 markdown
    cleaning experiment) — run manually, not part of the main app flow

## License

MIT — see [`LICENSE`](LICENSE). The vendored SelfCheckGPT code under
`selfcheckgpt/` retains its own original MIT license — see
`selfcheckgpt/LICENSE` and `selfcheckgpt/MODIFICATIONS.md`.
