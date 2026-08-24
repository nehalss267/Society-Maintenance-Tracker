from tests.conftest import register


def test_weak_password_rejected(client):
    r = client.post(
        "/api/auth/register",
        json={"name": "Weak", "email": "weak@t.dev", "password": "abcdefgh"},
    )
    assert r.status_code == 422

    r = client.post(
        "/api/auth/register",
        json={"name": "Short", "email": "short@t.dev", "password": "ab1"},
    )
    assert r.status_code == 422

    r = client.post(
        "/api/auth/register",
        json={"name": "Ok", "email": "ok@t.dev", "password": "goodpass123"},
    )
    assert r.status_code == 201


def test_cors_and_security_headers_present(client):
    r = client.options(
        "/api/auth/login",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"

    h = client.get("/health")
    assert h.headers["x-content-type-options"] == "nosniff"
    assert h.headers["x-frame-options"] == "DENY"


def test_upload_path_traversal_contained(client):
    from app.services.storage_service import resolve_local_path

    evil = resolve_local_path("/uploads/../../backend/.env")
    assert evil is None

    ok = resolve_local_path("/uploads/documents/somefile.png")
    assert ok is not None
