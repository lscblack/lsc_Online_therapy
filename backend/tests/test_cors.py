async def test_cors_allows_configured_origin(client):
    r = await client.get("/v1/health", headers={"Origin": "http://localhost:5173"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert r.headers.get("access-control-allow-credentials") == "true"


async def test_cors_preflight_and_unknown_origin(client):
    r = await client.options("/v1/health", headers={
        "Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,content-type"})
    assert r.status_code == 200
    r2 = await client.get("/v1/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in r2.headers
