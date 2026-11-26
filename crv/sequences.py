"""The constrained-random sequence: turns a profile into a stream of cycles.

Every cycle the sequence:
  1. reads the occupancy the DUT reports,
  2. decides the phase (FILL or DRAIN),
  3. hands both to the transaction and randomizes it,
  4. maybe turns the cycle into a reset,
  5. returns the cycle for the environment to drive.

Profiles (the convergence history; each one replays by name):
  v1  uniform transaction, no resets                          (the baseline)
  v2  boundary-shaped transaction (HW5), resets at a flat 1/400 per cycle,
      enables during reset taken from the shaped mix
  v3  v2, with the reset rate raised at the boundaries (1/40 at empty or
      full, 1/600 elsewhere). Closed reset-at-full, but OPENED new holes for
      reset at partial occupancy.
  v4  reset rate 1/30 at the boundaries and 1/120 elsewhere, and the enables
      on a reset cycle come from two unconstrained pyvsc bits (rst_wr,
      rst_rd), so all four enable pairs are equally likely during reset.
      This is the sign-off profile.

Resets are decided here, at the sequence layer, from the same seeded `random`
stream pyvsc uses, rather than as a pyvsc field: a guarded constraint on a
reset field fired at about 10x its intended rate (ai_log.md, entry 3), and an
unguarded dist cannot depend on the occupancy.

Order matters for reproducibility: the calls to random.random() and
randomize() below happen in the same order as in the original code, so every
seed still produces the same stimulus digest.
"""
import random

from crv.transactions import DRAIN, FILL, FifoTransaction, UniformFifoTransaction

PROFILES = ("v1", "v2", "v3", "v4")
PHASE_FLIP_CHANCE_AT_BOUNDARY = 0.05   # per cycle spent at the target boundary: mean dwell 20 cycles


def reset_probability(profile, count, depth):
    """Chance that this cycle becomes a reset, given the current occupancy."""
    at_a_boundary = count in (0, depth)
    if profile == "v1":
        return 0.0
    if profile == "v2":
        return 1.0 / 400
    if profile == "v3":
        return 1.0 / 40 if at_a_boundary else 1.0 / 600
    return 1.0 / 30 if at_a_boundary else 1.0 / 120


class ConstrainedRandomSequence:
    def __init__(self, profile, data_width, depth):
        assert profile in PROFILES, f"unknown profile {profile}"
        self.profile = profile
        self.data_width = data_width
        self.depth = depth
        transaction_class = UniformFifoTransaction if profile == "v1" else FifoTransaction
        self.transaction = transaction_class(data_width, depth)
        self.phase = FILL

    def _maybe_flip_phase(self, count):
        """Turn around once we have dwelt at the boundary we were heading to.
        The random draw only happens when we are AT that boundary (the `and`
        short-circuits), exactly as in the original code."""
        reached_full = self.phase == FILL and count >= self.depth
        reached_empty = self.phase == DRAIN and count == 0
        if reached_full and random.random() < PHASE_FLIP_CHANCE_AT_BOUNDARY:
            self.phase = DRAIN
        elif reached_empty and random.random() < PHASE_FLIP_CHANCE_AT_BOUNDARY:
            self.phase = FILL

    def next_cycle(self, count):
        """Return (reset_n, write_enable, read_enable, write_data) for the next
        cycle, given the occupancy the DUT reports now."""
        self._maybe_flip_phase(count)

        self.transaction.count = max(count, 0)
        self.transaction.phase = self.phase
        self.transaction.randomize()
        write_enable = int(self.transaction.wr_en)
        read_enable = int(self.transaction.rd_en)
        write_data = int(self.transaction.wr_data)

        make_this_a_reset = random.random() < reset_probability(self.profile, count, self.depth)
        if make_this_a_reset:
            self.phase = FILL
            if self.profile == "v4":
                write_enable = int(self.transaction.rst_wr)
                read_enable = int(self.transaction.rst_rd)
            return 0, write_enable, read_enable, write_data
        return 1, write_enable, read_enable, write_data


async def run_constrained_random(env, profile, cycles, on_cycle_done=None):
    """Drive `cycles` constrained-random cycles through the environment.

    `on_cycle_done(n)`, when given, is called after cycle n (1-based). The
    graduate study uses it to record coverage at its budget checkpoints.
    """
    sequence = ConstrainedRandomSequence(profile, env.data_width, env.depth)
    for cycle_number in range(1, cycles + 1):
        reset_n, write_enable, read_enable, write_data = sequence.next_cycle(env.last_pins.count)
        await env.step(write_enable, read_enable, write_data, reset_n)
        if on_cycle_done is not None:
            on_cycle_done(cycle_number)
    return sequence
