import base64
import hashlib
import hmac
import time

from app.core.config import Settings
from app.realtime.turn import get_ice_servers


def _settings(**kw) -> Settings:
    base = dict(
        database_url="postgresql+asyncpg://x:y@localhost/z_test",
        stun_url="stun:stun.example.org:3478",
        turn_url="turn:turn.example.org:3478",
        turn_secret="",
        turn_ttl=3600,
    )
    base.update(kw)
    return Settings(_env_file=None, **base)


def test_ice_servers_stun_only_when_no_turn_secret():
    servers = get_ice_servers(_settings())
    assert servers == [{"urls": ["stun:stun.example.org:3478"]}]
    assert all("credential" not in s and "username" not in s for s in servers)


def test_turn_credentials_are_time_limited_hmac():
    secret = "s3cret-shared-with-coturn"
    before = int(time.time())
    servers = get_ice_servers(_settings(turn_secret=secret), identity="user-42")
    after = int(time.time())
    assert len(servers) == 2
    assert servers[0] == {"urls": ["stun:stun.example.org:3478"]}
    turn = servers[1]
    assert "turn:turn.example.org:3478" in turn["urls"]
    expiry_s, ident = turn["username"].split(":", 1)
    assert ident == "user-42"
    assert before + 3600 <= int(expiry_s) <= after + 3600
    expected = base64.b64encode(
        hmac.new(secret.encode(), turn["username"].encode(), hashlib.sha1).digest()
    ).decode()
    assert turn["credential"] == expected


def test_turn_ttl_respected():
    before = int(time.time())
    turn = get_ice_servers(_settings(turn_secret="k", turn_ttl=60))[1]
    expiry = int(turn["username"].split(":")[0])
    assert before + 60 <= expiry <= int(time.time()) + 60
