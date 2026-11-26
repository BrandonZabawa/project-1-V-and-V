# AI log — Project 1 (Check the Machine) · synchronous FWFT FIFO

> **AI disclosure:** AI was used to help finish this task.

Structure follows `templates/ctm.md` (predict, run, compare), as `templates/INDEX.md` suggests for `ai_log.md`.

**Assistant used:** a general-purpose frontier AI coding agent, tool-using (it can run Icarus and cocotb before answering), October 2026.

**Prompt (verbatim, the request that started the session):**

```text
Need you to do and answer all sections of each PDF especially the Graduate extension sections, mention that I used AI as a disclosure at the beginning, and ensure if any code needs updates or formatting that you keep it exactly as how the templates sections looks, and even run tests yourself using any simulators because that's what we're doing. Everything wise for information or code needing to look or add into should be referenced inside the zip file. Please make sure this is done accurately so that I don't need to worry about it, and also make sure for the project section to make the deliverables meet the standard he wants as outlined in the project 1 pdf, but is completable within a short time period.
```

Attached with it: the student packet (`craft-vv-student`, rev 8b9d934), the Project 1 PDF, the HW5 PDF and the Graduate Study PDF. The packet's own Week 5 demo (`demos/wk05-s2-constraints/DEMO.md`) was part of the context and is why prediction 1 exists.

---

## Entry 1 — the constraint block: branch-local `vsc.dist` under `if_then`

