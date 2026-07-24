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


def test_register_creates_user(client: TestClient) -> None:
    response = client.post("/auth/register", json=JAKE_PAYLOAD)

    assert response.status_code == 201
    body = response.json()
    assert body["username"] == "jake"
    assert body["profile"]["risk_preference"] == "aggressive"
    assert "password" not in body
    assert "password_hash" not in body


def test_register_rejects_duplicate_username(client: TestClient) -> None:
    client.post("/auth/register", json=JAKE_PAYLOAD)
    response = client.post("/auth/register", json={**JAKE_PAYLOAD, "email": "other@example.com"})

    assert response.status_code == 409


def test_login_returns_token_for_correct_credentials(client: TestClient) -> None:
    client.post("/auth/register", json=JAKE_PAYLOAD)

    response = client.post(
        "/auth/login",
        data={"username": "jake", "password": "correct-horse-battery-staple"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert len(body["access_token"]) > 0


def test_login_rejects_wrong_password(client: TestClient) -> None:
    client.post("/auth/register", json=JAKE_PAYLOAD)

    response = client.post("/auth/login", data={"username": "jake", "password": "wrong-password"})

    assert response.status_code == 401


def test_login_rejects_unknown_username(client: TestClient) -> None:
    response = client.post("/auth/login", data={"username": "ghost", "password": "whatever"})

    assert response.status_code == 401


def test_logout_returns_200(client: TestClient) -> None:
    response = client.post("/auth/logout")

    assert response.status_code == 200


def test_register_rejects_invalid_email(client: TestClient) -> None:
    response = client.post("/auth/register", json={**JAKE_PAYLOAD, "email": "not-an-email"})

    assert response.status_code == 422


def test_register_rejects_too_short_password(client: TestClient) -> None:
    response = client.post("/auth/register", json={**JAKE_PAYLOAD, "password": "short"})

    assert response.status_code == 422


def test_register_rejects_username_with_invalid_characters(client: TestClient) -> None:
    response = client.post("/auth/register", json={**JAKE_PAYLOAD, "username": "not a valid username!"})

    assert response.status_code == 422


def test_register_rejects_missing_profile(client: TestClient) -> None:
    payload = {k: v for k, v in JAKE_PAYLOAD.items() if k != "profile"}

    response = client.post("/auth/register", json=payload)

    assert response.status_code == 422


def test_register_rejects_duplicate_email_with_different_username(client: TestClient) -> None:
    client.post("/auth/register", json=JAKE_PAYLOAD)

    response = client.post("/auth/register", json={**JAKE_PAYLOAD, "username": "someone_else"})

    assert response.status_code == 409
