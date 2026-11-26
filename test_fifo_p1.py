"""Project 1: constrained-random verification of the synchronous FWFT FIFO.

AI disclosure: AI was used to help finish this task.

The three cocotb tests below are the whole suite. The layers they use live in
tb/ (driver, monitor, scoreboard, environment), crv/ (pyvsc transactions,
sequences, seeded regression) and coverage_model/ (functional coverage).
vplan.md traces each test to the spec.

  T1 test_t1_directed_smoke       fixed vectors: reset, read while empty, fill,
                                  write while full, drain in order, r+w at empty,
                                  mid and full
  T2 test_t2_security_reset_race  security thread: a write and a read asserted
                                  DURING reset with data inside; reset must win
  T3 test_t3_crv_signoff          pyvsc stimulus (profile v4), coverage sampled
                                  every cycle, stimulus and coverage gates

Every test checks count, full, empty and the FWFT head against the reference
queue on every cycle, at two sample points.

Environment knobs (all optional; the defaults are the graded configuration):
  SEED=1  PROFILE=v4  CYCLES=2500  COV_GATE=1  COV_OUT=<file.yml>
  STUDY=1 STUDY_OUT=<file.json> CHECKPOINTS=100,200,...
      Graduate-study mode: no final drain and no gates. It records coverage at
      each checkpoint and the CRV cycle of the first failing check, so a run
      with budget B is an exact prefix of a longer run with the same seed.
"""
import json
import os
import random

import cocotb

from coverage_model import model as coverage
from crv.sequences import run_constrained_random
from tb.env import FifoEnv

DATA_WIDTH = int(os.environ.get("FIFO_WIDTH", "8"))
DEPTH = int(os.environ.get("FIFO_DEPTH", "8"))
SEED = int(os.environ.get("SEED", "1"))
PROFILE = os.environ.get("PROFILE", "v4")
CYCLES = int(os.environ.get("CYCLES", "2500"))
COVERAGE_GATE_ON = os.environ.get("COV_GATE", "1") == "1"
COVERAGE_EXPORT_FILE = os.environ.get("COV_OUT", "")
STUDY_MODE = os.environ.get("STUDY", "0") == "1"
STUDY_OUTPUT_FILE = os.environ.get("STUDY_OUT", "")
STUDY_CHECKPOINTS = sorted(int(text) for text in os.environ.get("CHECKPOINTS", "").split(",")
                           if text.strip())

DATA_MASK = (1 << DATA_WIDTH) - 1
RESET_CYCLES = 3

# Corner cases the constrained-random stimulus must reach on every run. If one
# of these stays at zero, a mutant could silently stop being exercised, so the
# test fails instead of passing quietly.
REQUIRED_STIMULUS_EVENTS = (
    "write_while_full", "read_while_empty", "both_enables_at_full", "both_enables_at_empty",
    "simultaneous_rw", "wr_ptr_wrap", "rd_ptr_wrap", "reset_with_data", "write_during_reset",
)


def distinct_tags(first_value, how_many):
    """Consecutive data values, so every stored word is unique and traceable."""
    return [(first_value + offset) & DATA_MASK for offset in range(how_many)]


# =============================================================================
# T1: directed smoke (a seed-independent floor under the random suite)
# =============================================================================
@cocotb.test()
async def test_t1_directed_smoke(dut):
    """Features F1-F9 at fixed vectors, so the basic contract is checked on
    every run no matter which seed the constrained-random test uses."""
    env = FifoEnv(dut, DATA_WIDTH, DEPTH)
    await env.reset()

    for _ in range(2):                                    # read while empty: ignored
        await env.step(0, 1)
    for value in distinct_tags(0xA0, DEPTH):              # fill with unique tags
        await env.step(1, 0, value)
    assert int(dut.full.value) == 1

    await env.step(1, 0, 0x5E)                            # write while full: dropped
    await env.step(1, 1, 0x5F)                            # r+w at full: only the read happens
    await env.step(1, 1, 0x61)                            # r+w at DEPTH-1: both happen
    for _ in range(DEPTH):                                # drain, checking order
        await env.step(0, 1)
    await env.step(1, 1, 0x71)                            # r+w at empty: only the write happens
    for offset in range(2 * DEPTH + 1):                   # streaming r+w across the pointer wrap
        await env.step(1, 1, 0x80 + offset)
    await env.drain()


