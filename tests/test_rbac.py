def test_staff_can_create_category(client, staff_headers):
    resp = client.post("/categories/", json={"name": "Elektronik", "slug": "elektronik"}, headers=staff_headers)
    assert resp.status_code == 201


def test_staff_cannot_create_user(client, staff_headers):
    resp = client.post(
        "/auth/admin/users",
        json={"email": "x@x.com", "password": "secret123", "full_name": "X", "role": "customer"},
        headers=staff_headers,
    )
    assert resp.status_code == 403


def test_customer_cannot_create_category(client, user_headers):
    resp = client.post("/categories/", json={"name": "Giyim", "slug": "giyim"}, headers=user_headers)
    assert resp.status_code == 403


def test_admin_can_create_user(client, admin_headers):
    resp = client.post(
        "/auth/admin/users",
        json={"email": "new@x.com", "password": "secret123", "full_name": "New", "role": "staff"},
        headers=admin_headers,
    )
    assert resp.status_code == 201
