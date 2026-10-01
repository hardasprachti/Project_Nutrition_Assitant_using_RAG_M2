# AI Nutrition Assistant (RAG-based)

Citation-backed answers about food, nutrition and food safety, drawn only from official dietary guidance documents. See [docs/ProblemStatement.md](docs/ProblemStatement.md), [docs/Architecture.md](docs/Architecture.md) and [docs/implementation-plan.md](docs/implementation-plan.md).

> Work in progress: Phase 0 (foundations) is done. The full README (chunking, models, index, top-k, limitations, deployment) is written in Phase 9.

## Local setup

Requires Python 3.11+, Node 22+ and Docker.

```bash
cp .env.example .env                    # backend settings (git-ignored)
cp frontend/.env.example frontend/.env.local

docker compose up -d db                 # Postgres + pgvector on :5432

cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
alembic upgrade head                    # creates the schema and the pgvector extension
uvicorn app.main:app --reload           # http://localhost:8000/api/health

cd ../frontend
npm install
npm run dev                             # http://localhost:3000
```

## Checks (the same ones CI runs)

```bash
cd backend && ruff check . && ruff format --check . && mypy && pytest
cd frontend && npm run typecheck && npm run build
bash scripts/check_frontend_secrets.sh
```

Database integration tests run against `DATABASE_URL` and are skipped when Postgres is unreachable.
