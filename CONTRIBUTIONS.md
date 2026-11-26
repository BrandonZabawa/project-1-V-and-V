# Contributions — <team name> · Project 1 (synchronous FIFO, constrained-random)

> **AI disclosure:** AI was used to help finish this task.

> This file and the git history are cross-checked against each other, and
> against every member's confidential peer eval. Where the three disagree, the
> conversation happens *before* the Professionalism row is scored — so make
> them agree. A file written the night of M4 will not survive that check, and
> the way it fails is by being vague.

**Members:** Brandon Zabawa (<NID>) · Leo (<NID>)
**Repo:** <https://github.com/BrandonZabawa/project-1-V-and-V>
**Track:** Project 1 — synchronous FWFT FIFO (`code/dut/fifo.sv`); the capstone tracks do not apply yet
**Last updated:** 2026-11-13 · **through milestone:** M-final

---

## How to read this file

Each milestone section lists what each member owned, with the commits, files, or
tags that show it. "Helped with the testbench" is not a contribution record.
"Wrote the constrained-random sequence and its coverage bins — `tb/seq_rw.py`,
commits `a1b2c3d`..`e4f5g6h`" is.

Work that is genuinely shared gets its own row and says how it was shared
(pairing, review, a split you can describe). Do not inflate, and do not
flatten real differences into a polite fiction — an honest record of an uneven
milestone reads far better than a uniform one nobody believes.

---

## M1 — Project 1 has one milestone (M-final, Sunday 23:59)

Project 1 has a single deadline, so M1 holds the whole record and M2–M4 are marked not applicable. The split follows the handout's "split the work by layer" advice. **Leo's rows are a proposal built around the part he owns (Q2). Add anything else he did, have him commit his Q2 files under his own name, and make the shares agree with `git log` before you submit.**

| Member | What they owned | Evidence (commits / files / PRs) | Approx. share |
|--------|-----------------|----------------------------------|--------------:|
| Brandon Zabawa | Driver, monitor, reference-queue scoreboard (ported from his HW4 suite), the pre-edge sample point, pyvsc transaction and constraints (ported from his HW5 suite), sequence profiles v1–v4, coverage model, mutation runs, survivor analysis; graduate extension **Q1 (does closing coverage track finding bugs?)** and the shared measurement engine | `tb/`, `crv/`, `coverage_model/`, `FINDINGS.md`, `closure.md`, `extension/q1_coverage_vs_bugs.py`, `extension/detection_runner.py`, report §9; commit `016f1c4` (first import of the whole repo; split later commits by layer) | <%> |
| Leo | Graduate extension **Q2 (how much does the seed matter?)**: the 20-seed, two-budget measurement, the mean and 95% interval, the lucky-seed check, the directed-versus-CRV split, and its report section; <add his other work, e.g. vplan review, demo recording, report editing> | `extension/q2_seed_spread.py`, `extension/study_statistics.py`, `extension/results/q2_*`, report §10; <his commits> | <%> |

**Shared or paired work:** Q1 and Q2 run on one shared measurement (`extension/detection_runner.py`, v4 seeds 1–5 feed both questions). Brandon reviews Q2's statistics; Leo reviews Q1's figure and claim. <add the rotating layer review: who reviewed whose layer, and when>

**What slipped, and who picked it up:** Profile v3 left the reset-at-partial-occupancy bins open (`ai_log.md`, entry 4). Closed in v4 by a constraint change, not a directed test. <who>

## M2 — not applicable (single-milestone project)

| Member | What they owned | Evidence (commits / files / PRs) | Approx. share |
|--------|-----------------|----------------------------------|--------------:|
| — | — | — | — |

**Shared or paired work:** —

**What slipped, and who picked it up:** —

**Changes to the division of labor since M1, and why:** —

## M3 — not applicable (single-milestone project)

