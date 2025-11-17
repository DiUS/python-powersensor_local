from typing import Any


class EventBuffer:
    def __init__(self, keep: int):
        self._keep = keep
        self._evs = []

    def find_by_key(self, key: str, value: Any):
        for ev in self._evs:
            if key in ev and ev[key] == value:
                return ev
        return None

    def append(self, ev: dict):
        self._evs.append(ev)
        if len(self._evs) > self._keep:
            del self._evs[0]

    def evict_older(self, key: str, value: float):
        while len(self._evs) > 0:
            ev = self._evs[0]
            if key in ev and ev[key] <= value:
                del self._evs[0]
            else:
                return