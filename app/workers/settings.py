"""Arq worker settings."""

from arq.connections import RedisSettings

from app.config import get_settings

settings = get_settings()


def parse_redis_url(url: str) -> RedisSettings:
    """Parse Redis URL into RedisSettings."""
    # Simple parser for redis://host:port format
    url = url.replace("redis://", "")
    if "@" in url:
        # Handle auth: redis://user:pass@host:port
        auth, hostport = url.rsplit("@", 1)
        if ":" in auth:
            _, password = auth.split(":", 1)
        else:
            password = auth
    else:
        hostport = url
        password = None
    
    if ":" in hostport:
        host, port = hostport.split(":")
        port = int(port.split("/")[0])  # Handle /db suffix
    else:
        host = hostport.split("/")[0]
        port = 6379
    
    return RedisSettings(host=host, port=port, password=password)


redis_settings = parse_redis_url(settings.redis_url)
