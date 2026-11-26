#!/usr/bin/env python3
"""Q2 (Leo): How much does the seed matter?

The question, from the graduate-study menu: run the suite at 20 or more seeds
at two budgets, report the distribution of found/total at each budget with its
mean and a 95% interval, and watch for one lucky seed reported as the suite's
score.

Our claim (it could be wrong): on this FIFO the seed matters only at short
budgets. At 100 CRV cycles found/total spreads across seeds; at the 2,500-cycle
sign-off budget every seed scores the same, so our reported seed-1 score is
not a lucky seed. The claim is refuted if the 2,500-cycle distribution still
has spread, or if seed 1 sits above the 95% interval.

Two views of "the suite" are reported, because they answer different things:
  * CRV only    : the constrained-random test alone, the part the seed controls;
  * whole suite : directed tests T1 and T2 (seed-independent, measured once per
                  mutant) together with the CRV test, which is what the course
                  harness scores.

Input : extension/data/v4/seed_<n>.json, extension/data/directed_tests.json
Output: extension/results/q2_summary.json, extension/results/q2_table.md,
        extension/figures/q2_seed_spread.png (+ .pdf)

    python3 extension/detection_runner.py --directed-only
    python3 extension/detection_runner.py --profile v4 --seeds 1-20
    python3 extension/q2_seed_spread.py
"""
import json
import os
import random
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

EXTENSION_FOLDER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, EXTENSION_FOLDER)
import detection_runner as runner  # noqa: E402
import study_statistics as stats   # noqa: E402

SETTINGS = runner.SETTINGS["q2_seed_spread"]
PROFILE = SETTINGS["profile"]
SEEDS = SETTINGS["seeds"]
BUDGETS = SETTINGS["budgets"]
ALL_CHECKPOINTS = [budget for budget in runner.SETTINGS["coverage_checkpoints"] if budget <= max(BUDGETS)]
SIGN_OFF_SEED = 1          # the seed the report and the harness use by default
RESULTS_FOLDER = os.path.join(EXTENSION_FOLDER, "results")
FIGURES_FOLDER = os.path.join(EXTENSION_FOLDER, "figures")


def load_directed_finds():
    path = os.path.join(runner.DATA_FOLDER, "directed_tests.json")
    return {mutant_id: row["found_by_directed_tests"] for mutant_id, row in json.load(open(path)).items()}


def score_one_seed(seed_result, budget, directed_finds):
    """found counts for one seed at one budget, in every view we report."""
    scores = {"crv_released": 0, "crv_own": 0, "crv_all": 0,
              "suite_released": 0, "suite_own": 0, "suite_all": 0}
    for mutant in seed_result["mutants"]:
        found_by_crv = runner.is_found_within(mutant, budget)
        found_by_suite = found_by_crv or directed_finds[mutant["id"]]
        pool = "released" if mutant["pool"] == "released" else "own"
        scores[f"crv_{pool}"] += int(found_by_crv)
        scores["crv_all"] += int(found_by_crv)
        scores[f"suite_{pool}"] += int(found_by_suite)
        scores["suite_all"] += int(found_by_suite)
    scores["total_coverage"] = runner.coverage_at(seed_result, budget, "coverage")
    scores["cross_coverage"] = runner.coverage_at(seed_result, budget, "cross")
    return scores


def which_mutants_depend_on_the_seed(seed_results, budget):
    """Mutants found by some seeds but not others at this budget."""
    ids = [mutant["id"] for mutant in seed_results[0]["mutants"]]
    depends = []
    for mutant_id in ids:
        found_by = [result["seed"] for result in seed_results
                    if runner.is_found_within(next(m for m in result["mutants"] if m["id"] == mutant_id), budget)]
        if 0 < len(found_by) < len(seed_results):
            depends.append({"id": mutant_id, "seeds_that_find_it": len(found_by), "of": len(seed_results)})
    return depends


def rank_of_sign_off_seed(per_seed, view):
    """How many seeds score strictly higher / lower than the sign-off seed."""
    own_score = per_seed[SIGN_OFF_SEED][view]
    higher = sum(1 for score in per_seed.values() if score[view] > own_score)
    lower = sum(1 for score in per_seed.values() if score[view] < own_score)
    return {"score": own_score, "seeds_higher": higher, "seeds_lower": lower}


