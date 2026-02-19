# NBA Live Projections App (BallDontLie)

Starter implementation for an ESPN Gamecast-style projections app.

## Structure

- `backend/`: FastAPI websocket service that pulls live stats and computes live point projections.
- `frontend/`: React + Vite UI for game list and player cards with realtime updates.

## Run backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn server:app --reload
```

## Run frontend

```bash
cd frontend
npm install
npm run dev
```

Set custom websocket URL via `VITE_WS_URL` if needed.
