from fastapi.testclient import TestClient

JAKE_PAYLOAD = {
    "username": "jake",
    "email": "jake@example.com",
    "password": "correct-horse-battery-staple",
    "profile": {
        "account_size": "1000.00",
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


def test_watchlist_requires_authentication(client: TestClient) -> None:
    response = client.get("/users/me/watchlist")

    assert response.status_code == 401


def test_watchlist_starts_empty(client: TestClient) -> None:
    token = _register_and_login(client, JAKE_PAYLOAD)

    response = client.get("/users/me/watchlist", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == []


def test_add_symbol_normalizes_to_uppercase(client: TestClient) -> None:
    token = _register_and_login(client, JAKE_PAYLOAD)

    response = client.post(
        "/users/me/watchlist", json={"symbol": "nvda"}, headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 201
    assert response.json()["symbol"] == "NVDA"


def test_duplicate_symbol_is_a_conflict(client: TestClient) -> None:
    token = _register_and_login(client, JAKE_PAYLOAD)
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/users/me/watchlist", json={"symbol": "NVDA"}, headers=headers)

    response = client.post("/users/me/watchlist", json={"symbol": "NVDA"}, headers=headers)

    assert response.status_code == 409


def test_remove_symbol(client: TestClient) -> None:
    token = _register_and_login(client, JAKE_PAYLOAD)
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/users/me/watchlist", json={"symbol": "NVDA"}, headers=headers)

    response = client.delete("/users/me/watchlist/NVDA", headers=headers)

    assert response.status_code == 204
    assert client.get("/users/me/watchlist", headers=headers).json() == []


def test_remove_symbol_not_on_watchlist_is_not_found(client: TestClient) -> None:
    token = _register_and_login(client, JAKE_PAYLOAD)

    response = client.delete("/users/me/watchlist/GHOST", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 404


def test_watchlists_are_isolated_between_users(client: TestClient) -> None:
    jake_token = _register_and_login(client, JAKE_PAYLOAD)
    friend_token = _register_and_login(client, FRIEND_PAYLOAD)

    client.post("/users/me/watchlist", json={"symbol": "NVDA"}, headers={"Authorization": f"Bearer {jake_token}"})
    client.post("/users/me/watchlist", json={"symbol": "TSLA"}, headers={"Authorization": f"Bearer {friend_token}"})

    jake_list = client.get("/users/me/watchlist", headers={"Authorization": f"Bearer {jake_token}"}).json()
    friend_list = client.get("/users/me/watchlist", headers={"Authorization": f"Bearer {friend_token}"}).json()

    assert [s["symbol"] for s in jake_list] == ["NVDA"]
    assert [s["symbol"] for s in friend_list] == ["TSLA"]
