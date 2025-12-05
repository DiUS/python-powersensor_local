"""Abstraction for producing a household view."""

import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

PROJECT_ROOT = str(Path(__file__).parents[1])
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# pylint: disable=C0413
from powersensor_local.async_event_emitter import AsyncEventEmitter
from powersensor_local.event_buffer import EventBuffer

KEY_DUR_S = 'duration_s'
KEY_RESET = 'summation_resettime_utc'
KEY_START = 'starttime_utc'
KEY_SUM_J = 'summation_joules'
KEY_WATTS = 'watts'

@dataclass
class InstantaneousValues: # pylint: disable=C0115
    starttime_utc: int
    solar_watts: float
    housenet_watts: float
    duration_s: int

@dataclass
class SummationValues: # pylint: disable=C0115
    starttime_utc: int
    solar_summation: float
    solar_resettime: int
    housenet_summation: float
    housenet_resettime: int

@dataclass
class SummationDeltas: # pylint: disable=C0115
    solar_generation: float
    to_grid: float
    from_grid: float
    home_use: float

def same_duration(ev1: dict, ev2: dict):
    """Close-enough matching of duration_s in events."""
    dur = KEY_DUR_S
    if not dur in ev1 or not dur in ev2:
        return False
    # We don't care about sub-second differences
    d1 = round(ev1[dur], 0)
    d2 = round(ev2[dur], 0)
    return d1 == d2

def matching_instants(
        starttime_utc: int,
        solar_events: EventBuffer,
        housenet_events: EventBuffer) -> Optional[InstantaneousValues]:
    """Attempts to match and merge solar+housenet average_power events."""
    solar = solar_events.find_by_key(KEY_START, starttime_utc)
    housenet = housenet_events.find_by_key(KEY_START, starttime_utc)
    if solar is not None and housenet is not None and same_duration(solar, housenet):
        return InstantaneousValues(
            starttime_utc = starttime_utc,
            solar_watts = solar[KEY_WATTS],
            housenet_watts = housenet[KEY_WATTS],
            duration_s = round(solar[KEY_DUR_S], 0),
        )
    return None

def make_instant_housenet(ev: dict) -> Optional[InstantaneousValues]:
    """Helper for case where no solar merge is expected."""
    if ev is None:
        return None
    return InstantaneousValues(
        starttime_utc = ev[KEY_START],
        solar_watts = 0,
        housenet_watts = ev[KEY_WATTS],
        duration_s = round(ev[KEY_DUR_S], 0)
    )

def matching_summations(
        starttime_utc: int,
        solar_events: EventBuffer,
        housenet_events: EventBuffer) -> Optional[SummationValues]:
    """Attempts to match and merge solar+housenet summation events."""
    solar = solar_events.find_by_key(KEY_START, starttime_utc)
    housenet = housenet_events.find_by_key(KEY_START, starttime_utc)
    if solar is not None and housenet is not None:
        return SummationValues(
            starttime_utc = starttime_utc,
            solar_summation =solar[KEY_SUM_J],
            solar_resettime = solar[KEY_RESET],
            housenet_summation = housenet[KEY_SUM_J],
            housenet_resettime = housenet[KEY_RESET],
        )
    return None

def make_summation_housenet(ev: dict) -> Optional[SummationValues]:
    """Helper for case where no solar merge is expected."""
    if ev is None:
        return None
    return SummationValues(
        starttime_utc = ev[KEY_START],
        solar_summation = 0,
        solar_resettime = 0,
        housenet_summation = ev[KEY_SUM_J],
        housenet_resettime = ev[KEY_RESET]
    )



