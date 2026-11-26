# FINDINGS — Project 1, synchronous FWFT FIFO · Brandon Zabawa and Leo

> **AI disclosure:** AI was used to help finish this task.

> The number is the start of the argument, not the end of it. This file is
> where you say what the number means and what it does not cover.

**Suite:** `test_fifo_p1.py` (rewritten for readability in November; the stimulus digests of all 30 regression runs and both harness scores are unchanged): T1 directed smoke, T2 security reset race, T3 constrained-random sign-off (profile v4, seed 1, 2,500 cycles, coverage gate). All four outputs are checked every cycle at two sample points against the `FifoModel` reference queue. **Tools:** Icarus 12.0 (also green under Verilator 5.020), cocotb 1.9.2, pyvsc 0.9.5.27214109393, cocotb-coverage 1.2.0.

## Score

| Pool | found | total | % |
|------|------:|------:|--:|
| released (practice) | 8 | 8 | 100.0 |
| hidden (reported at grading) | pending | pending | pending |

**Command run:**

```bash
cd code/tb/fifo_p1
python -m craft_mutate.mutate --tb . --dut ../../dut/fifo.sv --pool mutants_released.yaml --sim icarus --json results/mutation/released.json
```

```text
[baseline] running clean fifo.sv through fifo_p1 ...
  clean RTL: 3 tests passed.

  [found  ] full_offbyone        (test-failed)  -- full asserts one entry too early (cnt == DEPTH-1)
  [found  ] empty_offbyone       (test-failed)  -- empty asserts one entry too early (cnt == 1)
  [found  ] ignore_full          (test-failed)  -- writes are accepted even when full (overflow)
  [found  ] ignore_empty         (test-failed)  -- reads are accepted even when empty (underflow)
  [found  ] count_wr_dec         (test-failed)  -- a write-only cycle decrements the count
  [found  ] rd_data_wrptr        (test-failed)  -- rd_data reads from the write pointer instead of the read pointer
  [found  ] mem_corrupt          (test-failed)  -- stored data is corrupted (+1) on write
  [found  ] wrptr_wrap_early     (test-failed)  -- write pointer wraps one slot early

==== found/total = 8/8  =  100.0%  (threshold 90%) ====
```

**Generalization check (not a course pool).** The released pool has no survivors, so we wrote 24 more one-line bugs in the harness YAML format (`mutation/mutants_stress.yaml`). They cover overlapping-enable traps, reset faults, pointer faults, boundary and flag faults, storage-cell faults, and three that we expected no spec-based checker could see. Same harness:

```text
python -m craft_mutate.mutate --tb . --dut ../../dut/fifo.sv --pool mutation/mutants_stress.yaml --sim icarus --json results/mutation/stress.json
...
  [SURVIVED] empty_bypass_leaks_input (passed)  -- while empty, rd_data shows wr_data (a live bypass of the input bus)
  [SURVIVED] empty_reads_zero     (passed)  -- while empty, rd_data is forced to zero instead of the stale slot
  [SURVIVED] full_from_pointers   (passed)  -- full derived from pointer equality plus a nonzero count (logically identical)
==== found/total = 21/24  =  87.5%  (threshold 90%) ====
```

**Is the score a lucky seed? (graduate extension Q2, Leo).** No. Over 20 seeds the whole suite scores 29/32 on every seed, at 100 CRV cycles and at 2,500, because T1 and T2 alone find 29 of 32 (every mutant any check against this spec can find). The CRV test alone spreads at 100 cycles (24–29 of 32, mean 27.80, 95% interval [27.05, 28.55]; seed 1 scores 28, the median) and agrees on every seed from 400 cycles on. Numbers: `extension/results/q2_table.md`.

## Survivors

One row per mutant your suite did not find. `Reachable?` is the important
column: a survivor you never reached is a *stimulus* problem, a survivor you
reached but did not notice is a *checking* problem, and they have different
fixes.

Final suite: no released survivors; three on our pool. The fourth row survived an earlier configuration of this same environment (CRV alone, profile v1) and shows the third kind of gap.

| Mutant | What it changes | Reachable by my stimulus? | Observable by my checks? | Why it survived |
|--------|-----------------|---------------------------|--------------------------|-----------------|
| `empty_bypass_leaks_input` | while `empty`, `rd_data` shows the live `wr_data` bus | yes (T3 seed 1 parks at empty for hundreds of cycles with `wr_data` random) | no | **observability, by the spec.** `rd_data` is defined only when `!empty`, so nothing compares it there |
| `empty_reads_zero` | while `empty`, `rd_data` is forced to 0 | yes | no | **observability, by the spec.** Same window. Arguably not a bug at all: it is a legal implementation of this spec |
| `full_from_pointers` | `full = (wr_ptr == rd_ptr) && (cnt != 0)` | yes | n/a | **equivalent.** Pointers are equal with `cnt != 0` exactly when `cnt == DEPTH`, so no input sequence tells it apart |
| `write_beats_reset` (CRV alone, profile v1, every budget up to 3,200 cycles, all 5 seeds) | reset is skipped on any cycle with `wr_en` high | **no** (v1 issues no mid-run reset, and the three opening reset cycles have `wr_en = 0`) | yes | **reachability.** Found in the final suite by T2 (`wr_en = rd_en = 1` on a reset edge) and by T3 under v4, which draws the enables of a reset cycle from two unconstrained pyvsc bits |

