from decimal import Decimal

from fastapi.testclient import TestClient

from app.domain.enums import SignalDirection
from app.services.signal_service import SignalService
from app.strategies.base import Signal as StrategySignal

USER_PAYLOAD = {
    "username": "jake",
    "email": "jake@example.com",
    "password": "correct-horse-battery-staple",
    "profile": {
        "account_size": "1000.00",
        "risk_preference": "aggressive",
        "trading_style": "momentum",
    },
}


def _auth_token(client: TestClient) -> str:
    client.post("/auth/register", json=USER_PAYLOAD)
    response = client.post(
        "/auth/login", data={"username": USER_PAYLOAD["username"], "password": USER_PAYLOAD["password"]}
    )
    return response.json()["access_token"]


def _seed_signal(client: TestClient, symbol: str = "NVDA") -> None:
    session = client.session_factory()
    try:
        SignalService(session).record_signal(
            StrategySignal(
                symbol=symbol,
                direction=SignalDirection.LONG,
                entry=Decimal("175.00"),
                stop_loss=Decimal("168.00"),
                target=Decimal("189.00"),
                confidence=82,
                reasoning=["fixture signal"],
                strategy_name="momentum",
            )
        )
    finally:
        session.close()


def test_list_signals_requires_authentication(client: TestClient) -> None:
    response = client.get("/signals")

    assert response.status_code == 401


def test_list_signals_returns_persisted_signals(client: TestClient) -> None:
    token = _auth_token(client)
    _seed_signal(client, "NVDA")
    _seed_signal(client, "AMD")

    response = client.get("/signals", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["symbol"] == "AMD"  # most recent first
    assert body[1]["symbol"] == "NVDA"


def test_list_signals_respects_limit(client: TestClient) -> None:
    token = _auth_token(client)
    for symbol in ["AAA", "BBB", "CCC"]:
        _seed_signal(client, symbol)

    response = client.get("/signals?limit=1", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert len(response.json()) == 1