# =============================================================================
# T2: security and trust thread (enables asserted during reset)
# =============================================================================
@cocotb.test()
async def test_t2_security_reset_race(dut):
    """Spec rule 1 says reset clears the FIFO. It says nothing about a write or
    a read asserted on the same edge. That undefined control combination is
    where a write-beats-reset or stale-data-survives bug hides. Reset must win:
    count 0, empty, and the marker written during reset must never appear at
    the head afterwards."""
    env = FifoEnv(dut, DATA_WIDTH, DEPTH)
    await env.reset()

    for value in distinct_tags(0x30, 5):
        await env.step(1, 0, value)
    for _ in range(2):
        await env.step(0, 1)                              # now wr_ptr=5, rd_ptr=2, count=3

    marker = 0xE & DATA_MASK if DATA_WIDTH < 8 else 0xEE
    await env.step(1, 1, marker, reset_n=0)               # write AND read during reset
    assert int(dut.count.value) == 0 and int(dut.empty.value) == 1, \
        "reset lost to a same-edge write/read"

    first_after_reset = 0x41 & DATA_MASK
    await env.step(1, 1, first_after_reset)               # r+w racing at the empty boundary
    assert int(dut.count.value) == 1 and int(dut.rd_data.value) == first_after_reset, \
        "after reset the head must be the first post-reset write, not stale data"

    for value in distinct_tags(0x50, DEPTH):              # full again, from clean pointers
        await env.step(1, 0, value)
    await env.step(1, 0, marker, reset_n=0)               # reset at full with a write asserted
    assert int(dut.count.value) == 0 and int(dut.full.value) == 0

    await env.step(1, 0, 0x42)
    await env.drain()


# =============================================================================
# T3: constrained-random sign-off run (the coverage-closing test)
# =============================================================================
@cocotb.test()
async def test_t3_crv_signoff(dut):
    random.seed(SEED)                                     # one seed fixes the whole trace
    sample_coverage = coverage.build(DEPTH, DATA_WIDTH)
    env = FifoEnv(dut, DATA_WIDTH, DEPTH, seed=SEED, coverage_sampler=sample_coverage)

    coverage_curve = []
    first_failure = None

    def record_checkpoint(cycle_number):
        coverage_curve.append({"cycles": cycle_number,
                               "coverage": round(coverage.total_percent(), 3),
                               "cross": round(coverage.cross_percent(), 3),
                               "each_cross": coverage.percent_of_each_cross()})

    def record_at_study_checkpoints(cycle_number):
        if cycle_number in STUDY_CHECKPOINTS:
            record_checkpoint(cycle_number)

    try:
        await env.reset(cycles=RESET_CYCLES)
        if STUDY_MODE:
            # No final drain here, so a budget-B run is an exact prefix of any
            # longer run with the same seed.
            study_budget = STUDY_CHECKPOINTS[-1] if STUDY_CHECKPOINTS else CYCLES
            await run_constrained_random(env, PROFILE, study_budget,
                                         on_cycle_done=record_at_study_checkpoints)
        else:
            await run_constrained_random(env, PROFILE, CYCLES)
            await env.drain()
    except Exception as failure:
        # Any exception fails the test, not only a failed check: an output
        # stuck at X raises ValueError when it is read as a number, and the
        # harness counts that as found too. Convert it into a CRV cycle number.
        # The reset cycles come first; a before-the-edge failure belongs to the
        # cycle about to be clocked; a failure during the opening reset is cycle 0.
        failed_before_edge = "before edge" in str(failure)
        crv_cycle = env.monitor.cycle - RESET_CYCLES + (1 if failed_before_edge else 0)
        first_failure = {"cycle": max(crv_cycle, 0),
                         "msg": f"{type(failure).__name__}: {failure}"[:300]}
        raise
    finally:
        if STUDY_MODE and STUDY_OUTPUT_FILE:
            with open(STUDY_OUTPUT_FILE, "w") as study_file:
                json.dump({"seed": SEED, "profile": PROFILE, "fail": first_failure,
                           "curve": coverage_curve}, study_file, indent=1)

    # ---- run log (crv/regress.py parses these lines) ----
    events = env.scoreboard.stimulus_events
    occupancy = env.scoreboard.occupancy_histogram
    total_cycles = sum(occupancy.values())
    dut._log.info(f"SEED {SEED} PROFILE {PROFILE} CYCLES {CYCLES} "
                  f"checked={events['cycles_checked']} pre_edge={events['pre_edge_checks']} "
                  f"digest={env.stimulus_digest.hexdigest()[:16]}")
    dut._log.info("OCC  " + " ".join(f"{level}:{occupancy[level]}" for level in range(DEPTH + 1)) +
                  f"   empty {occupancy[0] / total_cycles:.3f} full {occupancy[DEPTH] / total_cycles:.3f}")
    for name, covered, size, percent in coverage.summary():
        dut._log.info(f"COVER {name:32s} {covered:4d}/{size:<4d} {percent:6.2f}%")
    total_coverage = coverage.total_percent()
    dut._log.info(f"COVER TOTAL {total_coverage:.2f}%  holes={coverage.holes()}")

    if COVERAGE_EXPORT_FILE:
        coverage.coverage_db.export_to_yaml(filename=COVERAGE_EXPORT_FILE)
    if STUDY_MODE:
        return

    # ---- gates ----
    never_reached = [event for event in REQUIRED_STIMULUS_EVENTS if events[event] == 0]
    never_reached += [f"occ={level}" for level in range(DEPTH + 1) if occupancy[level] == 0]
    assert not never_reached, f"seed {SEED}: stimulus never reached {never_reached}"

    is_graded_configuration = PROFILE == "v4" and (DATA_WIDTH, DEPTH) == (8, 8)
    if COVERAGE_GATE_ON and is_graded_configuration:
        assert total_coverage >= 100.0, \
            f"seed {SEED}: coverage {total_coverage:.2f}% < 100% target, holes {coverage.holes()}"
