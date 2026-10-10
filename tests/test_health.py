async def test_health_ok(client):
    r = await client.get("/v1/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_ready_checks_db(client):
    r = await client.get("/v1/ready")
    assert r.status_code == 200
