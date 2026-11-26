"""Monitor: reads every pin of the FIFO and packs it into one PinSnapshot.

The monitor is independent of the driver. It reads the input pins back from
the DUT instead of asking the driver what it sent, so a driver bug cannot hide
behind a matching expectation.
"""
from dataclasses import dataclass
from typing import Optional

UNKNOWN_COUNT = -1   # stored in `count` when the pin holds X or Z


@dataclass
class PinSnapshot:
    cycle: int
    rst_n: int
    wr_en: int
    rd_en: int
    wr_data: int
    count: int                # UNKNOWN_COUNT if the pin is X or Z
    full: int
    empty: int
    rd_data: Optional[int]    # None while the DUT says empty, or if X or Z


class FifoMonitor:
    def __init__(self, dut):
        self.dut = dut
        self.cycle = 0        # counts rising edges seen so far

    def read_pins(self, before_edge=False) -> PinSnapshot:
        """Read all pins now. A read taken before the edge does not start a
        new cycle; a read taken after the edge does."""
        dut = self.dut
        if not before_edge:
            self.cycle += 1

        empty = int(dut.empty.value)
        read_data_pin = dut.rd_data.value
        count_pin = dut.count.value

        count = int(count_pin) if count_pin.is_resolvable else UNKNOWN_COUNT
        head_is_visible = (not empty) and read_data_pin.is_resolvable
        read_data = int(read_data_pin) if head_is_visible else None

        return PinSnapshot(
            cycle=self.cycle,
            rst_n=int(dut.rst_n.value),
            wr_en=int(dut.wr_en.value),
            rd_en=int(dut.rd_en.value),
            wr_data=int(dut.wr_data.value),
            count=count,
            full=int(dut.full.value),
            empty=empty,
            rd_data=read_data,
        )
