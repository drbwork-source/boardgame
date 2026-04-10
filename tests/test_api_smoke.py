"""
FastAPI smoke tests for core board/config/play endpoints.
"""

from __future__ import annotations

from pathlib import Path
import zipfile
from io import BytesIO

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.routes import config as config_routes


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture()
def isolated_decks_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Use a temporary decks.json location so CRUD tests never touch repo data."""
    monkeypatch.setattr(config_routes, "_get_decks_data_path", lambda: tmp_path)
    config_routes._DECKS.clear()
    config_routes._CARD_TEMPLATES.clear()
    config_routes._DECKS_INITIALIZED = False
    yield
    config_routes._DECKS.clear()
    config_routes._CARD_TEMPLATES.clear()
    config_routes._DECKS_INITIALIZED = False


def test_get_config_smoke(client: TestClient):
    res = client.get("/api/config")
    assert res.status_code == 200
    data = res.json()
    assert "tile_colors" in data
    assert "tile_metadata" in data
    assert "decks" in data


def test_board_generate_and_analysis_smoke(client: TestClient):
    gen = client.post(
        "/api/board/generate",
        json={"width": 12, "height": 10, "seed": 1234, "num_starts": 2, "generation_mode": "pathboard"},
    )
    assert gen.status_code == 200
    board = gen.json()["board"]
    assert len(board) == 10
    assert len(board[0]) == 12

    pathability = client.post("/api/board/pathability", json={"board": board})
    assert pathability.status_code == 200
    assert "ok" in pathability.json()

    validation = client.post("/api/board/validate", json={"board": board})
    assert validation.status_code == 200
    validation_data = validation.json()
    assert validation_data["goal_count"] == 1
    assert validation_data["start_count"] >= 1

    route = client.post("/api/board/route-quality", json={"board": board})
    assert route.status_code == 200
    assert isinstance(route.json().get("label"), str)

    sim = client.post("/api/board/simulate", json={"board": board, "num_games": 12, "seed": 7})
    assert sim.status_code == 200
    sim_data = sim.json()
    assert "expected_turns" in sim_data
    assert "heatmap" in sim_data
    assert "turn_spread" in sim_data
    assert "hotspot_count" in sim_data


def test_deck_crud_smoke(client: TestClient, isolated_decks_store):
    created = client.post(
        "/api/config/decks",
        json={"name": "Hazards", "card_template_ids": []},
    )
    assert created.status_code == 200
    deck_id = created.json()["id"]

    listed = client.get("/api/config/decks")
    assert listed.status_code == 200
    assert any(d["id"] == deck_id for d in listed.json())

    updated = client.patch(f"/api/config/decks/{deck_id}", json={"name": "Hazards+"})
    assert updated.status_code == 200
    assert updated.json()["name"] == "Hazards+"

    deleted = client.delete(f"/api/config/decks/{deck_id}")
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "ok"


def test_draw_card_for_tile_returns_placeholder_when_empty(client: TestClient, isolated_decks_store):
    res = client.get("/api/config/draw-card-for-tile", params={"symbol": "F"})
    assert res.status_code == 200
    body = res.json()
    assert body["id"] == "__placeholder"
    assert body["title"] == "Nothing happens"


def test_play_create_roll_and_end_turn_smoke(client: TestClient):
    board = [
        ["1", ".", "."],
        [".", ".", "."],
        [".", ".", "G"],
    ]
    created = client.post("/api/board/play/create", json={"board": board, "num_players": 1})
    assert created.status_code == 200
    payload = created.json()
    game_id = payload["game_id"]
    assert game_id

    rolled = client.post(f"/api/board/play/{game_id}/roll")
    assert rolled.status_code == 200

    ended = client.post(f"/api/board/play/{game_id}/end-turn")
    assert ended.status_code == 200


def test_export_print_tiled_includes_legend_file(client: TestClient):
    board = [
        ["1", ".", "."],
        [".", "F", "."],
        [".", ".", "G"],
    ]
    res = client.post(
        "/api/board/export-print",
        json={"board": board, "paper": "a4", "mode": "tiled"},
    )
    if res.status_code == 501:
        pytest.skip("Pillow not installed in test environment")
    assert res.status_code == 200
    archive = zipfile.ZipFile(BytesIO(res.content))
    names = archive.namelist()
    assert "board_legend.txt" in names
    legend = archive.read("board_legend.txt").decode("utf-8")
    assert "Board Legend" in legend
