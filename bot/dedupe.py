"""Ignore an update we have already handled.

Telegram retries a webhook when your app does not answer with 200 quickly enough,
or answers with an error. Without this, one slow response means the bot sends the
same message twice. Keyed on update_id, which Telegram guarantees is unique per
update.

In-memory by design: this is a starter, and a dict with a TTL covers a single
instance. Running several instances behind a load balancer needs a shared store
(Redis: SET key NX EX 900 does exactly this).
"""

from __future__ import annotations

import time
from collections import OrderedDict
from typing import Callable


class UpdateGuard:
    def __init__(self, ttl_seconds: int = 900, max_entries: int = 4096,
                 clock: Callable[[], float] = time.monotonic):
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self.clock = clock
        self._seen: "OrderedDict[int, float]" = OrderedDict()

    def seen(self, update_id: int) -> bool:
        """Record the update. Returns True if it was already handled."""
        now = self.clock()
        self._evict(now)
        if update_id in self._seen:
            return True
        self._seen[update_id] = now
        while len(self._seen) > self.max_entries:
            self._seen.popitem(last=False)
        return False

    def _evict(self, now: float) -> None:
        while self._seen:
            oldest_id, stamp = next(iter(self._seen.items()))
            if now - stamp <= self.ttl_seconds:
                return
            self._seen.pop(oldest_id)

    def __len__(self) -> int:
        return len(self._seen)
