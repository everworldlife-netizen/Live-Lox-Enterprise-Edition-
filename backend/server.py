import asyncio
import json
import os
from dataclasses import dataclass
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

app = FastAPI(title="NBA Projection Engine", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BDL_API_KEY = os.getenv("BALLDONTLIE_API_KEY", "")
POLL_INTERVAL_SECONDS = float(os.getenv("LIVE_POLL_INTERVAL_SECONDS", "3"))


@dataclass
class BaselineProjection:
    ppm: float
    expected_minutes: int


BASELINE_PROJECTIONS: dict[str, BaselineProjection] = {
    "LeBron James": BaselineProjection(ppm=1.24, expected_minutes=35),
    "Stephen Curry": BaselineProjection(ppm=1.18, expected_minutes=34),
    "Nikola Jokic": BaselineProjection(ppm=1.43, expected_minutes=36),
}


class BallDontLieClient:
    """Minimal API adapter with a mock fallback for local development."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._base_url = "https://api.balldontlie.io/v1"

    async def fetch_live_box_scores(self, client: httpx.AsyncClient) -> list[dict[str, Any]]:
        if not self._api_key:
            return self._mock_live_box_scores()

        response = await client.get(
            f"{self._base_url}/box_scores/live",
            headers={"Authorization": self._api_key},
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
        return payload.get("data", [])

    def _mock_live_box_scores(self) -> list[dict[str, Any]]:
        return [
            {
                "player": {"first_name": "LeBron", "last_name": "James"},
                "team": {"abbreviation": "LAL"},
                "pts": 18,
                "ast": 5,
                "reb": 6,
                "pf": 2,
                "min": "19:15",
                "game": {"id": 1, "home_team": {"abbreviation": "LAL"}, "visitor_team": {"abbreviation": "DEN"}, "home_team_score": 54, "visitor_team_score": 51, "status": "Q2 03:22"},
            },
            {
                "player": {"first_name": "Nikola", "last_name": "Jokic"},
                "team": {"abbreviation": "DEN"},
                "pts": 14,
                "ast": 4,
                "reb": 9,
                "pf": 3,
                "min": "17:04",
                "game": {"id": 1, "home_team": {"abbreviation": "LAL"}, "visitor_team": {"abbreviation": "DEN"}, "home_team_score": 54, "visitor_team_score": 51, "status": "Q2 03:22"},
            },
            {
                "player": {"first_name": "Stephen", "last_name": "Curry"},
                "team": {"abbreviation": "GSW"},
                "pts": 20,
                "ast": 2,
                "reb": 3,
                "pf": 1,
                "min": "18:40",
                "game": {"id": 2, "home_team": {"abbreviation": "GSW"}, "visitor_team": {"abbreviation": "BOS"}, "home_team_score": 49, "visitor_team_score": 47, "status": "Q2 04:11"},
            },
        ]


def parse_minutes(minutes_played: str | None) -> int:
    if not minutes_played or ":" not in minutes_played:
        return 0
    minute_portion, _ = minutes_played.split(":", maxsplit=1)
    return int(minute_portion)


def calculate_live_projection(
    player_name: str,
    current_points: int,
    minutes_played: int,
    personal_fouls: int,
    score_diff: int,
) -> float:
    baseline = BASELINE_PROJECTIONS.get(player_name, BaselineProjection(ppm=1.0, expected_minutes=30))
    remaining_minutes = max(0, baseline.expected_minutes - minutes_played)

    if personal_fouls >= 4 and minutes_played < 24:
        remaining_minutes *= 0.45

    if abs(score_diff) >= 20 and minutes_played >= 30:
        remaining_minutes *= 0.2

    live_projection = current_points + (baseline.ppm * remaining_minutes)
    return round(live_projection, 1)


def map_dashboard_payload(raw_player_stats: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for entry in raw_player_stats:
        player_name = f"{entry['player']['first_name']} {entry['player']['last_name']}"
        minutes_played = parse_minutes(entry.get("min"))
        game = entry.get("game", {})
        home_score = game.get("home_team_score", 0)
        visitor_score = game.get("visitor_team_score", 0)
        score_diff = home_score - visitor_score

        normalized.append(
            {
                "id": player_name.lower().replace(" ", "-"),
                "name": player_name,
                "team": entry.get("team", {}).get("abbreviation", "NBA"),
                "game_id": game.get("id"),
                "matchup": f"{game.get('visitor_team', {}).get('abbreviation', '??')} @ {game.get('home_team', {}).get('abbreviation', '??')}",
                "game_status": game.get("status", "Live"),
                "actual_pts": int(entry.get("pts", 0)),
                "actual_ast": int(entry.get("ast", 0)),
                "actual_reb": int(entry.get("reb", 0)),
                "fouls": int(entry.get("pf", 0)),
                "minutes": minutes_played,
                "projected_pts": calculate_live_projection(
                    player_name,
                    current_points=int(entry.get("pts", 0)),
                    minutes_played=minutes_played,
                    personal_fouls=int(entry.get("pf", 0)),
                    score_diff=score_diff,
                ),
            }
        )

    return sorted(normalized, key=lambda x: x["projected_pts"], reverse=True)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.websocket("/ws/live-gamecast")
async def live_gamecast_socket(websocket: WebSocket) -> None:
    await websocket.accept()
    bdl_client = BallDontLieClient(api_key=BDL_API_KEY)

    async with httpx.AsyncClient() as client:
        try:
            while True:
                raw_stats = await bdl_client.fetch_live_box_scores(client)
                payload = map_dashboard_payload(raw_stats)
                await websocket.send_text(json.dumps(payload))
                await asyncio.sleep(POLL_INTERVAL_SECONDS)
        except WebSocketDisconnect:
            return
        except Exception as exc:  # noqa: BLE001
            await websocket.send_text(json.dumps({"error": str(exc)}))
            await websocket.close(code=1011)
