from __future__ import annotations

import fnmatch
import time


class FakeRedis:
    def __init__(self) -> None:
        self._data: dict[str, bytes] = {}
        self._expiry: dict[str, float] = {}

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        return None

    def _purge_if_expired(self, key: str) -> None:
        exp = self._expiry.get(key)
        if exp is None:
            return
        if time.time() >= exp:
            self._data.pop(key, None)
            self._expiry.pop(key, None)

    async def get(self, key: str) -> bytes | None:
        self._purge_if_expired(key)
        return self._data.get(key)

    async def set(self, key: str, value, ex: int | None = None) -> bool:
        if isinstance(value, (bytes, bytearray)):
            b = bytes(value)
        else:
            b = str(value).encode("utf-8")
        self._data[key] = b
        if ex is not None:
            self._expiry[key] = time.time() + int(ex)
        else:
            self._expiry.pop(key, None)
        return True

    async def delete(self, key: str) -> int:
        existed = 1 if key in self._data else 0
        self._data.pop(key, None)
        self._expiry.pop(key, None)
        return existed

    async def incr(self, key: str) -> int:
        cur = await self.get(key)
        n = int(cur.decode("utf-8")) if cur else 0
        n += 1
        await self.set(key, str(n))
        return n

    async def mget(self, keys: list[bytes] | list[str]):
        out: list[bytes | None] = []
        for k in keys:
            ks = k.decode("utf-8") if isinstance(k, (bytes, bytearray)) else str(k)
            out.append(await self.get(ks))
        return out

    async def scan(self, cursor: int = 0, match: str | None = None, count: int = 10):
        keys = list(self._data.keys())
        if match:
            keys = [k for k in keys if fnmatch.fnmatch(k, match)]

        # Minimal scan implementation: return everything and cursor=0
        batch = keys[:count]
        return 0, [k.encode("utf-8") for k in batch]
