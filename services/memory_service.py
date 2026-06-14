import json
import hashlib
from typing import Optional
from config import settings

try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class MemoryService:
    def __init__(self):
        self._client: Optional[object] = None
        self._use_redis = False
        self._local: dict = {}

    async def connect(self):
        if not REDIS_AVAILABLE:
            return
        try:
            self._client = aioredis.from_url(settings.redis_url, decode_responses=True)
            await self._client.ping()
            self._use_redis = True
        except Exception:
            self._client = None
            self._use_redis = False

    async def disconnect(self):
        if self._client:
            await self._client.aclose()

    # ── internals ────────────────────────────────────────────────────────────

    def _key(self, *parts: str) -> str:
        return ":".join(["aura"] + list(parts))

    def _hash(self, text: str) -> str:
        return hashlib.md5(text.encode()).hexdigest()[:10]

    async def _get(self, key: str) -> Optional[str]:
        if self._use_redis:
            return await self._client.get(key)
        return self._local.get(key)

    async def _set(self, key: str, value: str, ttl: int = 0):
        if self._use_redis:
            if ttl:
                await self._client.setex(key, ttl, value)
            else:
                await self._client.set(key, value)
        else:
            self._local[key] = value

    async def _exists(self, key: str) -> bool:
        if self._use_redis:
            return bool(await self._client.exists(key))
        return key in self._local

    # ── public API ────────────────────────────────────────────────────────────

    async def has_announced(self, session_id: str, event: str) -> bool:
        key = self._key("announced", session_id, self._hash(event))
        return await self._exists(key)

    async def mark_announced(self, session_id: str, event: str):
        key = self._key("announced", session_id, self._hash(event))
        await self._set(key, "1", ttl=settings.narration_cooldown_seconds)

    async def save_scene(self, session_id: str, scene: dict):
        key = self._key("scene", session_id)
        await self._set(key, json.dumps(scene), ttl=300)

    async def get_scene(self, session_id: str) -> Optional[dict]:
        key = self._key("scene", session_id)
        raw = await self._get(key)
        return json.loads(raw) if raw else None

    async def add_history(self, session_id: str, entry: dict):
        key = self._key("history", session_id)
        if self._use_redis:
            await self._client.lpush(key, json.dumps(entry))
            await self._client.ltrim(key, 0, settings.max_history_items - 1)
            await self._client.expire(key, 7200)
        else:
            bucket = self._local.setdefault(key, [])
            bucket.insert(0, entry)
            self._local[key] = bucket[: settings.max_history_items]

    async def get_history(self, session_id: str, limit: int = 20) -> list[dict]:
        key = self._key("history", session_id)
        if self._use_redis:
            items = await self._client.lrange(key, 0, limit - 1)
            return [json.loads(i) for i in items]
        return self._local.get(key, [])[:limit]

    async def get_context(self, session_id: str) -> dict:
        key = self._key("context", session_id)
        raw = await self._get(key)
        return json.loads(raw) if raw else {}

    async def update_context(self, session_id: str, updates: dict):
        ctx = await self.get_context(session_id)
        ctx.update(updates)
        key = self._key("context", session_id)
        await self._set(key, json.dumps(ctx), ttl=7200)

    async def clear_session(self, session_id: str):
        keys = [
            self._key("history", session_id),
            self._key("context", session_id),
            self._key("scene", session_id),
        ]
        if self._use_redis:
            for k in keys:
                await self._client.delete(k)
        else:
            for k in keys:
                self._local.pop(k, None)


memory_service = MemoryService()
