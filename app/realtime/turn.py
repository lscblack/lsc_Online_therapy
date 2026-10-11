"""ICE server configuration for WebRTC clients.

STUN is always returned. When TURN_SECRET is set, a TURN entry with short-lived
credentials is added using coturn's REST ephemeral-credential scheme
(``use-auth-secret``): username = "<expiry>:<identity>", credential =
base64(HMAC-SHA1(secret, username)).

Caveat: with STUN only, peers behind symmetric NATs / strict firewalls cannot
connect; production should always configure a publicly reachable TURN server.
"""
import base64
import hashlib
import hmac
import time

from app.core.config import Settings, get_settings


def get_ice_servers(
    settings: Settings | None = None, identity: str = "ubuzima"
) -> list[dict]:
    s = settings or get_settings()
    servers: list[dict] = [{"urls": [s.stun_url]}]
    if s.turn_secret:
        expiry = int(time.time()) + s.turn_ttl
        username = f"{expiry}:{identity}"
        digest = hmac.new(
            s.turn_secret.encode(), username.encode(), hashlib.sha1
        ).digest()
        servers.append(
            {
                "urls": [s.turn_url],
                "username": username,
                "credential": base64.b64encode(digest).decode(),
            }
        )
    return servers
