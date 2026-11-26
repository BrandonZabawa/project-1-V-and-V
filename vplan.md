# Verification plan — synchronous FWFT FIFO (`dut/fifo.sv`)

**Author:** Brandon Zabawa and Leo (see `CONTRIBUTIONS.md`) **Spec version:** `code/dut/specs/fifo.md`, packet 20260831 . rev 8b9d934 **Date:** 2026-10-24

> **AI disclosure:** AI was used to help finish this task.

> A vplan is an argument that "done" is definable before you write tests. Every
> row here should be something you could defend in a signoff meeting. Rows you
> cannot defend are the honest content of the Risk section, not omissions.

Spec requirement ids used below (numbered from `fifo.md` "Behavior (the contract)" and "Corner cases"):

| Req | Spec text |
|-----|-----------|
| R1 | Reset: while `rst_n==0`, on the next clock edge `count→0`, `empty=1`, `full=0` |
| R2 | A write occurs iff `wr_en && !full`; a write while `full` is dropped (no overflow, no corruption) |
| R3 | A read occurs iff `rd_en && !empty`; a read while `empty` is ignored; `rd_data` continuously shows the current head |
| R4 | Simultaneous read+write (not full, not empty): both happen on the same edge, `count` unchanged |
| R5 | `full == (count==DEPTH)`, `empty == (count==0)` at all times |
| R6 | Strictly first-in-first-out |
| R7 | Ports table: `rd_data` is the head, valid whenever `!empty`; `count` is 0..DEPTH |
| R8 | Corner list: fill to full, drain to empty, write-while-full, read-while-empty, r+w at the boundaries, pointer wrap-around, ordering under random interleaving |
| R9 | Parameters `WIDTH`, `DEPTH` (defaults 8, 8) |

## 1. Scope

**In scope:** the `fifo` module at `WIDTH = 8, DEPTH = 8` (the graded configuration), against `fifo.md` rules R1–R8: reset, the write and read handshakes, dropped writes and ignored reads, simultaneous read+write at every occupancy, both flags, `count`, the FWFT head on `rd_data` whenever `!empty`, FIFO ordering, and pointer wrap. Checked every cycle at two sample points by a reference-queue scoreboard (`models.fifo_model.FifoModel`). One undefined control combination is in scope on purpose (security thread): `wr_en` / `rd_en` asserted during reset.
**Out of scope:** `rd_data` while `empty` (the spec defines the head only when `!empty`, so any value there is legal and nothing checks it; see risk 2). Timing, X-propagation beyond the monitor's X/Z flag, and power. Parameter sets other than 8/8 are exercised only as a smoke regression (`DEPTH=5 WIDTH=4`, `DEPTH=16 WIDTH=16`), not closed. Formal proof (Week 8) and SVA (Week 7) are not part of this plan.
**Assumptions about the environment:** one free-running clock, inputs change only on the falling edge, synchronous active-low reset. Every `(wr_en, rd_en)` pair is legal at every occupancy (R2, R3), and reset is a legal input, so the stimulus never needs a legality constraint; constraints only shape. The golden model is trusted as the reading of the spec; where it encodes a choice the spec leaves open, that choice is listed in section 5.

## 2. Feature list

One row per behavior the spec requires. `Req` cites a line or section of the
spec — if you cannot cite one, that is a spec gap and it belongs in section 5.

| ID | Feature | Req | Priority | How it is verified |
|----|---------|-----|----------|--------------------|
| F1 | Reset clears `count`, sets `empty`, clears `full`, from any occupancy | R1 | H | directed (T1, T2) + CRV (T3, resets at empty / partial / full) |
| F2 | Accepted write: `count` +1, data lands at the tail | R2 | H | CRV + scoreboard every cycle |
| F3 | Write while full is dropped: `count`, head and order unchanged | R2 | H | directed (T1) + CRV bin `(full, write)` |
| F4 | Accepted read: `count` −1, head advances | R3 | H | CRV + scoreboard |
| F5 | Read while empty is ignored: `count` stays 0, next write reads back | R3 | H | directed (T1) + CRV bin `(empty, read)` |
| F6 | `rd_data` shows the head whenever `!empty`, continuously (also between edges, with new inputs applied) | R3, R7 | H | scoreboard at two sample points (after edge, before next edge) |
| F7 | Simultaneous r+w mid-range: both happen, `count` unchanged | R4 | H | CRV bins `(one/mid/almost_full, simul)` |
| F8 | Simultaneous r+w at `full` (read only) and at `empty` (write only) | R2, R3, R4 | H | directed (T1) + CRV bins `(full, simul)`, `(empty, simul)` |
| F9 | `full` and `empty` match `count` on every cycle | R5 | H | scoreboard + illegal bin I2 |
| F10 | FIFO order under random interleaving, across pointer wrap | R6, R8 | H | scoreboard head compare + cross X2 |
| F11 | Every bit of every storage slot carries both values out | R2, R6 | M | march coverpoint C10 (128 bins) |
| F12 | Count moves by at most the amount the spec allows for that operation | R2–R4 | M | illegal bin I1 |
| F13 | Enables asserted during reset do not beat reset; no pre-reset data survives (security thread) | R1 (undefined combination) | M | directed (T2) + cross X3 |
| F14 | Other parameter values elaborate and pass | R9 | L | smoke regression at `DEPTH=5 WIDTH=4` and `DEPTH=16 WIDTH=16` |

