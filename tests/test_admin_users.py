def test_admin_can_create_admin_user(client, admin_headers):
    resp = client.post(
        "/auth/admin/users",
        headers=admin_headers,
        json={
            "email": "yeni.admin@test.com",
            "full_name": "Yeni Admin",
            "password": "secret123",
            "role": "admin",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "yeni.admin@test.com"
    assert body["role"] == "admin"


def test_admin_can_create_customer_user(client, admin_headers):
    resp = client.post(
        "/auth/admin/users",
        headers=admin_headers,
        json={
            "email": "yeni.musteri@test.com",
            "full_name": "Yeni Musteri",
            "password": "secret123",
            "role": "customer",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["role"] == "customer"


def test_non_admin_forbidden(client, user_headers):
    resp = client.post(
        "/auth/admin/users",
        headers=user_headers,
        json={
            "email": "x@test.com",
            "full_name": "X",
            "password": "secret123",
            "role": "customer",
        },
    )
    assert resp.status_code == 403


def test_no_auth_forbidden(client):
    resp = client.post(
        "/auth/admin/users",
        json={
            "email": "x@test.com",
            "full_name": "X",
            "password": "secret123",
            "role": "customer",
        },
    )
    assert resp.status_code == 403


def test_duplicate_email_rejected(client, admin_headers):
    payload = {
        "email": "dup@test.com",
        "full_name": "Dup",
        "password": "secret123",
        "role": "customer",
    }
    first = client.post("/auth/admin/users", headers=admin_headers, json=payload)
    assert first.status_code == 201
    second = client.post("/auth/admin/users", headers=admin_headers, json=payload)
    assert second.status_code == 400


def test_invalid_role_rejected(client, admin_headers):
    resp = client.post(
        "/auth/admin/users",
        headers=admin_headers,
        json={
            "email": "bad@test.com",
            "full_name": "Bad",
            "password": "secret123",
            "role": "superuser",
        },
    )
    assert resp.status_code == 422
