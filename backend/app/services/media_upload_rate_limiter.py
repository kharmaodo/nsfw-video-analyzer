import time
from collections import defaultdict, deque
from threading import Lock


class UploadRateLimiter:
    """Limiteur mémoire par adresse IP.

    Il protège une instance API. En déploiement multi-réplicas, remplacez-le par
    un limiteur Redis ou une règle de reverse-proxy partagée.
    """

    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(
        self,
        client_key: str,
        *,
        maximum_requests: int,
        window_seconds: int,
    ) -> bool:
        now = time.monotonic()
        cutoff = now - window_seconds

        with self._lock:
            events = self._events[client_key]
            while events and events[0] <= cutoff:
                events.popleft()

            if len(events) >= maximum_requests:
                return False

            events.append(now)
            return True
