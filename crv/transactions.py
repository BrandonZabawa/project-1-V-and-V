"""pyvsc transactions: one random FIFO operation per clock cycle.

FifoTransaction (profiles v2-v4) is the boundary-shaped transaction carried
over from our HW5 suite. wr_en, rd_en and wr_data are random. Two fields are
NOT random; the sequence sets them before every randomize():
  * count : the occupancy the DUT reports right now
  * phase : FILL (heading toward full) or DRAIN (heading toward empty)

UniformFifoTransaction (profile v1) is the unshaped baseline.

Legality
--------
Every (wr_en, rd_en) pair is legal at every occupancy (spec rules 2 and 3: a
write while full is dropped, a read while empty is ignored), and wr_data may
be any WIDTH-bit value. So legality needs no constraint, and no constraint
here can produce an illegal transaction. The constraints only SHAPE.

Two pyvsc behaviors we measured (pyvsc 0.9.5.27214109393, see ai_log.md)
decide how the shaping is written:
  1. A vsc.dist nested under if_then / else_if / else_then (or implies) is
     applied unconditionally, so branch-local distributions average out.
  2. A plain bounded field (roll < 20, or a rangelist) is not uniform: the
     solver over-weights values near the bounds. An unguarded dist with equal
     weights IS uniform.
So: one unguarded uniform dist on `roll`, one unguarded dist on wr_data, and
hard implications (which pyvsc does gate correctly) for the shaping.

Note on names: pyvsc may visit constraint blocks in name order. The three
block names below keep the same order as the originals, so the stimulus (and
its digest) is unchanged by the rename.
"""
import vsc

FILL, DRAIN = 0, 1
ROLL_RANGE = 20          # roll is uniform over 0..19, so each step is 5%

# Operation mix per (occupancy region, phase), counted out of ROLL_RANGE:
#   (write-only, both, read-only); idle takes whatever is left.
OPERATION_MIX = {
    ("near_empty", FILL):  (12, 5, 2),    # push writes away from empty
    ("near_empty", DRAIN): (2, 4, 11),    # park at empty: read while empty, r+w at empty
    ("mid", FILL):         (8, 9, 2),     # both enables 45%, drift up
    ("mid", DRAIN):        (2, 9, 8),     # both enables 45%, drift down
    ("near_full", DRAIN):  (2, 5, 12),    # push reads away from full
    ("near_full", FILL):   (11, 4, 2),    # park at full: write while full, r+w at full
}


def occupancy_region(count, depth):
    if count <= 1:
        return "near_empty"
    if count >= depth - 1:
        return "near_full"
    return "mid"


def data_corner_values(data_width):
    """The four data patterns we always want stored: 0x00, 0xFF, 0x55, 0xAA."""
    all_ones = (1 << data_width) - 1
    alternating_01 = int("01" * data_width, 2) & all_ones
    alternating_10 = alternating_01 ^ all_ones
    return [0, all_ones, alternating_01, alternating_10]


@vsc.randobj
class FifoTransaction:
    def __init__(self, data_width=8, depth=8):
        self.data_width = data_width
        self.depth = depth

        # Random fields. Keep this declaration order: it fixes the solver's
        # variable order and therefore the exact stimulus for each seed.
        self.wr_en = vsc.rand_bit_t(1)
        self.rd_en = vsc.rand_bit_t(1)
        self.wr_data = vsc.rand_bit_t(data_width)
        self.roll = vsc.rand_uint8_t()
        self.rst_wr = vsc.rand_bit_t(1)   # write enable to use IF the sequence makes this a reset cycle
        self.rst_rd = vsc.rand_bit_t(1)   # read enable to use IF the sequence makes this a reset cycle

        # Not random: the sequence writes these before every randomize().
        self.count = vsc.uint32_t(0)
        self.phase = vsc.uint8_t(FILL)

    def _apply_operation_mix(self, region_and_phase):
        """Map the uniform roll onto write-only / both / read-only / idle."""
        write_only, both, read_only = OPERATION_MIX[region_and_phase]
        with vsc.if_then(self.roll < write_only):
            self.wr_en == 1
            self.rd_en == 0
        with vsc.else_if(self.roll < write_only + both):
            self.wr_en == 1
            self.rd_en == 1
        with vsc.else_if(self.roll < write_only + both + read_only):
            self.wr_en == 0
            self.rd_en == 1
        with vsc.else_then:
            self.wr_en == 0
            self.rd_en == 0

    @vsc.constraint
    def roll_is_uniform(self):
        vsc.dist(self.roll, [vsc.weight(value, 1) for value in range(ROLL_RANGE)])

    @vsc.constraint
    def data_mix(self):
        zero, all_ones, alternating_01, alternating_10 = data_corner_values(self.data_width)
        vsc.dist(self.wr_data, [vsc.weight(zero, 10), vsc.weight(all_ones, 10),
                                vsc.weight(alternating_01, 10), vsc.weight(alternating_10, 10),
                                vsc.weight(vsc.rng(1, all_ones - 1), 60)])

    @vsc.constraint
    def shape_operation_by_occupancy(self):
        with vsc.if_then(self.count <= 1):
            with vsc.if_then(self.phase == FILL):
                self._apply_operation_mix(("near_empty", FILL))
            with vsc.else_then:
                self._apply_operation_mix(("near_empty", DRAIN))
        with vsc.else_if(self.count >= self.depth - 1):
            with vsc.if_then(self.phase == DRAIN):
                self._apply_operation_mix(("near_full", DRAIN))
            with vsc.else_then:
                self._apply_operation_mix(("near_full", FILL))
        with vsc.else_then:
            with vsc.if_then(self.phase == FILL):
                self._apply_operation_mix(("mid", FILL))
            with vsc.else_then:
                self._apply_operation_mix(("mid", DRAIN))


@vsc.randobj
class UniformFifoTransaction:
    """Profile v1: the starter's unshaped transaction (the baseline)."""

    def __init__(self, data_width=8, depth=8):
        self.data_width = data_width
        self.depth = depth
        self.wr_en = vsc.rand_bit_t(1)
        self.rd_en = vsc.rand_bit_t(1)
        self.wr_data = vsc.rand_bit_t(data_width)
        self.count = vsc.uint32_t(0)
        self.phase = vsc.uint8_t(FILL)