| Member | What they owned | Evidence (commits / files / PRs) | Approx. share |
|--------|-----------------|----------------------------------|--------------:|
| — | — | — | — |

**Shared or paired work:** —

**What slipped, and who picked it up:** —

**Changes to the division of labor since M2, and why:** —

## M4 — not applicable (single-milestone project)

| Member | What they owned | Evidence (commits / files / PRs) | Approx. share |
|--------|-----------------|----------------------------------|--------------:|
| — | — | — | — |

**Shared or paired work:** —

**What slipped, and who picked it up:** —

---

## Whole-project summary

One row per member, across all four milestones. This is the row a reader checks
first, so it must be consistent with the four sections above.

| Member | Principal contributions (all four milestones) | Overall share |
|--------|-----------------------------------------------|--------------:|
| Brandon Zabawa | <one line, consistent with M1> | <%> |
| Leo | Q2 seed study and its report section; <one line, consistent with M1> | <%> |

**The three things this team did that we would each defend in an interview:**

1. We measured our constraints instead of trusting them: three pyvsc constructs solved cleanly while shaping nothing or the wrong thing (branch-local `dist`, bounded-field bias, a guarded reset field), and we replaced each one with a construct whose induced distribution we measured (`ai_log.md`).
2. We found a survivor that no amount of stimulus could catch, because it lived between our sample points, and closed it with a second sample point justified by spec rule 3 (`FINDINGS.md`).
3. Every coverage number reproduces from a seed and a command line (`crv/regress.py`, stimulus digests in `results/`), and the coverage gate fails the run if closure is not reached.

## Non-code contributions

Real work that leaves a thin git trace — and is graded all the same. Cite the
artifact where one exists.

| Member | Contribution | Where it shows |
|--------|--------------|----------------|
| Brandon Zabawa | spec archaeology / vplan authorship (requirement ids R1–R9, ambiguity table) | `vplan.md` |
| Leo | Q2 interpretation and the "lucky seed" check in the report; <review / demo prep / report editing> | report §10, `DEMO.md` 5:30 |

## AI assistance

Consistent with the course policy and your `ctm` record: name where an assistant
was used on capstone work, and who verified the output. The verifier is a named
person, always.

| Where | Used for | Verified by | Where the verification shows |
|-------|----------|-------------|------------------------------|
| `crv/transactions.py` | drafting the constraint block | Brandon Zabawa | `ai_log.md` entries 1–3 (induced-rate measurements) |
| `coverage_model/model.py` | drafting the coverage model | Brandon Zabawa | `ai_log.md` entry 4; `results/convergence/summary.md` |
| `tb/` port of the HW4 scoreboard | porting and the pre-edge check | Brandon Zabawa | `ai_log.md` entry 5; `results/mutation/` |
| `crv/regress.py`, `extension/` scripts, `REPORT.pdf` text | scripting and drafting | Brandon Zabawa | every number traced to `results/` |
| readability rewrite of `tb/`, `crv/`, `coverage_model/`, `test_fifo_p1.py` | renaming and restructuring with no behavior change | Brandon Zabawa | identical stimulus digests and coverage on all 30 regression runs (`ai_log.md` entry 6) |
| `extension/q1_coverage_vs_bugs.py` | drafting the Q1 analysis | Brandon Zabawa | `extension/results/crosscheck.json` (method agrees with the course harness) |
| `extension/q2_seed_spread.py`, `extension/study_statistics.py` | drafting the Q2 analysis and the interval math | Leo | `extension/results/q2_table.md` against the per-seed data in `extension/data/v4/` |

---

## Attestation

- [ ] Every claim above can be traced to the repo history.
- [ ] This file was updated at each milestone, not reconstructed at the end.
- [ ] Every member has read this file and agrees it is accurate.
- [ ] Each member has separately submitted their **confidential individual peer
      eval** — teammates' main contributions, an equity judgment, one sentence
      of evidence each — outside this repo, by the M4 deadline.
