from decimal import Decimal

from fastapi.testclient import TestClient

from app.domain.enums import DecisionType, SignalDirection
from app.repositories.user_repository import UserRepository
from app.services.decision_service import DecisionService
from app.services.position_service import PositionService
from app.services.signal_service import SignalService
from app.strategies.base import Signal as StrategySignal

JAKE_PAYLOAD = {
    "username": "jake",
    "email": "jake@example.com",
    "password": "correct-horse-battery-staple",
    "profile": {
        "account_size": "100000.00",
        "risk_preference": "aggressive",
        "trading_style": "momentum",
    },
}

FRIEND_PAYLOAD = {
    "username": "friend",
    "email": "friend@example.com",
    "password": "another-strong-password",
    "profile": {
        "account_size": "5000.00",
        "risk_preference": "conservative",
        "trading_style": "swing",
    },
}


def _register_and_login(client: TestClient, payload: dict) -> str:
    client.post("/auth/register", json=payload)
    response = client.post("/auth/login", data={"username": payload["username"], "password": payload["password"]})
    return response.json()["access_token"]


def test_market_status_requires_authentication(client: TestClient) -> None:
    assert client.get("/market/status").status_code == 401


def test_market_status_returns_open_or_closed(client: TestClient) -> None:
    token = _register_and_login(client, JAKE_PAYLOAD)

    response = client.get("/market/status", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["is_open"] in (True, False)


def test_positions_and_decisions_require_authentication(client: TestClient) -> None:
    assert client.get("/portfolio/positions").status_code == 401
    assert client.get("/portfolio/decisions").status_code == 401


def test_positions_and_decisions_are_isolated_per_user(client: TestClient) -> None:
    jake_token = _register_and_login(client, JAKE_PAYLOAD)
    friend_token = _register_and_login(client, FRIEND_PAYLOAD)

    session = client.session_factory()
    try:
        jake = UserRepository(session).get_by_username("jake")
        signal = SignalService(session).record_signal(
            StrategySignal(
                symbol="NVDA",
                direction=SignalDirection.LONG,
                entry=Decimal("100.00"),
                stop_loss=Decimal("90.00"),
                target=Decimal("120.00"),
                confidence=80,
                reasoning=["fixture"],
                strategy_name="momentum",
            )
        )
        DecisionService(session).record_decision(user_id=jake.id, signal_id=signal.id, decision=DecisionType.OPEN)
        PositionService(session).open_position(user=jake, signal=signal)
    finally:
        session.close()

    jake_positions = client.get("/portfolio/positions", headers={"Authorization": f"Bearer {jake_token}"}).json()
    friend_positions = client.get("/portfolio/positions", headers={"Authorization": f"Bearer {friend_token}"}).json()
    jake_decisions = client.get("/portfolio/decisions", headers={"Authorization": f"Bearer {jake_token}"}).json()
    friend_decisions = client.get("/portfolio/decisions", headers={"Authorization": f"Bearer {friend_token}"}).json()

    assert len(jake_positions) == 1
    assert jake_positions[0]["shares"] > 0
    assert friend_positions == []
    assert len(jake_decisions) == 1
    assert jake_decisions[0]["decision"] == "open"
    assert friend_decisions == []
