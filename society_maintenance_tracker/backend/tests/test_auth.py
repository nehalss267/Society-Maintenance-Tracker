from tests.conftest import register


def test_register_login_me_flow(client):
    headers, email = register(client)

    r = client.get("/api/auth/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["email"] == email
    assert r.json()["role"] == "RESIDENT"


def test_duplicate_email_rejected(client):
    _, email = register(client)

    r = client.post(
        "/api/auth/register",
        json={"name": "Dup", "email": email, "password": "Test@12345"},
    )
    assert r.status_code == 409


def test_bad_password_login(client):
    _, email = register(client)

    r = client.post("/api/auth/login", json={"email": email, "password": "nope"})
    assert r.status_code == 401


def test_me_requires_token(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401
