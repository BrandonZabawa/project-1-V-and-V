# Project 1 — constrained-random verification of the synchronous FWFT FIFO

> **AI disclosure:** AI was used to help finish this task.

EEE 4701 / EEE 5703 · packet `craft-vv-student` 20260831 · rev 8b9d934 · DUT `code/dut/fifo.sv` (spec `code/dut/specs/fifo.md`), `WIDTH = DEPTH = 8` · Team: Brandon Zabawa and Leo · Repo: <https://github.com/BrandonZabawa/project-1-V-and-V>

## Results at a glance

Rerun from this exact tree on 2026-11-14 with the eustis tool versions (Icarus 12.0, Verilator 5.020, cocotb 1.9.2). Every number matches the saved evidence file.

| Check | Result | Evidence |
|---|---|---|
| Full suite (directed smoke, reset-race security test, constrained-random sign-off), Icarus | 3/3 pass, functional coverage 100.00%, seed 1 digest `9f792b79f86b6cf1` | `results/clean_icarus.log` |
| Same suite, Verilator | 3/3 pass, same digest | `results/verilator/clean.log` |
| Seed replay (`SEED=7`, twice) | identical digest `c40273008eb7c833` both times | `results/signoff/summary.md` row 7 |
| Released mutant pool | **8/8** found | `results/mutation/released.txt` |
| Our own stress pool | **21/24** found: 2 survivors change `rd_data` while empty (undefined by the spec), 1 is logically equivalent | `results/mutation/stress.txt`, `FINDINGS.md` |
| Sign-off regression, profile v4, seeds 1–10 | all pass; merged coverage 213/213 bins | `results/signoff/summary.md` |
| Other parameter sets | `DEPTH=5 WIDTH=4`: 3/3, 100%; `DEPTH=16 WIDTH=16`: 3/3, 99.67% (coverage gate off, smoke only) | rerun commands below |
| **Q1** (Brandon): does closing coverage track finding bugs? | Only early. Every findable bug falls by cycle 400 on every seed, while cross coverage keeps closing until 1,600 to 3,200 cycles | `extension/results/q1_table.md`, `extension/figures/q1_curves.png` |
| **Q2** (Leo): how much does the seed matter? | At 100 cycles the constrained-random score spans 24 to 29 of 32 (mean 27.80, 95% interval 27.05 to 28.55); at 2,500 cycles every seed scores 29/32. Seed 1 is the median, not a lucky seed | `extension/results/q2_table.md`, `extension/figures/q2_seed_spread.png` |

## Where to put this repo

Unzip or clone it to `code/tb/fifo_p1/` inside the student packet. Then the default DUT path (`../../dut/fifo.sv`), the golden model (`../../lib/models`) and the course harness all resolve with no edits:

```bash
source /opt/course/cocotb-env/bin/activate        # eustis
cd code
git clone https://github.com/BrandonZabawa/project-1-V-and-V tb/fifo_p1   # or unzip the submission zip into tb/
make -C tb/fifo_p1 SIM=icarus                     # full suite (3 tests), about 25 s
python -m craft_mutate.mutate --tb tb/fifo_p1 --pool tb/fifo/mutants_released.yaml --sim icarus
just mutate fifo_p1                               # same thing: the repo carries a copy of the released pool
```

## Record the demo (about 6 minutes)

`scripts/demo.sh` plays the `DEMO.md` script in order: it prints each step's title and the script's target time, runs the commands, prints the lines to point at, and opens each figure in VS Code (this works in a VS Code Remote-SSH terminal on eustis). It waits for Enter between steps, so you control the pace while you talk.

```bash
cd code/tb/fifo_p1
scripts/demo.sh --check          # preflight in a few seconds: tools, DUT, golden model, figures
scripts/demo.sh --cues           # rehearsal: also prints what to say at each step
scripts/demo.sh                  # the recording: start the screen recorder, then press Enter per step
scripts/demo.sh --from 9         # re-record from step 9 (Q1) onward
```

