# Predictive Logistics & Forward Supply Chain (student prototype)

Synthetic-data prototype: demand forecast, stock-risk alerts, route status, dispatch recommendation, map dashboard. See [Problem_Statement.md](Problem_Statement.md), [PRD.md](PRD.md) and [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

## Getting started on your own clone

Everything runs locally against **your own** database, so your seeding and simulator runs never touch anyone else's data.

1. **Clone** the repo (you need read access) and, to share changes, push to your own fork and open a PR.
2. **Database:** create a free Postgres + PostGIS project on [Supabase](https://supabase.com) (or Neon). Copy the *Session pooler* connection string.
3. **Env:** from the repo root, `cp .env.example .env` and set `DATABASE_URL`. Never commit `.env`.
4. **Backend** (Python 3.11+):
   ```
   cd backend
   python -m venv .venv
   .venv\Scripts\activate        # Windows; macOS/Linux: source .venv/bin/activate
   pip install -r requirements.txt
   ```
5. **Seed** (from the repo root, venv active): `python data/generator/seed.py`. This also applies `db/migrations/*.sql`.
6. **Train** the forecast model: `python backend/ml/train.py`.
7. **Run:** `uvicorn app.main:app --reload` in `backend/`, then `npm install && npm run dev` in `frontend/`.

Full command list (tests, simulator, demo script, conventions) is in [CLAUDE.md](CLAUDE.md).

## Working rules

Collaborators technically have write access, so by agreement: **never push to `main`**. Work on your own branch (`git checkout -b yourname/topic`), push that branch, and open a PR for the owner to review and merge.
