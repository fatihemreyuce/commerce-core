def test_login_returns_refresh_token(client, normal_user):
    resp = client.post("/auth/login", json={"email": "user@test.com", "password": "secret123"})
    assert resp.status_code == 200
    assert "refresh_token" in resp.json()


def test_refresh_returns_new_access_token(client, normal_user):
    from app.core.security import create_refresh_token
    refresh = create_refresh_token(subject=str(normal_user.id))
    resp = client.post("/auth/refresh", json={"refresh_token": refresh})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_refresh_rejects_access_token(client, normal_user):
    from app.core.security import create_access_token
    access = create_access_token(subject=str(normal_user.id))
    resp = client.post("/auth/refresh", json={"refresh_token": access})
    assert resp.status_code == 401
