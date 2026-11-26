# Coverage closure — synchronous FWFT FIFO (`dut/fifo.sv`) · Brandon Zabawa and Leo

> **AI disclosure:** AI was used to help finish this task.

> Coverage is a measure of what you *looked at*, never of what is *correct*.
> A closed model with a weak checker reports 100% and proves nothing. This file
> is the argument that your number means something — and the honest list of
> what it still cannot mean.

## 1. The number

| | |
|---|---|
| Coverpoints closed | 10 / 10 (C1–C10, 175 bins), plus 4 / 4 illegal checks at zero hits |
| Cross `top.occ_x_op` closed | 20 / 20 bins (ours is named `fifo.occ_x_op`; also `fifo.wrap_x_occ` 8 / 8 and `fifo.rst_x_en` 12 / 12) |
| Target declared in my vplan | 100% |
| Reached | 100% on the sign-off seed (213 / 213 bins); 100% merged over seeds 1–10; 9 / 10 seeds alone |
| Vectors to closure | 975 cycles (seed 1, profile v4; measured at 25-cycle resolution, so between 951 and 975) |
| Vectors soaked past closure | 1,525 cycles, plus the end-of-test drain (the sign-off run is 2,500 cycles) |

**How the report was produced:**

```bash
# coverage_db.report_coverage(...) — also exports coverage.yml
make SIM=icarus                                   # T3 prints one COVER line per item + COVER TOTAL, and fails below 100%
python3 crv/regress.py                            # seeds 1-10: each run exports seed_<n>.yml via coverage_db.export_to_yaml,
                                                  # merged per profile into results/signoff/summary.md
python3 crv/regress.py --convergence              # profiles v1-v4 x seeds 1-5 -> results/convergence/summary.md
STUDY=1 SEED=1 PROFILE=v4 CHECKPOINTS=25,50,...,2500 STUDY_OUT=results/closure_curve/seed1_v4.json \
    make SIM=icarus TESTCASE=test_t3_crv_signoff  # the closure curve below
```

```text
 25733.00ns INFO     cocotb.fifo                        COVER fifo.march                        128/128  100.00%
 25733.00ns INFO     cocotb.fifo                        COVER fifo.occ_x_op                      20/20   100.00%
 25733.00ns INFO     cocotb.fifo                        COVER fifo.wrap_x_occ                     8/8    100.00%
 25733.00ns INFO     cocotb.fifo                        COVER fifo.rst_x_en                      12/12   100.00%
 25733.00ns INFO     cocotb.fifo                        COVER TOTAL 100.00%  holes={}
                                                        ** TESTS=3 PASS=3 FAIL=0 SKIP=0                          25733.00          19.72       1305.00  **
```

Full log: `results/clean_icarus.log`.

## 2. The convergence argument

**Shape of the curve:** seed 1, profile v4, total coverage (cross coverage in brackets): 86.4% (55.0%) at 100 cycles, 93.0% (70.0%) at 200, 97.2% (87.5%) at 400, 99.1% (95.0%) at 600, 99.5% (97.5%) at 800, 100% (100%) at 975. The single coverpoints and most of X1 close in the first 200 cycles, because the shaped walk crosses every occupancy on its first fill and drain. The remaining 3% is all crosses. Each of those bins needs two independent events to line up: a pointer at slot 7 *and* the FIFO at a boundary, or a reset *and* a particular occupancy class *and* a particular enable pair.

**The last bins to close, and what it took:**

| Bin | Why it was rare | What I changed to hit it |
|-----|-----------------|--------------------------|
| `fifo.rst_x_en (partial, *)` and `(full, rd)` | v1 never resets. v2 resets at 1/400 per cycle and reuses the shaped enables, so `rd`-only during a reset at full is about 10% of an already rare event. v3 raised the reset rate at the boundaries but starved partial occupancy (1/600 per cycle) and opened `(partial, none/wr/rd)` | **Constraint change, v4:** reset 1/30 per cycle at empty or full and 1/120 elsewhere, with the enables on a reset cycle from two unconstrained pyvsc bits (`rst_wr`, `rst_rd`), so all four pairs are equally likely. Last bin on seed 1: `(partial, wr)` at about cycle 975 |
| `fifo.rst_x_en` on seed 4 | same family. At 2,500 cycles seed 4 still lacks `(partial, both)` (99.53%) | nothing: at 4,000 cycles seed 4 closes (`results/seed4_budget/seed4_4000.log`, `COVER TOTAL 100.00%`), so this is budget, not reachability |
| `fifo.wrap_x_occ (rd_wrap, empty)`, `(wr_wrap, one)` | the read that empties the FIFO must come from slot 7, and the write into an empty FIFO must land in slot 7: about 1 drain or fill in 8 | nothing beyond the dwell already in v2: parking at each boundary for a mean of 20 cycles produces many fills and drains. Closed by about 800 cycles on seed 1 |
| `fifo.occ_x_op (empty, idle)` | the shaped mix idles at near-empty only 5% (FILL) to 15% (DRAIN) of draws | nothing: still reached by about 800 cycles. We kept the mix rather than add idle weight, because idle at empty finds nothing a read at empty does not |