If the shell answers `Permission denied` (an unzip on Windows can drop the executable bit), run `chmod +x scripts/*.sh` once, or start it as `bash scripts/demo.sh`. Step 6 shows the saved released-pool run by default, because the live run takes about 4 minutes; add `--live-mutation` to run it on camera. Full output of every command lands in `demo_logs/` (ignored by git). Save the video outside the repo (video files are ignored too), upload it, and paste the link into `DEMO.md`.

## What is where (the deliverables)

| Deliverable | File(s) |
|---|---|
| Verification plan | `vplan.md` |
| `tb/`: driver, monitor, scoreboard | `tb/driver.py`, `tb/monitor.py`, `tb/scoreboard.py` (reference queue = `FifoModel`), `tb/env.py` |
| `crv/`: transactions, constraints, seeded regression | `crv/transactions.py` (pyvsc), `crv/sequences.py` (profiles v1–v4), `crv/regress.py`, `crv/seeds.txt` |
| Coverage model and its report | `coverage_model/model.py`; reports in `results/signoff/summary.md`, `results/convergence/summary.md`; argument in `closure.md` |
| found/total and survivor analysis | `FINDINGS.md`; harness output in `results/mutation/` |
| Check the Machine | `ai_log.md` (probe scripts in `results/ai_probes/`) |
| Team record | `CONTRIBUTIONS.md` |
| Report and demo | `REPORT.pdf` (built from `docs/REPORT.tex`); demo link and script in `DEMO.md`; `scripts/demo.sh` plays the script |
| Test results log (editable) | `RESULTS.md` |
| Submission zip | `scripts/make_submission_zip.sh` (keeps what `.gitignore` keeps, warns about unfilled placeholders) |
| Graduate extension | `extension/` (see below); summarized in `REPORT.pdf` §8–§10 |

### Graduate extension (`extension/`)

| Part | Owner | Script | Output |
|---|---|---|---|
| Occupancy histogram against uniform, and a constraint that reaches *full with a simultaneous read and write* with P > 0.99 within N draws | team | `stimulus_distribution.py` (uses `chain.py`) | `results/stimulus_distribution.json`, `figures/occupancy_hist.png` |
| **Q1. Does closing coverage track finding bugs?** Cross coverage and found/total at 7 doubling budgets, both curves on one budget axis | Brandon Zabawa | `q1_coverage_vs_bugs.py` | `results/q1_summary.json`, `results/q1_table.md`, `figures/q1_curves.png`, `figures/q1_scatter.png` |
| **Q2. How much does the seed matter?** found/total at 20 seeds and two budgets, mean and 95% interval | Leo | `q2_seed_spread.py` | `results/q2_summary.json`, `results/q2_table.md`, `figures/q2_seed_spread.png` |
| Shared measurement engine (first-failure cycle of every mutant, coverage at each checkpoint) | team | `detection_runner.py` | `data/<profile>/seed_<n>.json`, `data/directed_tests.json` |
| Check of the method against the course harness | team | `crosscheck_with_harness.py` | `results/crosscheck.json`, `results/mutation/*.txt` |

## Reproducing every number (the seed and the command line are the source of truth)

All commands from `code/tb/fifo_p1/` with the course environment active. Icarus 12.0, cocotb 1.9.2, pyvsc 0.9.5.27214109393, cocotb-coverage 1.2.0. Times are for 2 cores.

