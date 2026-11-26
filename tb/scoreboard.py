"""Scoreboard: compares the FIFO against a reference queue on every cycle.

The reference queue is the course golden model (models.fifo_model.FifoModel,
a deque). Each cycle the scoreboard:
  1. steps the model with the inputs the MONITOR saw, using the state from
     before the edge (the same gating rule the spec gives: full blocks a
     write, empty blocks a read);
  2. compares count, full and empty, and, whenever the model holds data, the
     first-word-fall-through head against rd_data.

It does this at two sample points: after the edge, and again before the next
edge once the new inputs are on the pins (spec rule 3 says rd_data shows the
head "continuously", so it must not change until an edge happens).

The scoreboard also builds a CycleRecord for every checked cycle. The coverage
model and the stimulus self-checks read that record, so what gets counted as
covered is exactly what was just checked.
"""
from collections import Counter
from dataclasses import dataclass
from typing import Optional

from models.fifo_model import FifoModel


@dataclass
class CycleRecord:
    """Everything that happened on one checked clock edge."""
    rst_n: int
    wr_en: int
    rd_en: int
    wr_data: int
    occupancy_before: int
    occupancy_after: int
    write_happened: bool
    read_happened: bool
    write_pointer_wrapped: bool
    read_pointer_wrapped: bool
    popped_value: Optional[int]     # the word that left the FIFO (None if no pop)
    popped_from_slot: int           # the memory slot that word came from
    depth: int
    width: int


class FifoScoreboard:
    def __init__(self, data_width, depth, seed):
        self.model = FifoModel(data_width, depth)
        self.data_width = data_width
        self.depth = depth
        self.seed = seed

        # Shadow pointers. They feed coverage (wrap and slot bins) only and are
        # never compared against the DUT, because the spec does not expose them.
        self.write_slot = 0
        self.read_slot = 0

        # Stimulus bookkeeping for the self-checks and the run log.
        self.stimulus_events = Counter()       # e.g. "write_while_full" -> times seen
        self.occupancy_histogram = Counter()   # occupancy after the edge -> cycles

    # ------------------------------------------------------------------ checks
    def check_before_edge(self, pins):
        """Second sample point: the new inputs are on the pins, no edge yet.

        Nothing has been clocked, so every output must still match the model's
        current state. This catches outputs that react combinationally to
        wr_en, rd_en or wr_data.
        """
        model = self.model
        where = (f"seed {self.seed} before edge {pins.cycle + 1} "
                 f"(rst_n={pins.rst_n} wr_en={pins.wr_en} "
                 f"rd_en={pins.rd_en} wr_data=0x{pins.wr_data:x})")

        assert pins.count == model.count, f"{where}: count {pins.count} != model {model.count}"
        assert pins.full == int(model.full), f"{where}: full {pins.full} != model {int(model.full)}"
        assert pins.empty == int(model.empty), f"{where}: empty {pins.empty} != model {int(model.empty)}"
        if not model.empty:
            assert pins.rd_data == model.head, \
                f"{where}: rd_data {pins.rd_data} != model head 0x{model.head:x}"

        self.stimulus_events["pre_edge_checks"] += 1

    def check_after_edge(self, pins):
        """Main sample point: step the model by one edge, then compare."""
        model = self.model
        where = (f"seed {self.seed} cycle {pins.cycle} "
                 f"(rst_n={pins.rst_n} wr_en={pins.wr_en} "
                 f"rd_en={pins.rd_en} wr_data=0x{pins.wr_data:x})")

        occupancy_before = model.count
        write_happened = read_happened = False
        write_pointer_wrapped = read_pointer_wrapped = False
        popped_value = None
        popped_from_slot = self.read_slot

        if not pins.rst_n:
            model.reset()
            self.write_slot = 0
            self.read_slot = 0
        else:
            head_before_edge = model.head
            write_happened, read_happened = model.step(pins.wr_en, pins.wr_data, pins.rd_en)
            if read_happened:
                popped_value = head_before_edge
                self.read_slot = (self.read_slot + 1) % self.depth
                read_pointer_wrapped = (self.read_slot == 0)
            if write_happened:
                self.write_slot = (self.write_slot + 1) % self.depth
                write_pointer_wrapped = (self.write_slot == 0)

        record = CycleRecord(
            rst_n=pins.rst_n, wr_en=pins.wr_en, rd_en=pins.rd_en, wr_data=pins.wr_data,
            occupancy_before=occupancy_before, occupancy_after=model.count,
            write_happened=write_happened, read_happened=read_happened,
            write_pointer_wrapped=write_pointer_wrapped,
            read_pointer_wrapped=read_pointer_wrapped,
            popped_value=popped_value, popped_from_slot=popped_from_slot,
            depth=self.depth, width=self.data_width,
        )
        self._count_stimulus_events(record)

        # Compare all four outputs, every cycle.
        assert pins.count == model.count, f"{where}: count {pins.count} != model {model.count}"
        assert pins.full == int(model.full), f"{where}: full {pins.full} != model {int(model.full)}"
        assert pins.empty == int(model.empty), f"{where}: empty {pins.empty} != model {int(model.empty)}"
        if not model.empty:
            assert pins.rd_data is not None, f"{where}: rd_data is X/Z, model head 0x{model.head:x}"
            assert pins.rd_data == model.head, (
                f"{where}: rd_data 0x{pins.rd_data:x} != model head 0x{model.head:x} "
                f"(model queue {[hex(word) for word in model.q]})")
        return record

    # -------------------------------------------------------------- bookkeeping
    def _count_stimulus_events(self, record):
        """Tally the corner cases the stimulus reached. The CRV test fails if
        any of these stays at zero (a stimulus self-check)."""
        events = self.stimulus_events
        full_level = self.depth
        before = record.occupancy_before
        after = record.occupancy_after

        events["cycles_checked"] += 1
        self.occupancy_histogram[after] += 1

        if not record.rst_n:
            events["reset"] += 1
            events["reset_with_data"] += int(before > 0)
            events["reset_at_full"] += int(before == full_level)
            events["write_during_reset"] += int(bool(record.wr_en))
            return

        both_enables = record.wr_en and record.rd_en
        events["write_while_full"] += int(record.wr_en and before == full_level)
        events["read_while_empty"] += int(record.rd_en and before == 0)
        events["both_enables_at_full"] += int(both_enables and before == full_level)
        events["both_enables_at_empty"] += int(both_enables and before == 0)
        events["simultaneous_rw"] += int(record.write_happened and record.read_happened)
        events["wr_ptr_wrap"] += int(record.write_pointer_wrapped)
        events["rd_ptr_wrap"] += int(record.read_pointer_wrapped)
        events["writes"] += int(record.write_happened)
        events["reads"] += int(record.read_happened)
        events["full"] += int(after == full_level)
        events["empty"] += int(after == 0)