## 3. Coverage model

Coverpoints and their bins. A cross earns its place only if the interaction is
where a bug would hide — say which bug.

Implemented in `coverage_model/model.py` (cocotb-coverage), sampled once per checked cycle from the scoreboard's prediction.

| ID | Coverpoint | Bins | Why these bins |
|----|-----------|------|----------------|
| C1 | `fifo.occ` post-edge occupancy | 0, 1, …, 8 (9) | every occupancy, so off-by-one flag and wrap faults have a state to show in |
| C2 | `fifo.op` requested op (non-reset) | idle, write, read, simul (4) | the four handshakes of R2–R4 |
| C3 | `fifo.pre_occ` pre-edge occupancy class | empty, one, mid, almost_full, full (5) | the boundary classes where gating changes behavior; `one` and `almost_full` are where off-by-one gating bites |
| C4 | `fifo.outcome` what the edge did | none, push, pop, push_pop, drop_write, ignore_read, simul_drop_write, simul_ignore_read (8) | separates "requested" from "happened", so dropped and ignored ops are visible bins |
| C5 | `fifo.data` accepted-write data class | zero, ones, 0x55, 0xAA, other (5) | data corners that toggle every bit |
| C6 | `fifo.wrap` pointer wrap on this edge | wr_wrap, rd_wrap (2) | wrap logic is where early-wrap faults live |
| C7 | `fifo.wrap_occ_cls` occupancy class on wrap edges | 5 classes | feeds X2 |
| C8 | `fifo.rst_occ` occupancy when reset hits | empty, partial, full (3) | reset must clear from every state |
| C9 | `fifo.rst_en` enables during a reset edge | none, wr, rd, both (4) | the undefined combination (security thread) |
| C10 | `fifo.march` (slot, bit, value) of every popped word | 8 × 8 × 2 = 128 | a stuck or coupled cell keeps order, count and flags intact; only data that toggles that exact bit in that exact slot exposes it |

**Crosses**

| ID | Cross | The interaction it is aimed at |
|----|-------|-------------------------------|
| X1 | `fifo.occ_x_op` = C3 × C2 (20 bins) | gating bugs that only exist at one occupancy: write accepted at full (`ignore_full`), read accepted at empty (`ignore_empty`), a simultaneous r+w that miscounts, a write that sneaks in at full because a read happens on the same edge |
| X2 | `fifo.wrap_x_occ` = C6 × C7 (10 tuples, 8 bins) | early-wrap and wrap-to-wrong-slot faults, which only corrupt order when the wrap happens with live data behind it (wrap at `one`, `almost_full`, `full`) |
| X3 | `fifo.rst_x_en` = C8 × C9 (12 bins) | write-beats-reset and stale-pointer faults: reset with data inside, with a write or read racing it (security thread) |

**Illegal / ignore bins:**
- Ignore (X2): `(rd_wrap, full)`: a read decrements `count` or, as a simultaneous r+w, needs `!full` (R4), and at `full` a simultaneous r+w is read-only (R2), so a read can never leave the FIFO full. `(wr_wrap, empty)`: an accepted write always leaves `count ≥ 1` (R2, R4). Both are unreachable by the spec, not hard to reach.
- Illegal (each a `CoverCheck` that must stay at zero hits, and an assertion in `check_illegal`): I1 `count` change other than the one R2–R4 allow for that `(pre_occ, op)`; I2 `full` and `empty` together (R5, `DEPTH ≥ 1`); I3 both pointers wrapping on one edge (pointers are equal only at empty or full, where R2/R3 forbid a true simultaneous r+w); I4 occupancy outside 0..`DEPTH` (R7).
- Deliberately **not** ignored: `(full, write)` and `(empty, read)` in X1. The spec defines both (dropped, ignored), so they are corners to cover, not exclusions.

## 4. Test matrix

Every feature maps to at least one test; every test traces back to a feature.
An untraceable test is a test nobody can defend.

