def test_cors_allows_configured_origin(client):
    resp = client.get("/", headers={"Origin": "http://localhost:3000"})
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"