def smallest_budget_where_every_seed_agrees(seed_results, directed_finds, view):
    for budget in ALL_CHECKPOINTS:
        values = {score_one_seed(result, budget, directed_finds)[view] for result in seed_results}
        if len(values) == 1:
            return budget
    return None


def draw_spread(per_budget, totals, curve, findable_ceiling):
    """Left: every seed's score at the two budgets. Right: the spread at every
    checkpoint. Both in mutant counts, with the findable ceiling marked."""
    figure, (left, right) = plt.subplots(1, 2, figsize=(7.2, 2.8), dpi=150, sharey=True,
                                         gridspec_kw={"width_ratios": [1.15, 1]})
    jitter = random.Random(0)
    views = [("crv_all", "CRV test only", "#c0392b"), ("suite_all", "whole suite (T1+T2+T3)", "#2c3e50")]
    for budget_index, budget in enumerate(BUDGETS):
        for view_index, (view, label, color) in enumerate(views):
            x_center = budget_index * 2.4 + view_index * 1.0
            values = per_budget[budget]["values"][view]
            xs = [x_center + jitter.uniform(-0.2, 0.2) for _ in values]
            ys = [value + jitter.uniform(-0.08, 0.08) for value in values]
            left.scatter(xs, ys, s=10, color=color, alpha=0.6,
                         label=label if budget_index == 0 else None, zorder=2)
            described = per_budget[budget]["stats"][view]
            middle = described["mean"]
            left.errorbar([x_center + 0.36], [middle],
                          yerr=[[middle - described["ci95_low"]], [described["ci95_high"] - middle]],
                          fmt="D", color="black", ms=3.5, capsize=3, lw=1, zorder=3)
    for axes in (left, right):
        axes.axhline(findable_ceiling, color="#7f8c8d", lw=0.8, ls="--", zorder=1)
        axes.grid(alpha=0.3, lw=0.4, axis="y")
    left.text(-0.45, findable_ceiling + 0.5, f"{findable_ceiling} = every mutant a spec-based check can find",
              fontsize=6.5, color="#555555")
    left.set_xticks([0.5, 2.9])
    left.set_xticklabels([f"{BUDGETS[0]:,} cycles", f"{BUDGETS[1]:,} cycles"], fontsize=8)
    left.set_ylabel(f"mutants found (of {totals['all']})", fontsize=8)
    left.set_title(f"{len(SEEDS)} seeds; diamond = mean, bar = 95% interval", fontsize=8.5)
    left.legend(fontsize=7, frameon=False, loc="lower right")
    left.set_ylim(findable_ceiling - 7, findable_ceiling + 1.2)

    budgets = [row["budget"] for row in curve]
    for view, label, color in views:
        means = [row[view]["mean"] for row in curve]
        lows = [row[view]["min"] for row in curve]
        highs = [row[view]["max"] for row in curve]
        right.fill_between(budgets, lows, highs, color=color, alpha=0.15, lw=0)
        right.plot(budgets, means, "-o", color=color, ms=3, lw=1.1, label=label)
    right.set_xscale("log", base=2)
    right.set_xticks(budgets)
    right.set_xticklabels([f"{budget:,}" for budget in budgets], fontsize=6.5)
    right.set_xlabel("stimulus budget (CRV cycles)", fontsize=8)
    right.set_title("mean over seeds; band = min..max", fontsize=8.5)
    figure.tight_layout()
    for extension in ("png", "pdf"):
        figure.savefig(os.path.join(FIGURES_FOLDER, f"q2_seed_spread.{extension}"))


