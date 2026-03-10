from __future__ import annotations


def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_create_without_alias_redirect_and_metadata_clicks(client):
    create = client.post(
        "/url/create",
        json={"original_url": "https://example.com", "expire_in_days": 7},
    )
    assert create.status_code == 200
    data = create.json()
    assert "short_code" in data
    code = data["short_code"]

    r1 = client.get(f"/r/{code}", allow_redirects=False)
    assert r1.status_code == 302
    assert r1.headers["location"].startswith("https://example.com")

    r2 = client.get(f"/r/{code}", allow_redirects=False)
    assert r2.status_code == 302

    meta = client.get(f"/url/{code}")
    assert meta.status_code == 200
    meta_json = meta.json()
    assert meta_json["short_code"] == code
    assert meta_json["long_url"].startswith("https://example.com")
    assert meta_json["clicks"] >= 2


def test_custom_alias_success_and_conflict(client):
    r1 = client.post(
        "/url/create",
        json={
            "original_url": "https://example.com",
            "custom_alias": "example",
            "expire_in_days": 7,
        },
    )
    assert r1.status_code == 200
    assert r1.json()["short_code"] == "example"

    r2 = client.post(
        "/url/create",
        json={
            "original_url": "https://example.org",
            "custom_alias": "example",
            "expire_in_days": 7,
        },
    )
    assert r2.status_code == 409


def test_loopback_target_rejected(client):
    r = client.post(
        "/url/create",
        json={"original_url": "http://127.0.0.1:8080", "expire_in_days": 7},
    )
    assert r.status_code == 422


def test_invalid_short_code_404(client):
    r = client.get("/url/this has spaces")
    assert r.status_code == 404