**Task.** Draft the occupancy-biased constraint: writes pushed near-empty, reads pushed near-full, both enables mid-range, built with `vsc.if_then / else_if / else_then` and `vsc.dist` (the HW5 handout's wording).

**Generated block (first draft, unedited):**

```python
with vsc.if_then(self.count <= 1):
    vsc.dist(self.wr_en, [vsc.weight(1, 90), vsc.weight(0, 10)])
    vsc.dist(self.rd_en, [vsc.weight(0, 80), vsc.weight(1, 20)])
with vsc.else_if(self.count >= 7):
    vsc.dist(self.wr_en, [vsc.weight(0, 80), vsc.weight(1, 20)])
    vsc.dist(self.rd_en, [vsc.weight(1, 90), vsc.weight(0, 10)])
with vsc.else_then:
    vsc.dist(self.wr_en, [vsc.weight(1, 80), vsc.weight(0, 20)])
    vsc.dist(self.rd_en, [vsc.weight(1, 80), vsc.weight(0, 20)])
```

**Prediction (before the run).** The packet's Week 5 demo shows `dist` ignoring an enclosing `implies` in the pinned pyvsc. `if_then` is a different construct, but if it lowers to the same guarded-constraint machinery, all three branch-local dists will apply on every draw and average out. *Evidence that would show it:* the measured P(wr_en) is the same in all three regions, near the mean of 0.90, 0.20 and 0.80 (≈ 0.63), instead of 0.90 / 0.20 / 0.80.

**Run.** `python3 results/ai_probes/dist_probe.py` (600 draws per region, seed 1, pyvsc 0.9.5.27214109393). Columns: count, P(wr_en), P(rd_en):

```text
0 0.64 0.6566666666666666
4 0.6616666666666666 0.6366666666666667
8 0.63 0.67
```

**Verdict: confirmed.** `dist` is not gated by `if_then` either. The draft solves cleanly, every transaction is legal, and it shapes nothing.

**Fix.** One uniform draw `roll` and hard implications per branch (`_mix()` in `crv/transactions.py`). Hard constraints under `if_then` *are* gated (entry 2 measures it). `vsc.dist` stays only where it is unguarded: on `roll` itself and on `wr_data` corners.

---

## Entry 2 — the uniform draw: `rangelist` vs `dist`

**Prediction (before the run).** A bounded random field (`roll in rangelist(0..99)`) is uniform, so the region mixes come out at their written percentages. *Evidence:* the 10 deciles of `roll` each hold about 10% over 3,000 draws, and the near-empty FILL mix (60/25/10/5) measures close to that.

**Run.** `python3 results/ai_probes/txn_probe.py`, seed 1. Rows: count, phase (0 = FILL), induced (wr_en, rd_en) rates over 1,000 draws, cost; then wr_data classes; then `roll` deciles over 3,000 draws:

```text
0 0 {'(0, 0)': 0.136, '(0, 1)': 0.169, '(1, 0)': 0.431, '(1, 1)': 0.264} 6.26 ms/draw
0 1 {'(0, 0)': 0.209, '(0, 1)': 0.392, '(1, 0)': 0.172, '(1, 1)': 0.227} 6.54 ms/draw
4 0 {'(0, 0)': 0.154, '(0, 1)': 0.183, '(1, 0)': 0.341, '(1, 1)': 0.322} 6.14 ms/draw
4 1 {'(0, 0)': 0.132, '(0, 1)': 0.36, '(1, 0)': 0.157, '(1, 1)': 0.351} 6.32 ms/draw
8 0 {'(0, 0)': 0.183, '(0, 1)': 0.164, '(1, 0)': 0.396, '(1, 1)': 0.257} 6.25 ms/draw
8 1 {'(0, 0)': 0.124, '(0, 1)': 0.429, '(1, 0)': 0.173, '(1, 1)': 0.274} 6.29 ms/draw
Counter({'other': 1183, '00': 219, 'AA': 207, '55': 196, 'FF': 195})
[(0, 550), (1, 308), (2, 283), (3, 343), (4, 180), (5, 195), (6, 218), (7, 217), (8, 239), (9, 467)]
```

The first row was written as 0.05 / 0.10 / 0.60 / 0.25 (idle / read-only / write-only / both) and measured 0.136 / 0.169 / 0.431 / 0.264.

**Verdict: refuted.** The solver over-weights values near the bounds (decile 0 holds 18%, decile 9 holds 16%), so every mix is skewed toward its first and last ranges.

**Fix.** `roll` takes 20 values with an unguarded `vsc.dist` of equal weights. A 100-weight dist was too slow (the probe did not finish in 120 s); 20 weights keeps 5% resolution. Re-measured (`python3 results/ai_probes/txn_probe3.py`, same row format; last line is the 20 `roll` buckets over 3,000 draws, 150 expected each):

```text
0 0 {'(0, 0)': 0.058, '(0, 1)': 0.107, '(1, 0)': 0.624, '(1, 1)': 0.211} 6.43 ms/draw
0 1 {'(0, 0)': 0.147, '(0, 1)': 0.564, '(1, 0)': 0.091, '(1, 1)': 0.198} 6.60 ms/draw
4 0 {'(0, 0)': 0.059, '(0, 1)': 0.084, '(1, 0)': 0.408, '(1, 1)': 0.449} 6.71 ms/draw
4 1 {'(0, 0)': 0.056, '(0, 1)': 0.395, '(1, 0)': 0.107, '(1, 1)': 0.442} 6.64 ms/draw
8 0 {'(0, 0)': 0.146, '(0, 1)': 0.085, '(1, 0)': 0.558, '(1, 1)': 0.211} 6.69 ms/draw
8 1 {'(0, 0)': 0.043, '(0, 1)': 0.604, '(1, 0)': 0.096, '(1, 1)': 0.257} 6.73 ms/draw
Counter({'other': 1180, '00': 214, 'AA': 210, 'FF': 201, '55': 195})
[(0, 147), (1, 121), (2, 155), (3, 152), (4, 142), (5, 166), (6, 147), (7, 146), (8, 143), (9, 142), (10, 171), (11, 155), (12, 160), (13, 154), (14, 151), (15, 145), (16, 156), (17, 134), (18, 175), (19, 138)]
```

Written mixes for those rows (idle / read-only / write-only / both): 0.05/0.10/0.60/0.25, 0.15/0.55/0.10/0.20, 0.05/0.10/0.40/0.45, 0.05/0.40/0.10/0.45, 0.15/0.10/0.55/0.20, 0.05/0.60/0.10/0.25. All within 0.03.

Cost: 6.3–6.7 ms per `randomize()` with the shaping constraints, against 0.08 ms for the unconstrained transaction. That cost sets our cycle budgets (2,500 cycles ≈ 19 s per run).

---

## Entry 3 — resets as a pyvsc field

**Generated block:**

```python
with vsc.if_then((self.count == 0) | (self.count == self.depth)):
    self.rst == (self.rroll < 2)          # intended 2/128 = 1.6% at the boundaries
with vsc.else_then:
    self.rst == (self.rroll < 1)          # intended 0.8% elsewhere
```

**Prediction (before the run).** Given entry 2, the guard field `rroll` will be pulled toward its bound and `rst` will fire far more often than intended. *Evidence:* P(rst) well above 0.016 / 0.008.

**Run.** `python3 results/ai_probes/rst_probe.py`, 4,000 draws per occupancy. Columns: count, P(rst), cost:

```text
0 0.1605 1.1137531995773315 ms
4 0.1285 1.1159765124320984 ms
8 0.15775 1.1106454133987427 ms
```

**Verdict: confirmed, and worse than predicted** (10x to 16x the intended rate). A run that resets every 7 cycles never fills the FIFO.

**Fix.** Reset events are decided at the sequence layer (`crv/sequences.py`, `reset_probability()`), from the same seeded `random` stream pyvsc uses, so reproducibility is unchanged. The pyvsc transaction keeps two *unconstrained* bits, `rst_wr` and `rst_rd`, that supply the enables on a reset cycle (profile v4).

---

## Entry 4 — the coverage model draft

**Task.** Draft the cocotb-coverage model of `vplan.md` section 3: coverpoints, the occupancy × operation cross, ignore bins, illegal bins.

**Predictions (before the run).**
1. The draft will put `(full, write)` and `(empty, read)` in ignore bins, because they "do nothing". *Evidence:* an `ign_bins` entry on `fifo.occ_x_op`. That would hide two corners the spec defines.
2. The (slot, bit, value) march coverpoint will be mis-built, because cocotb-coverage samples one value per call and a popped word carries eight bits. *Evidence:* fewer than 128 bins reachable, or two items with one name.

**Run.** Review, then `make SIM=icarus` on the first draft.

**Verdict.** 1 refuted: the cross had no ignore bins. 2 confirmed by review before the first run: the draft defined `fifo.march` twice (one decorator per bit position, same name). Fixed to one coverpoint with `rel=` matching each (slot, bit, value) bin and `inj=False`, so one sample hits eight bins.

**Measured after the fix** (`results/convergence/summary.md` and the clean run log): `fifo.march 128/128`, `fifo.occ_x_op 20/20`, `fifo.wrap_x_occ 8/8` (10 tuples minus the 2 justified ignore bins), all four illegal checks at zero hits.

**Anything I did not predict.** The reset cross. Profile v3 (reset rate raised at the boundaries) closed `(full, *)` but left `(partial, none/wr/rd)` and `(full, rd)` empty on seed 1:

```text
COVER fifo.rst_x_en                       8/12    66.67%
COVER TOTAL 98.12%  holes={'fifo.rst_x_en': [('partial', 'none'), ('partial', 'wr'), ('partial', 'rd'), ('full', 'rd')]}
```

Two causes: v3 starved the partial occupancies of resets (1/600 per cycle), and on a reset cycle it reused the shaped enables, which almost never give `rd`-only at full. Fixed with a constraint change, not a directed test: profile v4 (1/30 at the boundaries, 1/120 elsewhere, enables from the unconstrained `rst_wr` / `rst_rd` bits). Seed 1 then closes at 100%; per-seed closure across the regression is in `closure.md`.

---

## Entry 5 — the ported HW4 scoreboard: one sample point

**Prediction (before the run).** Porting the HW4 scoreboard unchanged keeps every released find, and the CRV stimulus should find at least as many of our own stress mutants as the directed suite did.

**Run.** HW4 suite and the first HW5 suite, same harness, our 24-mutant stress pool:

```text
HW4 directed:      ==== found/total = 20/24  =  83.3%  (threshold 90%) ====
HW5 CRV (1st cut): ==== found/total = 20/24  =  83.3%  (threshold 90%) ====
surviving mutants: head_shows_input_on_simul_at_one, empty_bypass_leaks_input, empty_reads_zero, full_from_pointers
```

**Verdict: partly.** Randomization added nothing on this pool. `head_shows_input_on_simul_at_one` makes `rd_data` follow `wr_data` while `count == 1` and both enables are high. At the only instant we sampled (1 ns after the edge) the mutant's output equals the true head, so it is invisible there. It is a sampling-point (observability) gap, not a stimulus gap.

**Fix.** A second sample point 1 ns after the new inputs are driven, before the edge (`check_pre_edge`). Spec rule 3 says `rd_data` *continuously* shows the head, so the head must not move between edges. Result on the same pool: 21/24 for HW5 and for this project suite (FINDINGS.md).

**Follow-up bug the fix introduced.** The parameter smoke run at `DEPTH=5 WIDTH=4` failed `before edge 1: count 1 != model 0`: the pre-edge check ran on the first reset cycle of a test, comparing the previous test's leftover DUT state with a fresh model. Fixed with an `env.known` flag (no pre-edge check until the first reset edge). The 8/8 runs never hit it, because every earlier test ended drained.

---

## Entry 6 — the readability rewrite and the Q1 / Q2 study code (November 2026)

**Task (summary of the request).** Rewrite the code so it reads like plain English, add the graduate-study measurements for Q1 (Brandon: does closing coverage track finding bugs?) and Q2 (Leo: how much does the seed matter?), test and run everything, write a `.gitignore` that stops the upload errors, and update the report.

**Prediction 1 (before the run).** Renaming the pyvsc constraint blocks (`c_roll`, `c_data`, `c_shape`) could reorder how the solver visits them and change the stimulus, even with the same seed. *Evidence that would show it:* a different `digest=` for any seed. Mitigation planned in advance: new block names that keep the old alphabetical and definition order.

**Run.** `python3 crv/regress.py` (sign-off, v4 seeds 1–10) and `python3 crv/regress.py --convergence` (v1–v4, seeds 1–5) on the rewritten code, then `diff` of every result row against the committed `summary.md` files.

```text
signoff: 10 old rows, 10 new rows
signoff IDENTICAL
convergence: 20 old rows, 20 new rows
convergence IDENTICAL
```

**Verdict: refuted.** 30/30 digests, coverage values and occupancy masses are identical. The harness again scores 8/8 released and 21/24 on our pool.

**Prediction 2 (before the run).** Q2: the seed changes found/total at short budgets only; at 2,500 cycles every seed scores the same. *Evidence:* a single value in the 2,500-cycle distribution over 20 seeds. Result in `extension/results/q2_table.md` and report section 10.

**What we did not predict.** The rewrite moved the opening reset inside the study-mode `try` block and caught only `AssertionError`. `reset_keeps_count` leaves `empty` at X, so the monitor's `int()` raises `ValueError` instead, and the study file recorded "no failure": a found mutant became a false survivor (seed 1 and seed 2 read 28/32 instead of 29/32). Caught by comparing each mutant's verdict with the October data.

**Fix.** Study mode now records any exception as the failure (`except Exception`, the type name kept in the message), and `detection_runner.py --mutants reset_keeps_count` re-measured the two affected seeds: `found@0` on both. The October data had labeled the same mutant `build/crash`, which was also not the real reason.

**Second finding.** The October extension read its correlation and median-detection numbers from `extension/data/summary.json`, but no script in the repo wrote that file. Every graduate number now regenerates from `extension/` (`q1_coverage_vs_bugs.py`, `q2_seed_spread.py`, `stimulus_distribution.py`), and `extension/crosscheck_with_harness.py` checks the measurement method against the course harness.

---

## Takeaway

**The class of failure:** generated constraints that *solve* are not constraints that *shape*. Three of the five drafts above passed every legality check and ran green while doing something other than what they said (entries 1–3). Only measuring the induced distribution showed it. The same goes for checkers: a scoreboard that is green on every mutant it can see says nothing about the instants it never samples (entry 5).

**Where it connects:** Week 5 (the `dist`/`implies` trap generalizes to `if_then` and to bounded-field bias), Week 6 (coverage bounds what you looked at, not what is correct: the closed reset cross took a constraint change, not more cycles), and the observability half of the reachability/observability split used in FINDINGS.md.

**What I would change in how I framed the request:** ask for the measurement script together with each constraint block ("and print the induced P(wr_en), P(rd_en) per region over 1,000 draws"), so the check comes with the generated block.

---

## Disclosure

- [x] Every prompt above is verbatim and complete. (Entry 6 states its request as a summary, marked as such.)
- [x] I have marked every edit I made to the generated output.
- [x] The tool is described by class, not by product name.
- [ ] Section 2 was written before the prompt was sent. *Not literally: each prediction was written before its own run, inside one working session that started with the prompt above. The order (prediction, then run) is real; the session prompt came first.*