The convergence history across profiles (`results/convergence/summary.md`, 2,500 cycles, seeds 1–5):

| Profile | What changed | Per-seed coverage | Merged | Holes left |
|---------|--------------|------------------:|-------:|------------|
| v1 | uniform transaction, no resets | 92.49% (all 5) | 92.49% | 11 of 12 `rst_x_en` bins, plus `rst_occ` partial/full and `rst_en` wr/rd/both |
| v2 | boundary-shaped transaction (HW5), resets 1/400 | 93.90–98.12% | 99.06% | `rst_x_en (empty, wr)`, `(empty, both)` |
| v3 | reset rate raised at the boundaries | 98.12–99.06% | 100% | none merged, but 0 / 5 seeds close alone |
| v4 | partial-occupancy resets restored, uniform enables during reset | 99.53–100% | 100% | 4 / 5 seeds close alone (seed 4: one bin, closed at 4,000 cycles) |

Every hole was closed by changing a constraint or the sequence's reset policy, never by a directed test aimed at a bin. The two directed tests (T1, T2) do not sample coverage, so they cannot close a bin.

**Why I stopped where I stopped:** The model closes at 975 cycles on the sign-off seed. We keep running to 2,500, then drain, for two reasons. (1) Closure is a property of the regression, not of one seed: 9 of 10 seeds close alone at 2,500, and the last one needs about 4,000. (2) A mutant is only found if its corruption reaches a checked output *after* the bin is ticked. A data fault written into a slot near the end of the run is compared only when that word reaches the head, which is what the soak and the final drain guarantee. The 1,525 soaked cycles add no coverage. What they buy is that every bin is revisited many times (seed 1 spends 757 of 2,505 checked cycles at empty or full), so a fault that needs a *second* visit to a state (a wrap after a reset, for example) is still exercised.

## 3. Bin justification

Every `illegal` and `ignore` bin is a claim about the design. Each one needs an
authority — a line of `dut/specs/fifo.md`, or an argument you would defend.

| Bin | illegal / ignore | The claim | Authority (spec line, or the argument) |
|-----|------------------|-----------|----------------------------------------|
| `fifo.wrap_x_occ (rd_wrap, full)` | ignore | a read-pointer wrap can never leave the FIFO full | rule 3: an accepted read lowers `count`; rule 4: a true r+w needs `!full`; rule 2: at `full` an r+w is read-only. No read edge ends at `count == DEPTH` |
| `fifo.wrap_x_occ (wr_wrap, empty)` | ignore | a write-pointer wrap can never leave the FIFO empty | rules 2 and 4: an accepted write raises `count` or, in a true r+w, leaves it at ≥ 1 |
| I1 `fifo.illegal.I1_count_delta` | illegal | `count` changes by exactly +1 (write accepted), −1 (read accepted) or 0 (neither, or a true r+w) | rules 2–4 |
| I2 `fifo.illegal.I2_full_and_empty` | illegal | `full` and `empty` are never both 1 | rule 5, with `DEPTH ≥ 1` |
| I3 `fifo.illegal.I3_double_wrap` | illegal | both pointers never wrap on the same edge | pointers are equal only at empty or full, where rules 2–3 make a true r+w impossible, so a same-edge double wrap needs an illegal state |
| I4 `fifo.illegal.I4_range` | illegal | occupancy stays in 0..`DEPTH` | Ports table: `count` is 0..`DEPTH` |

**Corner bins that are legal and must be covered, not excluded:**

`fifo.occ_x_op (full, write)` (write dropped, rule 2), `(empty, read)` (read ignored, rule 3), `(full, simul)` (read only) and `(empty, simul)` (write only). All four are legal, spec-defined behavior and all four are ordinary bins of X1. `fifo.outcome` also gives `drop_write`, `ignore_read`, `simul_drop_write` and `simul_ignore_read` their own bins, so "the request was made" and "the spec's drop/ignore happened" are separate observations. Nothing in `vplan.md` section 3 moves a spec-permitted behavior into `ignore`.

