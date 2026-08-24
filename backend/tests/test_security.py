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


PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
JPEG_MAGIC = b"\xff\xd8\xff\xe0"


def test_complaint_photo_magic_bytes_enforced(client, resident):
    """Spoofed uploads (text bytes declared as image/png) must be rejected."""
    auth, _ = resident

    r = client.post(
        "/api/complaints",
        headers=auth,
        data={
            "category": "PLUMBING",
            "description": "Photo upload validation test complaint.",
        },
        files={"photo": ("fake.png", b"definitely not an image payload", "image/png")},
    )
    assert r.status_code == 422

    r = client.post(
        "/api/complaints",
        headers=auth,
        data={
            "category": "PLUMBING",
            "description": "Photo upload validation test complaint.",
        },
        files={"photo": ("swap.jpg", PNG_MAGIC + b"0" * 20, "image/jpeg")},
    )
    assert r.status_code == 422

    r = client.post(
        "/api/complaints",
        headers=auth,
        data={
            "category": "PLUMBING",
            "description": "Photo upload validation test complaint.",
        },
        files={"photo": ("gif.png", b"GIF89a" + b"0" * 10, "image/png")},
    )
    assert r.status_code == 422

    r = client.post(
        "/api/complaints",
        headers=auth,
        data={
            "category": "PLUMBING",
            "description": "Photo upload validation test complaint.",
        },
        files={"photo": ("real.png", PNG_MAGIC + b"0" * 20, "image/png")},
    )
    assert r.status_code == 201
    assert r.json()["photo_url"]
