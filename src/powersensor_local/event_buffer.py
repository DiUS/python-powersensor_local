"""A simple fixed‑size buffer that stores event dictionaries."""
from typing import Any


class EventBuffer:
    """A simple fixed‑size buffer that stores event dictionaries.

    Parameters
    ----------
    keep : int
        The maximum number of events to retain in the buffer. When a new event
        is appended and this limit would be exceeded, the oldest event (the
        one at index 0) is removed.
    """
    def __init__(self, keep: int):
        self._keep = keep
        self._evs = []

    def find_by_key(self, key: str, value: Any):
        """Return the first event that contains ``key`` with the given ``value``.

        Parameters
        ----------
        key : str
            The dictionary key to search for.
        value : Any
            The value that the key must match.

        Returns
        -------
        dict | None
            The matching event dictionary, or ``None`` if no match is found.
        """
        for ev in self._evs:
            if key in ev and ev[key] == value:
                return ev
        return None

    def append(self, ev: dict):
        """Add an event to the buffer.

        If adding the new event would exceed ``self._keep``, the oldest event
        is removed to keep the buffer size bounded.

        Parameters
        ----------
        ev : dict
            The event dictionary to append.
        """
        self._evs.append(ev)
        if len(self._evs) > self._keep:
            del self._evs[0]

    def evict_older(self, key: str, value: float):
        """Remove events that are older than a given timestamp.

        Events are considered *older* if they contain ``key`` and its value is
        less than or equal to the provided ``value``. Eviction stops as soon
        as an event that does not satisfy this condition is encountered (the
        buffer is ordered by insertion time).

        Parameters
        ----------
        key : str
            The timestamp key to inspect in each event.
        value : float
            The cutoff timestamp; events with timestamps <= this value are removed.
        """
        while len(self._evs) > 0:
            ev = self._evs[0]
            if key in ev and ev[key] <= value:
                del self._evs[0]
            else:
                return