def write_markdown_table(summary):
    lines = ["# Q2 -- how much does the seed matter? (Leo)", "",
             f"Profile {PROFILE}, seeds {SEEDS[0]}-{SEEDS[-1]} ({len(SEEDS)} seeds). "
             f"Released pool = {summary['pool_sizes']['released']}, own pool = {summary['pool_sizes']['own']}.", "",
             "| budget | view | mean | 95% interval for the mean | min | median | max | seed 1 |",
             "|---:|---|---:|---|---:|---:|---:|---:|"]
    view_names = {"crv_released": "CRV only, released", "crv_all": "CRV only, all",
                  "suite_released": "whole suite, released", "suite_all": "whole suite, all",
                  "total_coverage": "total coverage %"}
    for budget in BUDGETS:
        block = summary["by_budget"][str(budget)]
        for view, name in view_names.items():
            described = block["stats"][view]
            lines.append(f"| {budget} | {name} | {described['mean']:.2f} | "
                         f"[{described['ci95_low']:.2f}, {described['ci95_high']:.2f}] | {described['min']} | "
                         f"{described['median']} | {described['max']} | {block['sign_off_seed'][view]['score']} |")
    with open(os.path.join(RESULTS_FOLDER, "q2_table.md"), "w") as table_file:
        table_file.write("\n".join(lines) + "\n")


def main():
    os.makedirs(RESULTS_FOLDER, exist_ok=True)
    os.makedirs(FIGURES_FOLDER, exist_ok=True)
    directed_finds = load_directed_finds()
    seed_results = [runner.load_seed_result(PROFILE, seed) for seed in SEEDS]
    released_total = sum(1 for mutant in seed_results[0]["mutants"] if mutant["pool"] == "released")
    totals = {"released": released_total, "own": len(seed_results[0]["mutants"]) - released_total,
              "all": len(seed_results[0]["mutants"])}
    views = ("crv_released", "crv_own", "crv_all", "suite_released", "suite_own", "suite_all",
             "total_coverage", "cross_coverage")

    by_budget = {}
    for budget in BUDGETS:
        per_seed = {result["seed"]: score_one_seed(result, budget, directed_finds) for result in seed_results}
        values = {view: [per_seed[seed][view] for seed in SEEDS] for view in views}
        by_budget[budget] = {
            "values": values,
            "stats": {view: stats.describe(values[view]) for view in views},
            "sign_off_seed": {view: rank_of_sign_off_seed(per_seed, view) for view in views},
            "seeds_closing_100_percent": sum(1 for value in values["total_coverage"] if value >= 100.0),
            "mutants_that_depend_on_the_seed": which_mutants_depend_on_the_seed(seed_results, budget),
        }

    curve = []
    for budget in ALL_CHECKPOINTS:
        row = {"budget": budget}
        for view in ("crv_all", "suite_all"):
            values = [score_one_seed(result, budget, directed_finds)[view] for result in seed_results]
            row[view] = {"mean": stats.mean(values), "min": min(values), "max": max(values)}
        curve.append(row)

    directed_found = sum(1 for found in directed_finds.values() if found)
    summary = {
        "question": "Q2: How much does the seed matter?",
        "owner": SETTINGS["owner"],
        "profile": PROFILE, "seeds": SEEDS, "budgets": BUDGETS, "pool_sizes": totals,
        "directed_tests_alone_find": directed_found,
        "by_budget": {str(budget): block for budget, block in by_budget.items()},
        "every_seed_agrees_from_budget": {
            "crv_all": smallest_budget_where_every_seed_agrees(seed_results, directed_finds, "crv_all"),
            "suite_all": smallest_budget_where_every_seed_agrees(seed_results, directed_finds, "suite_all"),
        },
        "curve_over_checkpoints": curve,
    }
    with open(os.path.join(RESULTS_FOLDER, "q2_summary.json"), "w") as summary_file:
        json.dump(summary, summary_file, indent=1)
    write_markdown_table(summary)
    findable_ceiling = max(by_budget[max(BUDGETS)]["values"]["suite_all"])
    draw_spread(by_budget, totals, curve, findable_ceiling)

    print(open(os.path.join(RESULTS_FOLDER, "q2_table.md")).read())
    printable = {budget: {"seeds_closing_100_percent": block["seeds_closing_100_percent"],
                          "mutants_that_depend_on_the_seed": block["mutants_that_depend_on_the_seed"]}
                 for budget, block in summary["by_budget"].items()}
    print(json.dumps({"directed_tests_alone_find": directed_found,
                      "every_seed_agrees_from_budget": summary["every_seed_agrees_from_budget"],
                      **printable}, indent=1))


if __name__ == "__main__":
    main()
