# Demo — Project 1

> **AI disclosure:** AI was used to help finish this task.

**Demo link:** <paste the recording URL here (unlisted YouTube, Panopto, or a OneDrive link) before submitting>

**Length:** about 6 minutes (Brandon presents Q1, Leo presents Q2). Record the terminal (eustis over SSH is fine) and narrate. Every command below is copy-pasteable from `code/tb/fifo_p1/` with the course environment active.

**Easiest way to record:** `scripts/demo.sh` plays the table below in order and waits for Enter between steps. Run `scripts/demo.sh --check` first, rehearse once with `scripts/demo.sh --cues` (prints the "Say" column), then start the recorder and run `scripts/demo.sh`. Figures open in VS Code when you run it from a VS Code terminal. To redo one part: `scripts/demo.sh --from 9`.

| Time | Show | Say (one or two sentences) |
|------|------|-----------------------------|
| 0:00 | `README.md` layering picture | "Driver drives on the falling edge, the monitor reads pins back, the scoreboard is a reference queue that checks count, full, empty and the head every cycle at two sample points; coverage is sampled from the scoreboard's own prediction." |
| 0:40 | `crv/transactions.py`, the `OPERATION_MIX` table and `shape_operation_by_occupancy` | "Every enable pair is legal, so constraints only shape. Occupancy and phase are non-random fields fed each cycle. We do not use `dist` inside the branches, because we measured that pyvsc applies it unconditionally." |
| 1:30 | `make SIM=icarus` (≈ 25 s) | Point at `TESTS=3 PASS=3`, the `OCC` histogram (U-shaped: about 0.10–0.13 at empty, about 0.2 at full, against 0.0625 for uniform), and `COVER TOTAL 100.00%`. |
| 2:15 | `SEED=7 make SIM=icarus TESTCASE=test_t3_crv_signoff` twice | "Same seed, same digest. The seed and the command line are the source of truth." |
| 2:45 | `results/convergence/summary.md` | "v1 uniform stalls at 92.49% (no resets). v2 and v3 leave reset-cross holes. v3 even opened new ones at partial occupancy. v4 fixed them with a constraint change, not a directed test." |
| 3:30 | `python -m craft_mutate.mutate --tb . --dut ../../dut/fifo.sv --pool mutants_released.yaml --sim icarus` (or show `results/mutation/released.txt`) | "8 of 8 on the released pool." |
| 4:00 | `FINDINGS.md` survivors table | "On our own 24-mutant pool we find 21. Two survivors drive `rd_data` while empty, which the spec leaves undefined. One is logically equivalent. The one we fixed lived between our sample points." |
| 4:40 | `extension/figures/occupancy_hist.png` | Graduate extension: the histogram against uniform and the corner bound. |
| 5:00 | `extension/figures/q1_curves.png` (Brandon) | "Q1: both curves on one budget axis. Every findable bug falls in the first few hundred cycles, while the cross keeps closing for thousands more. A coverage hole predicted a miss; coverage growth did not predict finds." |
| 5:30 | `extension/figures/q2_seed_spread.png` (Leo) | "Q2: 20 seeds at two budgets. The seed changes the CRV score at 100 cycles and not at all at 2,500, and seed 1 is not a lucky seed." |