| Number | Command | Output |
|---|---|---|
| Clean suite green, coverage 100% on seed 1 | `make SIM=icarus` | `TESTS=3 PASS=3`, `COVER TOTAL 100.00%` |
| Replay any seed exactly | `SEED=7 make SIM=icarus` | the same `digest=` every time |
| Sign-off regression (v4, seeds 1–10) | `python3 crv/regress.py` | `results/signoff/summary.md` |
| Convergence history (v1–v4, seeds 1–5) | `python3 crv/regress.py --convergence` | `results/convergence/summary.md`, `results/convergence/occupancy.json` |
| Released pool | `python -m craft_mutate.mutate --tb . --dut ../../dut/fifo.sv --pool mutants_released.yaml --sim icarus --json results/mutation/released.json` | `results/mutation/released.txt` |
| Our own stress pool | same, `--pool mutation/mutants_stress.yaml` | `results/mutation/stress.txt` |
| Histogram and corner bound (seconds) | `python3 extension/stimulus_distribution.py` | `extension/results/stimulus_distribution.json` |
| Directed tests against every mutant (about 1.5 min) | `python3 extension/detection_runner.py --directed-only` | `extension/data/directed_tests.json` |
| Measurement for Q1 and Q2 (about 60 min) | `python3 extension/detection_runner.py --profile v4 --seeds 1-20` then `--profile v1 --seeds 1-5` | `extension/data/<profile>/seed_<n>.json` |
| Q1 numbers and figures | `python3 extension/q1_coverage_vs_bugs.py` | `extension/results/q1_*`, `extension/figures/q1_*` |
| Q2 numbers and figures | `python3 extension/q2_seed_spread.py` | `extension/results/q2_*`, `extension/figures/q2_*` |
| Method check against the harness (about 15 min) | `python3 extension/crosscheck_with_harness.py` | `extension/results/crosscheck.json` |
| Report | `python3 docs/make_numbers.py && cd docs && pdflatex REPORT.tex && pdflatex REPORT.tex && cp REPORT.pdf ..` | `REPORT.pdf` |
| Other parameter sets (smoke) | `make SIM=icarus DEPTH=5 WIDTH=4`, `make SIM=icarus DEPTH=16 WIDTH=16 COV_GATE=0` | green |

Verilator: `make SIM=verilator` adds `-Wno-fatal`, because the provided `fifo.sv` trips a `WIDTHEXPAND` lint warning that is fatal by default (the RTL, not the testbench). Rerun on 2026-11-14 under Verilator 5.020: 3/3 pass with the same seed 1 digest as Icarus (`results/verilator/clean.log`).

## Uploading to the autograder

Upload the submission zip, not the working folder. A folder upload sends every file under `.git/` (about 200 objects) and every raw per-seed log, and the upload server answered each of them with `502 Bad Gateway`. `.gitignore` keeps regenerable output out of the repo; the zip also leaves out `.git/`. Build the zip after pasting the demo link:

```bash
scripts/make_submission_zip.sh                   # writes ../fifo_p1_submission.zip, lists any placeholders left
STRICT=1 scripts/make_submission_zip.sh          # same, but refuses while a placeholder remains
```

If an older clone of this repo committed raw logs before `.gitignore` existed, stop tracking them (`--ignore-unmatch` skips any path that is not there, so the command is safe on a fresh clone):

```bash
git rm -r --cached --ignore-unmatch results/convergence/v1 results/convergence/v2 results/convergence/v3 results/convergence/v4 results/signoff/v4 docs/REPORT.pdf
git commit -m "Stop tracking regenerable logs (see .gitignore)"
```

## Layering in one picture

```text
 crv/sequences.py ──(rst_n, wr_en, rd_en, wr_data)──> tb/driver.py ──pins──> fifo.sv
   ^  count, phase into FifoTransaction (pyvsc)                                  │
   │                                                                     tb/monitor.py
   └──────────────────── observed count ─────────────────────────────────────── │ PinSnapshot
                                                                                 v
                    coverage_model/model.py <── CycleRecord ── tb/scoreboard.py (FifoModel reference queue)
```

The driver never checks; the monitor reads the pins back and never asks the driver; the scoreboard sees only `PinSnapshot` records; coverage is sampled from the scoreboard's own prediction (`CycleRecord`).
