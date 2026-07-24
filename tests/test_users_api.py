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


def test_me_requires_authentication(client: TestClient) -> None:
    response = client.get("/users/me")

    assert response.status_code == 401


def test_me_returns_own_profile(client: TestClient) -> None:
    token = _register_and_login(client, JAKE_PAYLOAD)

    response = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "jake"
    assert body["profile"]["account_size"] == "1000.00"


def test_rejects_invalid_token(client: TestClient) -> None:
    response = client.get("/users/me", headers={"Authorization": "Bearer not-a-real-token"})

    assert response.status_code == 401


def test_update_profile_changes_own_data_only(client: TestClient) -> None:
    jake_token = _register_and_login(client, JAKE_PAYLOAD)
    friend_token = _register_and_login(client, FRIEND_PAYLOAD)

    update_response = client.patch(
        "/users/me/profile",
        json={"account_size": "2500.00"},
        headers={"Authorization": f"Bearer {jake_token}"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["account_size"] == "2500.00"

    friend_me = client.get("/users/me", headers={"Authorization": f"Bearer {friend_token}"})
    assert friend_me.json()["profile"]["account_size"] == "5000.00"