| Test | Features | Kind | Pass criterion |
|------|----------|------|----------------|
| `test_t1_directed_smoke` | F1, F3, F5, F6, F7, F8, F9, F10 | directed (T1) | scoreboard clean on every cycle at both sample points; `full == 1` after 8 writes |
| `test_t2_security_reset_race` | F1, F13, F8 (r+w at empty after reset) | directed (T2, security thread) | after a reset edge with `wr_en = rd_en = 1`: `count == 0`, `empty == 1`; first head after reset is the first post-reset write, never the marker |
| `test_t3_crv_signoff` | F1–F13; F14 when run with `DEPTH` / `WIDTH` overrides | random, pyvsc (T3: profile v4, seed 1, 2,500 cycles by default) | scoreboard clean; stimulus self-checks reached (write-while-full, read-while-empty, r+w at full and at empty, true r+w, both wraps, reset with data, write during reset, every occupancy 0..8); functional coverage 100% |

**Runs built from these three tests** (commands, not extra tests; each one runs the tests above with different seeds, profiles, parameters or DUTs):

- Sign-off regression, `python3 crv/regress.py`: `test_t3_crv_signoff` on profile v4, seeds 1–10 (features F1–F13). Pass: every seed green, merged coverage 100%, per-seed closure reported.
- Convergence history, `python3 crv/regress.py --convergence`: `test_t3_crv_signoff` on profiles v1–v4, seeds 1–5 (the coverage closure argument). Pass: holes per profile recorded in `results/convergence/summary.md`.
- Parameter smoke runs, `make DEPTH=5 WIDTH=4` and `make DEPTH=16 WIDTH=16 COV_GATE=0`: all three tests (feature F14). Pass: all tests green; the coverage gate applies to the 8/8 model only (see risk 4).
- Mutation runs, `just mutate fifo_p1` and the same harness on `mutation/mutants_stress.yaml`: all three tests against each mutant (quality of the F1–F13 checks). Pass: found/total recorded in `FINDINGS.md`.
- Graduate extension Q1 and Q2, `extension/detection_runner.py`: `test_t3_crv_signoff` in study mode on many seeds and budgets, plus the two directed tests once per mutant. Results in `extension/results/`.

## 5. Risk and spec ambiguity

| # | Ambiguity or risk | Where in the spec | How I resolved it | Residual |
|---|-------------------|-------------------|-------------------|----------|
| 1 | Write asserted during reset: spec says what reset does, not whether a same-edge write may land | R1 | assumed reset wins (synchronous reset dominates); tested in T2 and covered by X3 | if the intended design lets the write land, T2 is green against the wrong intent; no spec line settles it |
| 2 | `rd_data` while `empty` is undefined ("valid whenever `!empty`") | Ports table, R3 | not checked; any value is legal | a design that drives the live `wr_data` bus or stale secret data onto `rd_data` while empty passes every check (measured: two stress mutants survive for exactly this reason, see FINDINGS) |
| 3 | "`rd_data` continuously shows the current head": does the head have to hold between edges while new inputs are applied? | R3 | read literally: yes. Added a pre-edge sample point | a combinational path from the inputs to `rd_data` is now caught; glitches shorter than 1 ns after the input change are still not sampled |
| 4 | Simultaneous r+w at full: spec rule 4 covers only "not full, not empty"; rules 2–3 decide the boundary (write dropped at full, read ignored at empty) | R2–R4 | assumed rules 2–3 apply on the pre-edge state, as `FifoModel` does | a design that allows write-through at full when a read frees a slot would be flagged as a bug; the spec arguably permits only our reading |
| 5 | The model "mirrors the RTL exactly" (its own docstring) | n/a | treated the model as the spec's reading; cross-checked each model rule against R1–R6 by hand | a misreading shared by the model and RTL is invisible to every compare |
| 6 | Only `WIDTH = DEPTH = 8` is closed | R9 | smoke runs at 5/4 and 16/16 | coverage bins and the hidden pool are 8/8 only |

## 6. Closure criteria

State the numbers *before* you start, so closure is a measurement and not a
negotiation.

- Functional coverage target: **100%** of the model in section 3 (C1–C10, X1–X3, all bins except the two justified ignore bins), with all four illegal checks at zero hits, reached by the CRV sign-off test alone (directed tests do not sample coverage), and on the merged seeded regression.
- Mutation target: **≥ 90%** found/total on the hidden pool (full credit line); 8/8 on the released pool; every survivor on our own stress pool classified as reachability, observability, or equivalent.
- Assertions: every property paired with a passing `cover` (no vacuous passes). Not applicable here: this environment uses scoreboard checks and coverage-checked illegal bins, not SVA. The stimulus self-checks in T3 play the non-vacuity role: the run fails if any corner the checks depend on was never reached.
- What I will report as **not verified**: `rd_data` while empty; parameter sets other than 8/8 beyond a smoke run; behavior inside a clock cycle other than at the two sample points; anything the model and RTL could share as the same misreading.
