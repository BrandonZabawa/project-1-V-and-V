# Test results log: Project 1 FIFO (Q1 and Q2)

> **AI disclosure:** AI was used to help with this work, including checking the code, rerunning the analysis, and drafting this log.

This file is meant to be edited. Part A records what was checked when the submission was added to this repo (2026-11-26). Part B is a blank template for your own run on eustis. Fill it in, then resubmit.

---

## Part A: checks run while adding the submission (2026-11-26)

### Environment

| Item | Value |
|---|---|
| Machine | Linux cloud container (not eustis) |
| Python | 3.13 with matplotlib 3.11, numpy 2.5, PyYAML 6.0, scipy 1.18 (scipy was used only for the separate cross-check) |
| Simulators | **None installed** (no Icarus, Verilator or cocotb) |
| Course packet | **Not present** (no `code/dut/fifo.sv`, no `code/lib/models` golden model) |

Because the DUT, the golden model and the simulators live in the course packet on eustis, the cocotb suite (`make SIM=icarus`) and the mutation harness **could not be run here**. They have to be run in Part B. Every check below works from the saved per-seed data in `extension/data/`, which those simulations produced.

### What was checked

| # | Check | Command | Result |
|---|---|---|---|
| 1 | Every Python file compiles | `python -m py_compile` on all `.py` files | **Pass**, no errors |
| 2 | Q2 analysis reruns | `python3 extension/q2_seed_spread.py` | **Pass**, exit 0; `q2_summary.json` and `q2_table.md` are byte-identical to the submitted files |
| 3 | Q1 analysis reruns | `python3 extension/q1_coverage_vs_bugs.py` | **Pass**, exit 0; `q1_summary.json` and `q1_table.md` are byte-identical |
| 4 | Stimulus histogram and corner bound | `python3 extension/stimulus_distribution.py` | **Pass**, exit 0; `stimulus_distribution.json` is byte-identical |
| 5 | Report numbers | `python3 docs/make_numbers.py` | **Pass**, exit 0; `docs/numbers.tex` is byte-identical |
| 6 | Separate check of the Q2 statistics | Recomputed straight from `extension/data/v4/seed_*.json` with numpy and scipy (`scipy.stats.t.interval`), without using the project's `study_statistics.py` | **Pass**: every mean, 95% interval, min, median, max and seed-1 value matches `q2_table.md` (table below) |
| 7 | Figures regenerate | the same scripts write `extension/figures/*.png/.pdf` | **Pass**: they render correctly. The bytes differ only because of the matplotlib version, so the original figures were kept to match `REPORT.pdf` |
| 8 | Submission zip builds | `scripts/make_submission_zip.sh` | **Pass**, 101 files and 711 KiB; it warns about the unfilled placeholders listed below |

### Q2 results (how much does the seed matter?), confirmed by the separate recomputation

Profile v4, seeds 1–20, 32 mutants (8 released + 24 of our own).

| Budget | View | Mean | 95% interval | Min | Median | Max | Seed 1 |
|---:|---|---:|---|---:|---:|---:|---:|
| 100 | CRV only, all | 27.80 | [27.05, 28.55] | 24 | 28 | 29 | 28 |
| 100 | CRV only, released | 7.80 | [7.61, 7.99] | 7 | 8 | 8 | 8 |
| 100 | Whole suite, all | 29.00 | [29.00, 29.00] | 29 | 29 | 29 | 29 |
| 100 | Total coverage % | 87.93 | [86.88, 88.98] | 83.10 | 88.03 | 93.43 | 86.39 |
| 2500 | CRV only, all | 29.00 | [29.00, 29.00] | 29 | 29 | 29 | 29 |
| 2500 | CRV only, released | 8.00 | [8.00, 8.00] | 8 | 8 | 8 | 8 |
| 2500 | Whole suite, all | 29.00 | [29.00, 29.00] | 29 | 29 | 29 | 29 |
| 2500 | Total coverage % | 99.84 | [99.71, 99.96] | 99.06 | 100 | 100 | 100 |

CRV-only score for each seed at 100 cycles (seeds 1–20): 28, 28, 24, 28, 26, 29, 29, 29, 29, 26, 28, 29, 29, 28, 28, 29, 24, 27, 29, 29.
At 2,500 cycles every seed scores 29/32.

**Takeaway:** the seed matters only at short budgets. At 100 cycles the CRV-only score ranges from 24 to 29. At the 2,500-cycle sign-off budget every seed gives the same score. Seed 1 sits at the median (28 at 100 cycles), so the reported score does not come from a lucky seed. The 3 mutants no seed ever finds are the ones `FINDINGS.md` explains: 2 change `rd_data` while the FIFO is empty, which the spec leaves undefined, and 1 behaves exactly like the original design.

### Q1 results (does closing coverage track finding bugs?)

These were rerun and match the submission exactly (`extension/results/q1_table.md`). Every findable bug is caught by cycle 400 on every seed. Cross coverage keeps closing until 1,600 to 3,200 cycles.

### Placeholders still to fill before resubmitting

- `CONTRIBUTIONS.md`: `<team name>`, both `<NID>`s, the `<%>` shares, Leo's `<his commits>` and `<add his other work…>`, and the whole-project summary lines.
- `DEMO.md`: the demo recording link.
- `CONTRIBUTIONS.md` says Leo owns Q2 and his Q2 files should be committed under his name. Update that row so it reflects who actually finished Q2, and keep it consistent with `git log` and the peer evals.

---

## Part B: your own run on eustis (fill in)

Date: ____________ Tester: ____________

```bash
source /opt/course/cocotb-env/bin/activate
cd code
git clone https://github.com/BrandonZabawa/project-1-V-and-V tb/fifo_p1
cd tb/fifo_p1
git checkout claude/sharp-cray-smm7t0
```

| # | Check | Command | Expected | What you saw |
|---|---|---|---|---|
| 1 | Full suite, Icarus | `make SIM=icarus` | `TESTS=3 PASS=3`, `COVER TOTAL 100.00%`, digest `9f792b79f86b6cf1` | |
| 2 | Full suite, Verilator | `make SIM=verilator` | 3/3 pass, same digest | |
| 3 | Seed replay | `SEED=7 make SIM=icarus` (run it twice) | digest `c40273008eb7c833` both times | |
| 4 | Released mutant pool | `just mutate fifo_p1` | 8/8 found | |
| 5 | Stress pool | `python -m craft_mutate.mutate --tb . --dut ../../dut/fifo.sv --pool mutation/mutants_stress.yaml --sim icarus` | 21/24 found | |
| 6 | Q2 rerun | `python3 extension/q2_seed_spread.py` | the table above | |
| 7 | Q1 rerun | `python3 extension/q1_coverage_vs_bugs.py` | matches `q1_table.md` | |
| 8 | Submission zip | `scripts/make_submission_zip.sh` | writes `../fifo_p1_submission.zip` | |

Notes:

-