## 4. What the cross is aimed at

A cross earns its place only if the interaction is where a bug would hide.

**The bug `top.occ_x_op` is aimed at:** gating that is wrong at one occupancy only. Examples: `ignore_full` (a write accepted at full, bin `(full, write)`); `write_when_full_if_reading` (a write sneaks in at full because a read frees a slot on the same edge, bin `(full, simul)`, our stress pool); `read_when_empty_if_writing` (bin `(empty, simul)`); `full_offbyone` (needs `(almost_full, write)` followed by a write at the falsely full state). Each of these can only fail on an edge from the bin named, so a hole there means the bug is unreachable.

**A bug it would *not* see, even fully closed:** `head_shows_input_on_simul_at_one`. Bin `(one, simul)` is hit hundreds of times, but at the post-edge sample the mutant's `rd_data` equals the true head. Only the second, pre-edge sample point sees it. Likewise `mem_corrupt` or a stuck cell: X1 is about control, so it is closed whether or not the data was right. That is the scoreboard's job, and C10 (the march) only proves the data *passed through* each cell.

## 5. Coverage vs. correctness — the blind spots

My model is closed and my suite is green. That still establishes nothing about:

1. **`rd_data` while the FIFO is empty.** No bin samples it and no check compares it, because the spec defines the head only when `!empty`. Two stress mutants (`empty_bypass_leaks_input`, `empty_reads_zero`) close every bin and survive. A spec clarification plus one stability check would fix it.
2. **Behavior between our two sample points.** Coverage is sampled once per cycle from the model's prediction, and checks run 1 ns after the input change and 1 ns after the edge. Every bin is about end-of-edge state, so a glitch at any other instant ticks the same bins.
3. **Sequences longer than one cycle.** Every bin is one edge (plus pre and post occupancy). "Reset on the same edge a pointer wraps with a write racing it" or "the 9th write after a reset" are not bins, so a fault that needs one can hide under 100%.
4. **Whether the model is right.** Bins are sampled from `FifoModel`'s prediction. If the model and the RTL share a misreading (say, of r+w at full), the bin is ticked by the same wrong behavior that passes the check.
5. **Parameters other than 8/8.** Closure is measured on `WIDTH = DEPTH = 8` only.

**Transients in particular:** an output that glitches and returns to the right value before the post-edge sample ticks the right bins and passes the end-of-edge check. Our model would not see that. The pre-edge sample catches one class (outputs that react combinationally to the *current* inputs, which is how `head_shows_input_on_simul_at_one` was found), but a glitch elsewhere in the cycle needs a cycle-accurate trace check or an SVA property on every simulation step, not more coverage.

## 6. Correlation with mutation

Cross-reference `FINDINGS.md`. The interesting case is divergence.

| | found / total |
|---|---|
| Before closing holes | v1 (uniform, no resets; reset cross stalled at 1 / 12, total 92.49%): released 8 / 8, own pool 20 / 24 at 3,200 cycles on each of the 5 seeds (budget sweep in `extension/data/`). Survivors: `write_beats_reset` + the 3 unfindable |
| After closing holes | v4 (100%): released 8 / 8, own pool 21 / 24 (the 3 unfindable remain) |

**Did closing holes raise the score?**

- If **yes** — which survivor did which bin catch?
- If **no** — you have found a mutant the coverage model cannot see. Name it,
  and say whether the gap is *reachability* (stimulus never creates the state)
  or *observability* (the corruption never reaches a checked output).

**Yes, by one, and the bin that did it is named:** closing `fifo.rst_x_en (*, wr)` and `(*, both)` (a write asserted during reset) is what finds `write_beats_reset`. v1 never creates that state (**reachability**). **And no, for three:** `empty_bypass_leaks_input` and `empty_reads_zero` are reached on every seed and never observed (**observability**: no check on `rd_data` while empty). `full_from_pointers` is equivalent. The other 28 mutants are found by both profiles, so for them closure changed only *how early* they fall. The budget sweep in `extension/` measures that directly, across 5 seeds and 7 budgets per profile.

---

- [x] Every `illegal` and `ignore` bin in section 3 cites an authority.
- [x] Section 5 names blind spots of this design, not of coverage in general.
- [x] The numbers here agree with `coverage.yml` and `FINDINGS.md`.
