"""Driver: turns one transaction into pin activity on the FIFO.

The driver only drives. It never checks anything, so a checking bug cannot
hide inside it.

Timing of one cycle:
  1. Wait for the falling edge, then put the new inputs on the pins.
  2. Optionally, 1 ns later, call the "before the edge" check. The inputs are
     already on the pins but no rising edge has happened yet, so the outputs
     must still show the old state (the second sample point).
  3. Wait for the rising edge, then 1 ns more, so the monitor reads settled
     outputs while this cycle's inputs are still held.

The driver also owns the clock. It is reused from the HW4 testbench, with
reset folded into `drive_one_cycle()` so a reset is just another transaction.
"""
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge, Timer

CLOCK_PERIOD_NS = 10
SETTLE_TIME_NS = 1


class FifoDriver:
    def __init__(self, dut, data_width, clock_period_ns=CLOCK_PERIOD_NS):
        self.dut = dut
        self.data_mask = (1 << data_width) - 1

        # Start in reset with every request low, then start the clock.
        dut.rst_n.value = 0
        dut.wr_en.value = 0
        dut.rd_en.value = 0
        dut.wr_data.value = 0
        cocotb.start_soon(Clock(dut.clk, clock_period_ns, units="ns").start())

    async def drive_one_cycle(self, write_enable, read_enable, write_data=0,
                              reset_n=1, check_before_edge=None):
        """Drive one clock cycle.

        `check_before_edge`, when given, runs 1 ns after the new inputs reach
        the pins and before the rising edge (the second sample point).
        """
        dut = self.dut

        await FallingEdge(dut.clk)
        dut.rst_n.value = reset_n
        dut.wr_en.value = write_enable
        dut.rd_en.value = read_enable
        dut.wr_data.value = write_data & self.data_mask

        if check_before_edge is not None:
            await Timer(SETTLE_TIME_NS, units="ns")
            check_before_edge()

        await RisingEdge(dut.clk)
        await Timer(SETTLE_TIME_NS, units="ns")