**What would catch each one:**

- `write_beats_reset`: any reset edge with `wr_en = 1`. The fix was a constraint (v4 resets with random enables at 1/30 per cycle at the boundaries and 1/120 elsewhere), not a test aimed at this mutant. The cross `fifo.rst_x_en` now has a bin for every (occupancy class, enables) pair, so a stimulus edit that stops producing this case shows up as a coverage hole and fails the gate.
- `empty_bypass_leaks_input`: a spec decision first. If `fifo.md` said "`rd_data` holds its last value while empty" or "is 0 while empty", a stability check (no change on `rd_data` while `empty` unless a write is accepted) would catch it within a few cycles, since our random `wr_data` toggles while parked at empty. As a security property it is an information-flow check: while empty, `rd_data` must not depend on same-cycle `wr_data`. That is the self-composition pattern of `dut/leak_check.sv`, which simulation can only spot-check and formal can prove.
- `empty_reads_zero`: under this spec, nothing should catch it. A check that failed on it would also fail on any legal design that chose a different empty-time value, which means the checker would be over-reading the spec. We list it so the hidden-pool number can be read correctly if a mutant like it appears there.
- `full_from_pointers`: no simulation can. The right evidence is a proof that `full == (cnt == DEPTH)` is an inductive invariant of the mutated design (`sby`, Week 8). That classifies it as equivalent and removes it from the denominator honestly.

## What I changed, and what it bought

| Change | Score before | Score after | Which survivors it caught |
|--------|-------------:|------------:|---------------------------|
| HW4 layering ported (driver / monitor / reference-queue scoreboard, all four outputs every cycle) under uniform CRV (v1) | starter 3/8 released | 8/8 released; 21/32 at 50 cycles, 28/32 from 200 cycles on (v1 seed 1, budget sweep) | `full_offbyone`, `ignore_full`, `rd_data_wrptr`, `mem_corrupt`, `wrptr_wrap_early` |
| Boundary-shaped pyvsc transaction (v2, kept in v4) | boundary-class mutants (own pool): median first failure at cycle 84 (v1, 5 seeds) | median cycle 17.5 (v4, 5 seeds) | none new; the boundary bugs fall about 4.8x earlier. Over all found mutants the medians are close (8 and 13), because most fail within a few cycles either way (`extension/results/q1_summary.json`, `median_detection_cycle`) |
| Reset events with random enables (v4), plus T2 security test | own pool 20/24 (`write_beats_reset` unreached by CRV) | 21/24 with the pre-edge check | `write_beats_reset` |
| Second sample point before the edge (spec rule 3: the head shows *continuously*) | own pool 20/24 (HW4 and HW5-first-cut suites) | 21/24 | `head_shows_input_on_simul_at_one` (visible only between edges) |
| Coverage gate + stimulus self-checks in T3 | — | gate fails the run below 100% | none directly; protects every find above from a silent stimulus regression |

## Residual risk

What this suite still cannot catch, stated plainly. Name a fault class, not a
mutant id — the pool is a sample, not the population.

1. **Any behavior of `rd_data` while the FIFO is empty** (**observability**, by the spec), including leaking the input bus or stale data. Closing it takes a spec change, then one stability check.
2. **Misreadings shared by the reference model and the RTL** (**observability**). `FifoModel` mirrors the RTL. A wrong reading of simultaneous r+w at a boundary would be wrong in both, and every compare would agree.
3. **Reset-path faults that need a rare alignment** (**reachability**), for example a reset on the exact edge a pointer wraps with a write racing it. v4 issues about 40 resets per 2,500-cycle run (exact chain: 0.0159 per cycle). Each such alignment is a small fraction of those, and no coverpoint names it.
4. **Parameter sets other than 8/8** (**reachability**). They elaborate and pass a smoke run (`DEPTH=5 WIDTH=4` closes 100% coverage on seed 1; `DEPTH=16 WIDTH=16` reaches 99.67%), but the hidden pool and our coverage closure are 8/8 only.
5. **Transients between the two sample points** (**observability**). We sample 1 ns after the inputs change and 1 ns after the edge.

**If I had another day:** write the three survivors' fix as an assertion bundle. That means one `rd_data`-stability property gated on a spec clarification we would ask for, plus an `sby` invariant proof that classifies `full_from_pointers` as equivalent. That converts two of the three survivors from "argued" to "measured".
