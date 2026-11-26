"""Environment: connects driver -> DUT -> monitor -> scoreboard (+ coverage).

One call to `step()` is one fully checked clock cycle. Tests and sequences
talk to the environment in transactions only; nothing above this layer
touches a pin.
"""
import hashlib

from tb.driver import FifoDriver
from tb.monitor import FifoMonitor
from tb.scoreboard import FifoScoreboard


class FifoEnv:
    def __init__(self, dut, data_width, depth, seed=0, coverage_sampler=None):
        self.dut = dut
        self.data_width = data_width
        self.depth = depth

        self.driver = FifoDriver(dut, data_width)
        self.monitor = FifoMonitor(dut)
        self.scoreboard = FifoScoreboard(data_width, depth, seed)
        self.coverage_sampler = coverage_sampler      # callable(CycleRecord) or None

        # A SHA-1 of every transaction driven. Two runs with the same seed must
        # print the same digest; that is how we prove a seed replays exactly.
        self.stimulus_digest = hashlib.sha1()

        self.last_pins = None
        # The DUT state is unknown (X) until the first reset edge, so the
        # before-the-edge check only starts after that.
        self.state_is_known = False

    @property
    def model(self):
        return self.scoreboard.model

    async def step(self, write_enable, read_enable, write_data=0, reset_n=1):
        """Drive one cycle, check it at both sample points, sample coverage."""
        self.stimulus_digest.update(
            f"{reset_n}{write_enable}{read_enable}{write_data:x};".encode())

        before_edge_check = self._check_before_edge if self.state_is_known else None
        await self.driver.drive_one_cycle(write_enable, read_enable, write_data, reset_n,
                                          check_before_edge=before_edge_check)
        self.last_pins = self.monitor.read_pins()
        if not reset_n:
            self.state_is_known = True

        record = self.scoreboard.check_after_edge(self.last_pins)
        if self.coverage_sampler is not None:
            self.coverage_sampler(record)
        return record

    def _check_before_edge(self):
        pins_before_edge = self.monitor.read_pins(before_edge=True)
        self.scoreboard.check_before_edge(pins_before_edge)

    async def reset(self, cycles=3, write_enable=0, read_enable=0, write_data=0):
        for _ in range(cycles):
            await self.step(write_enable, read_enable, write_data, reset_n=0)

    async def drain(self):
        """Pop everything still stored, so every entry reaches the head and is
        compared, then pop once more (a read while empty)."""
        while not self.model.empty:
            await self.step(0, 1)
        await self.step(0, 1)
