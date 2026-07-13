def test_add_list_remove_favorite(client, user_headers, make_variant):
    variant = make_variant()
    product_id = str(variant.product_id)

    add = client.post("/favorites", json={"product_id": product_id}, headers=user_headers)
    assert add.status_code == 201

    listing = client.get("/favorites", headers=user_headers)
    assert listing.status_code == 200
    assert len(listing.json()) == 1
    assert listing.json()[0]["product"]["id"] == product_id

    remove = client.delete(f"/favorites/{product_id}", headers=user_headers)
    assert remove.status_code == 204

    empty = client.get("/favorites", headers=user_headers)
    assert empty.json() == []


def test_duplicate_favorite_returns_400(client, user_headers, make_variant):
    variant = make_variant()
    pid = str(variant.product_id)
    client.post("/favorites", json={"product_id": pid}, headers=user_headers)
    dup = client.post("/favorites", json={"product_id": pid}, headers=user_headers)
    assert dup.status_code == 400


def test_favorites_requires_auth(client):
    resp = client.get("/favorites")
    assert resp.status_code in (401, 403)


def test_remove_nonexistent_favorite_returns_404(client, user_headers, make_variant):
    variant = make_variant()
    resp = client.delete(f"/favorites/{variant.product_id}", headers=user_headers)
    assert resp.status_code == 404
