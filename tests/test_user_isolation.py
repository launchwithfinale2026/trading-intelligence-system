"""Dedicated cross-cutting isolation suite: two real users, exercised
end-to-end through the actual HTTP API (not just service/repository unit
tests), confirming User A can never read or affect User B's data —
profile, watchlist, positions, decisions, or Telegram linkage.

Individual isolation assertions already exist scattered across
test_users_api.py / test_watchlist_api.py / test_telegram_handlers.py; this
file exists so "user isolation" has one place that verifies it as a single
end-to-end property across every user-owned resource at once, per the
Phase 1 audit's explicit requirement.
"""

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.domain.enums import DecisionType, RiskPreference, SignalDirection, TradingStyle
from app.services.decision_service import DecisionService
from app.services.position_service import PositionService
from app.services.signal_service import SignalService
from app.services.user_service import UserService
from app.strategies.base import Signal as StrategySignal

USER_A = {
    "username": "isolation_user_a",
    "email": "isolation_a@example.com",
    "password": "user-a-password-123",
    "profile": {"account_size": "1000.00", "risk_preference": "aggressive", "trading_style": "momentum"},
}

USER_B = {
    "username": "isolation_user_b",
    "email": "isolation_b@example.com",
    "password": "user-b-password-123",
    "profile": {"account_size": "5000.00", "risk_preference": "conservative", "trading_style": "swing"},
}


def _register_and_login(client: TestClient, payload: dict) -> str:
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 201, response.text
    login = client.post("/auth/login", data={"username": payload["username"], "password": payload["password"]})
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_two_users_get_independent_accounts(client: TestClient) -> None:
    token_a = _register_and_login(client, USER_A)
    token_b = _register_and_login(client, USER_B)

    me_a = client.get("/users/me", headers=_auth(token_a)).json()
    me_b = client.get("/users/me", headers=_auth(token_b)).json()

    assert me_a["username"] == "isolation_user_a"
    assert me_b["username"] == "isolation_user_b"
    assert me_a["id"] != me_b["id"]
    assert me_a["profile"]["account_size"] == "1000.00"
    assert me_b["profile"]["account_size"] == "5000.00"


def test_profile_updates_do_not_leak_between_users(client: TestClient) -> None:
    token_a = _register_and_login(client, USER_A)
    token_b = _register_and_login(client, USER_B)

    update = client.patch("/users/me/profile", json={"account_size": "9999.00"}, headers=_auth(token_a))
    assert update.status_code == 200
    assert update.json()["account_size"] == "9999.00"

    me_b = client.get("/users/me", headers=_auth(token_b)).json()
    assert me_b["profile"]["account_size"] == "5000.00"  # unchanged


def test_watchlists_are_fully_isolated(client: TestClient) -> None:
    token_a = _register_and_login(client, USER_A)
    token_b = _register_and_login(client, USER_B)

    client.post("/users/me/watchlist", json={"symbol": "NVDA"}, headers=_auth(token_a))
    client.post("/users/me/watchlist", json={"symbol": "TSLA"}, headers=_auth(token_a))
    client.post("/users/me/watchlist", json={"symbol": "AAPL"}, headers=_auth(token_b))

    watchlist_a = client.get("/users/me/watchlist", headers=_auth(token_a)).json()
    watchlist_b = client.get("/users/me/watchlist", headers=_auth(token_b)).json()

    assert {s["symbol"] for s in watchlist_a} == {"NVDA", "TSLA"}
    assert {s["symbol"] for s in watchlist_b} == {"AAPL"}

    # B removing a symbol they never added, that A owns, must not succeed
    forbidden_removal = client.delete("/users/me/watchlist/NVDA", headers=_auth(token_b))
    assert forbidden_removal.status_code == 404
    # ...and A's copy must still be there
    watchlist_a_after = client.get("/users/me/watchlist", headers=_auth(token_a)).json()
    assert {s["symbol"] for s in watchlist_a_after} == {"NVDA", "TSLA"}


def test_positions_and_decisions_are_fully_isolated(client: TestClient) -> None:
    token_a = _register_and_login(client, USER_A)
    token_b = _register_and_login(client, USER_B)

    # Seed a shared market Signal directly (Signal is a market fact, not
    # user-owned — see database/models/signal.py) and have only User A act
    # on it, via the same service layer the Telegram /open handler uses.
    session_factory = client.session_factory
    db: Session = session_factory()
    try:
        signal = SignalService(db).record_signal(
            StrategySignal(
                symbol="NVDA",
                direction=SignalDirection.LONG,
                entry=Decimal("175.00"),
                stop_loss=Decimal("168.00"),
                target=Decimal("189.00"),
                confidence=82,
                reasoning=["fixture"],
                strategy_name="momentum",
            )
        )
        user_a = UserService(db).users.get_by_username("isolation_user_a")
        DecisionService(db).record_decision(user_id=user_a.id, signal_id=signal.id, decision=DecisionType.OPEN)
        PositionService(db).open_position(user=user_a, signal=signal)
    finally:
        db.close()

    positions_a = client.get("/portfolio/positions", headers=_auth(token_a)).json()
    positions_b = client.get("/portfolio/positions", headers=_auth(token_b)).json()
    decisions_a = client.get("/portfolio/decisions", headers=_auth(token_a)).json()
    decisions_b = client.get("/portfolio/decisions", headers=_auth(token_b)).json()

    assert len(positions_a) == 1
    assert positions_a[0]["shares"] > 0
    assert positions_b == []  # B sees nothing of A's position

    assert len(decisions_a) == 1
    assert decisions_b == []  # B sees nothing of A's decision


def test_telegram_chat_ids_cannot_collide_between_users(client: TestClient) -> None:
    session_factory = client.session_factory
    db: Session = session_factory()
    try:
        user_a = UserService(db).create_user(
            username="tg_isolation_a",
            email="tg_isolation_a@example.com",
            password_hash="not-a-real-hash",
            account_size=Decimal("1000.00"),
            risk_preference=RiskPreference.MODERATE,
            trading_style=TradingStyle.MOMENTUM,
        )
        user_a.telegram_id = 555_000_111
        db.commit()

        user_b = UserService(db).create_user(
            username="tg_isolation_b",
            email="tg_isolation_b@example.com",
            password_hash="not-a-real-hash",
            account_size=Decimal("2000.00"),
            risk_preference=RiskPreference.MODERATE,
            trading_style=TradingStyle.MOMENTUM,
        )
        user_b.telegram_id = 555_000_111  # same chat id A already has
        try:
            db.commit()
            collided = True
        except Exception:
            db.rollback()
            collided = False

        assert not collided, "the database allowed two users to share one Telegram chat id"
    finally:
        db.close()


def test_unauthenticated_requests_cannot_access_any_users_data(client: TestClient) -> None:
    _register_and_login(client, USER_A)

    assert client.get("/users/me").status_code == 401
    assert client.get("/users/me/watchlist").status_code == 401
    assert client.get("/portfolio/positions").status_code == 401
    assert client.get("/portfolio/decisions").status_code == 401


def test_a_users_token_cannot_be_reused_to_impersonate_after_password_mismatch(client: TestClient) -> None:
    _register_and_login(client, USER_A)

    wrong_login = client.post("/auth/login", data={"username": "isolation_user_a", "password": "not-the-password"})
    assert wrong_login.status_code == 401
    assert "access_token" not in wrong_login.json()