class VirtualHousehold(AsyncEventEmitter):
    """
    Class for processing average_power and summation_energy events into
    to/from grid, solar generation, and home usage events.

    To use, simply feed the appropriate PlugApi events to the
    process_average_power_event and process_summation_event member functions.

    Point-in-time power flow events include:

    * home_usage
    * from_grid
    * to_grid (only for solar kits)
    * solar_generation (only for solar kits)

    These all have an event payload in the form:

      { timestamp_utc: , watts: }

    Energy summation events include:

    * home_usage_summation
    * from_grid_summation
    * to_grid_summation (only for solar kits)
    * solar_generation_summation (only for solar kits)

    These all have an event payload in the form:

      { timestamp_utc: , summation_resettime_utc: , summation_joules: }

    Summations may reset at any time. Track the summation_resettime_utc
    field to take note of summation resets.
    """

    def __init__(self, with_solar: bool):
        """Constructor.
        with_solar True if it's already known that solar exists. Will be
          automatically enabled upon encountering a solar event during
          processing, but until such a time may generate incorrect values
          for home usage. Similarly, if this is set to True but no solar
          exists, no events may be generated.
        """
        super().__init__()
        self._expect_solar = with_solar
        self._summation = self.SummationInfo(0, 0, 0, 0)
        self._counters = self.Counters(0, 0, 0, 0, 0)
        self._solar_instants = EventBuffer(31)
        self._housenet_instants = EventBuffer(31)
        self._solar_summations = EventBuffer(5)
        self._housenet_summations = EventBuffer(5)

    async def process_average_power_event(self, ev: dict):
        """Ingests an event of type 'average_power'."""
        if not KEY_START in ev:
            return
        starttime_utc = int(ev[KEY_START])
        if 'role' in ev:
            role = ev['role']
            if role == 'house-net':
                self._housenet_instants.append(ev)
                await self._process_instants(starttime_utc)
            elif role == 'solar':
                if not self._expect_solar:
                    self._expect_solar = True
                self._solar_instants.append(ev)
                await self._process_instants(starttime_utc)

    async def process_summation_event(self, ev: dict):
        """Ingests an event of type 'summation_energy'."""
        if not KEY_START in ev:
            return
        starttime_utc = int(ev[KEY_START])
        if 'role' in ev:
            role = ev['role']
            if role == 'house-net':
                self._housenet_summations.append(ev)
                await self._process_summations(starttime_utc)
            elif role == 'solar':
                if not self._expect_solar:
                    self._expect_solar = True
                self._solar_summations.append(ev)
                await self._process_summations(starttime_utc)

    async def _process_instants(self, starttime_utc: int):
        if self._expect_solar:
            v = matching_instants(starttime_utc, self._solar_instants, self._housenet_instants)
        else:
            v = make_instant_housenet(self._housenet_instants.find_by_key(KEY_START, starttime_utc))
        if v is None:
            return

        self._solar_instants.evict_older(KEY_START, starttime_utc)
        self._housenet_instants.evict_older(KEY_START, starttime_utc)

        await self.emit('from_grid', {
            'timestamp_utc': v.starttime_utc,
            'watts': v.housenet_watts  if v.housenet_watts > 0 else 0,
        })
        await self.emit('home_usage', {
            'timestamp_utc': v.starttime_utc,
            'watts': max(v.housenet_watts - v.solar_watts, 0),
        })
        if self._expect_solar:
            await self.emit('solar_generation', {
                'timestamp_utc': v.starttime_utc,
                'watts': max(-v.solar_watts, 0),
            })
            await self.emit('to_grid', {
                'timestamp_utc': v.starttime_utc,
                'watts': -v.housenet_watts if v.housenet_watts < 0 else 0,
            })

    async def _process_summations(self, starttime_utc: int):
        if self._expect_solar:
            v = matching_summations(
                starttime_utc,
                self._solar_summations,
                self._housenet_summations)
        else:
            v = make_summation_housenet(
                self._housenet_summations.find_by_key(KEY_START, starttime_utc))
        if v is None:
            return

        self._solar_summations.evict_older(KEY_START, starttime_utc)
        self._housenet_summations.evict_older(KEY_START, starttime_utc)

        if not self._resettime_validation(v, starttime_utc):
            return

        deltas = self._calculate_summation_deltas(v)
        self._increment_counters(deltas)

        await self.emit('from_grid_summation', {
            'timestamp_utc': starttime_utc,
            'summation_resettime_utc': self._counters.resettime_utc,
            'summation_joules': self._counters.from_grid,
        })
        await self.emit('home_usage_summation', {
            'timestamp_utc': starttime_utc,
            'summation_resettime_utc': self._counters.resettime_utc,
            'summation_joules': self._counters.home_use,
        })
        if self._expect_solar:
            await self.emit('solar_generation_summation', {
                'timestamp_utc': starttime_utc,
                'summation_resettime_utc': self._counters.resettime_utc,
                'summation_joules': self._counters.solar_generation,
            })
            await self.emit('to_grid_summation', {
                'timestamp_utc': starttime_utc,
                'summation_resettime_utc': self._counters.resettime_utc,
                'summation_joules': self._counters.to_grid,
            })

    def _resettime_validation(self, v: SummationValues, starttime_utc: int) -> bool:
        res = True
        summ = self._summation
        if v.solar_resettime != summ.solar_resettime:
            summ.solar_resettime = v.solar_resettime
            summ.solar_last = v.solar_summation
            res = False
        if v.housenet_resettime != summ.housenet_resettime:
            summ.housenet_resettime = v.housenet_resettime
            summ.housenet_last = v.housenet_summation
            res = False
        if not res:
            self._clear_counters(starttime_utc)
        return res

    def _clear_counters(self, resettime_utc: int):
        self._counters = self.Counters(resettime_utc, 0, 0, 0, 0)

    def _calculate_summation_deltas(self, v: SummationValues) -> SummationDeltas:
        summ = self._summation

        solar_delta = v.solar_summation - summ.solar_last
        summ.solar_last = v.solar_summation

        housenet_delta = v.housenet_summation - summ.housenet_last
        summ.housenet_last = v.housenet_summation

        return SummationDeltas(
            solar_generation = max(-solar_delta, 0),
            to_grid = -housenet_delta if housenet_delta < 0 else 0,
            from_grid = housenet_delta if housenet_delta > 0 else 0,
            home_use = max(housenet_delta - solar_delta, 0)
        )

    def _increment_counters(self, d: SummationDeltas):
        self._counters.solar_generation += d.solar_generation
        self._counters.to_grid += d.to_grid
        self._counters.from_grid += d.from_grid
        self._counters.home_use += d.home_use

    @dataclass
    class SummationInfo: # pylint: disable=C0115
        solar_resettime: int
        solar_last: float
        housenet_resettime: int
        housenet_last: float

    @dataclass
    class Counters: # pylint: disable=C0115
        resettime_utc: int
        solar_generation: float
        to_grid: float
        from_grid: float
        home_use: float
