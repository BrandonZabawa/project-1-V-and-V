#!/usr/bin/env python3
"""Q1 (Brandon Zabawa): Does closing coverage track finding bugs?

The question, from the graduate-study menu: measure cross coverage and
released found/total at five or more stimulus budgets (doubling each step),
draw both curves on one budget axis, and watch for a model that reaches 100%
while the finds stand still.

Our claim (it could be wrong): on this FIFO, cross-coverage closure tracks
found/total only up to a small budget. Past it, finds stand still while the
cross keeps closing, so a closed cross certifies how broad the stimulus was,
not how many bugs it found. The claim is refuted if the found/total curve keeps
rising together with the cross right up to closure.

What this script does with the measured data:
  * for every (profile, seed, budget): cross coverage, total coverage, and
    found/total on the released pool, our own pool, and both;
  * the mean, min and max over seeds, per profile and budget (the table);
  * Pearson and Spearman correlation of cross coverage against found/total
    over every (profile, seed, budget) point;
  * per seed: the cycle of the last new find, and the first budget at which
    the cross reached 100%;
  * which mutants each profile never finds, and which cross was still open.

Input : extension/data/<profile>/seed_<n>.json   (from detection_runner.py)
Output: extension/results/q1_summary.json, extension/results/q1_table.md,
        extension/figures/q1_curves.png (+ .pdf), extension/figures/q1_scatter.png (+ .pdf)

    python3 extension/detection_runner.py --profile v1 --seeds 1-5
    python3 extension/detection_runner.py --profile v4 --seeds 1-5
    python3 extension/q1_coverage_vs_bugs.py
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

EXTENSION_FOLDER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, EXTENSION_FOLDER)
import detection_runner as runner  # noqa: E402
import study_statistics as stats   # noqa: E402

SETTINGS = runner.SETTINGS["q1_coverage_vs_bugs"]
PROFILES = SETTINGS["profiles"]
SEEDS = SETTINGS["seeds"]
BUDGETS = SETTINGS["budgets"]
RESULTS_FOLDER = os.path.join(EXTENSION_FOLDER, "results")
FIGURES_FOLDER = os.path.join(EXTENSION_FOLDER, "figures")
PROFILE_COLORS = {"v1": "#7f8c8d", "v4": "#c0392b"}
PROFILE_LABELS = {"v1": "v1 (uniform)", "v4": "v4 (sign-off constraints)"}


def found_counts(seed_result, budget):
    """(released found, own found, all found) at this budget."""
    released = own = 0
    for mutant in seed_result["mutants"]:
        if runner.is_found_within(mutant, budget):
            if mutant["pool"] == "released":
                released += 1
            else:
                own += 1
    return released, own, released + own


def pool_sizes(seed_result):
    released = sum(1 for mutant in seed_result["mutants"] if mutant["pool"] == "released")
    return released, len(seed_result["mutants"]) - released


def measure_every_point():
    """One row per (profile, seed, budget)."""
    points = []
    for profile in PROFILES:
        for seed in SEEDS:
            seed_result = runner.load_seed_result(profile, seed)
            released_total, own_total = pool_sizes(seed_result)
            for budget in BUDGETS:
                released, own, both = found_counts(seed_result, budget)
                points.append({
                    "profile": profile, "seed": seed, "budget": budget,
                    "cross": runner.coverage_at(seed_result, budget, "cross"),
                    "total_coverage": runner.coverage_at(seed_result, budget, "coverage"),
                    "released_found": released, "released_total": released_total,
                    "own_found": own, "own_total": own_total,
                    "all_found": both, "all_total": released_total + own_total,
                })
    return points


def summarize_by_budget(points):
    """Mean, min and max over seeds for each (profile, budget)."""
    table = {}
    for profile in PROFILES:
        rows = []
        for budget in BUDGETS:
            group = [point for point in points if point["profile"] == profile and point["budget"] == budget]
            row = {"budget": budget, "released_total": group[0]["released_total"],
                   "all_total": group[0]["all_total"]}
            for column in ("cross", "total_coverage", "released_found", "own_found", "all_found"):
                values = [point[column] for point in group]
                row[column] = {"mean": round(stats.mean(values), 3), "min": min(values), "max": max(values)}
            rows.append(row)
        table[profile] = rows
    return table


def per_seed_timing(profile):
    """For each seed: cycle of the last new find, and when the cross first hit 100%."""
    timing = []
    for seed in SEEDS:
        seed_result = runner.load_seed_result(profile, seed)
        caught = [mutant for mutant in seed_result["mutants"] if mutant["verdict"] in runner.FOUND_VERDICTS]
        last_find = max(mutant["first_failure_cycle"] for mutant in caught) if caught else None
        cross_closed_at = None
        for point in seed_result["clean_run"]["coverage_curve"]:
            if point["cross"] >= 100.0:
                cross_closed_at = point["cycles"]
                break
        finds_after_closure = 0
        if cross_closed_at is not None:
            finds_after_closure = sum(1 for mutant in caught if mutant["first_failure_cycle"] > cross_closed_at)
        timing.append({"seed": seed, "last_new_find_cycle": last_find,
                       "cross_first_100_at_budget": cross_closed_at,
                       "finds_after_cross_closed": finds_after_closure,
                       "caught_at_longest_budget": len(caught)})
    return timing


def median_detection_cycle(profile):
    """Median CRV cycle of first failure over every (seed, found mutant) pair,
    overall and per bug class (released mutants carry the class 'released')."""
    cycles_by_class = {}
    for seed in SEEDS:
        for mutant in runner.load_seed_result(profile, seed)["mutants"]:
            if mutant["verdict"] in runner.FOUND_VERDICTS:
                cycles_by_class.setdefault(mutant["class"], []).append(mutant["first_failure_cycle"])
    every_cycle = [cycle for cycles in cycles_by_class.values() for cycle in cycles]
    return {"all_found": stats.percentile(every_cycle, 0.5),
            "by_class": {name: stats.percentile(cycles, 0.5) for name, cycles in sorted(cycles_by_class.items())}}


def never_found(profile):
    """Mutants no seed of this profile finds, with the crosses still open at the end."""
    seed_results = [runner.load_seed_result(profile, seed) for seed in SEEDS]
    longest = max(BUDGETS)
    ids = [mutant["id"] for mutant in seed_results[0]["mutants"]]
    missed = [mutant_id for mutant_id in ids
              if not any(runner.is_found_within(next(m for m in result["mutants"] if m["id"] == mutant_id), longest)
                         for result in seed_results)]
    final_point = seed_results[0]["clean_run"]["coverage_curve"][-1]
    open_crosses = {name: percent for name, percent in final_point.get("each_cross", {}).items() if percent < 100}
    return {"mutants": missed, "open_crosses_seed1_at_longest_budget": open_crosses}


def draw_curves(table, timing):
    """Both curves on one budget axis, one panel per profile, with the cycle of
    the last new find (over every seed) marked."""
    figure, panels = plt.subplots(1, 2, figsize=(7.2, 3.1), dpi=150, sharey=True)
    for panel, profile in zip(panels, PROFILES):
        rows = table[profile]
        all_total = rows[0]["all_total"]
        released_total = rows[0]["released_total"]
        cross_mean = [row["cross"]["mean"] for row in rows]
        cross_low = [row["cross"]["min"] for row in rows]
        cross_high = [row["cross"]["max"] for row in rows]
        released_mean = [100 * row["released_found"]["mean"] / released_total for row in rows]
        all_mean = [100 * row["all_found"]["mean"] / all_total for row in rows]
        all_low = [100 * row["all_found"]["min"] / all_total for row in rows]
        all_high = [100 * row["all_found"]["max"] / all_total for row in rows]
        color = "#c0392b"
        last_new_find = max(row["last_new_find_cycle"] for row in timing[profile])

        panel.fill_between(BUDGETS, cross_low, cross_high, color=color, alpha=0.15, lw=0)
        panel.plot(BUDGETS, cross_mean, "-o", color=color, ms=3, lw=1.2, label="cross coverage")
        panel.fill_between(BUDGETS, all_low, all_high, color="black", alpha=0.08, lw=0)
        panel.plot(BUDGETS, all_mean, "--s", color="black", ms=3, lw=1.0,
                   label=f"found/total, all {all_total}")
        panel.plot(BUDGETS, released_mean, ":^", color="#2980b9", ms=3, lw=1.0,
                   label=f"found/total, released {released_total}")
        panel.set_xscale("log", base=2)
        panel.set_xticks(BUDGETS)
        panel.set_xticklabels([str(budget) for budget in BUDGETS], fontsize=7)
        panel.set_ylim(0, 103)
        panel.set_title(PROFILE_LABELS[profile], fontsize=9)
        panel.set_xlabel("stimulus budget (CRV cycles)", fontsize=8)
        panel.axvline(last_new_find, color="#555555", lw=0.8, ls="-.")
        panel.text(last_new_find * 1.08, 4, f"last new find,\nany seed: cycle {last_new_find}",
                   fontsize=6.5, color="#555555")
        panel.grid(alpha=0.3, lw=0.4)
    panels[0].set_ylabel("percent (mean over 5 seeds; band = min..max)", fontsize=7.5)
    handles, labels = panels[0].get_legend_handles_labels()
    figure.legend(handles, labels, fontsize=7, frameon=False, loc="lower center", ncol=3)
    figure.tight_layout(rect=(0, 0.07, 1, 1))
    for extension in ("png", "pdf"):
        figure.savefig(os.path.join(FIGURES_FOLDER, f"q1_curves.{extension}"))


def draw_scatter(points):
    figure, axes = plt.subplots(figsize=(4.6, 2.8), dpi=150)
    for profile in PROFILES:
        for seed in SEEDS:
            line = [point for point in points if point["profile"] == profile and point["seed"] == seed]
            axes.plot([point["cross"] for point in line], [point["all_found"] for point in line], "-o",
                      ms=2.5, lw=0.8, alpha=0.75, color=PROFILE_COLORS[profile],
                      label=PROFILE_LABELS[profile] if seed == SEEDS[0] else None)
    axes.set_xlabel("cross coverage (%) at the budget", fontsize=8)
    axes.set_ylabel("mutants found (of 32)", fontsize=8)
    axes.set_title("One line per seed, budgets 50..3,200 cycles", fontsize=8.5)
    axes.legend(fontsize=7, frameon=False)
    axes.grid(alpha=0.3, lw=0.4)
    figure.tight_layout()
    for extension in ("png", "pdf"):
        figure.savefig(os.path.join(FIGURES_FOLDER, f"q1_scatter.{extension}"))


def write_markdown_table(table, summary):
    lines = ["# Q1 -- does closing coverage track finding bugs? (Brandon Zabawa)", "",
             "Mean over seeds 1-5 (min..max in brackets). Found counts are out of 8 released and 32 total.", "",
             "| profile | budget | cross % | total % | released found | all found |",
             "|---|---:|---:|---:|---:|---:|"]
    for profile in PROFILES:
        for row in table[profile]:
            def cell(column):
                values = row[column]
                return f"{values['mean']:.2f} [{values['min']}..{values['max']}]"
            lines.append(f"| {profile} | {row['budget']} | {cell('cross')} | {cell('total_coverage')} | "
                         f"{cell('released_found')} | {cell('all_found')} |")
    lines += ["", f"Pearson r (cross vs all found, every point): {summary['pearson_cross_vs_all_found']}",
              f"Spearman rho: {summary['spearman_cross_vs_all_found']}", ""]
    with open(os.path.join(RESULTS_FOLDER, "q1_table.md"), "w") as table_file:
        table_file.write("\n".join(lines) + "\n")


def main():
    os.makedirs(RESULTS_FOLDER, exist_ok=True)
    os.makedirs(FIGURES_FOLDER, exist_ok=True)
    points = measure_every_point()
    table = summarize_by_budget(points)

    crosses = [point["cross"] for point in points]
    all_found = [point["all_found"] for point in points]
    released_found = [point["released_found"] for point in points]
    summary = {
        "question": "Q1: Does closing coverage track finding bugs?",
        "owner": SETTINGS["owner"],
        "profiles": PROFILES, "seeds": SEEDS, "budgets": BUDGETS,
        "point_count": len(points),
        "pearson_cross_vs_all_found": round(stats.pearson(crosses, all_found), 3),
        "spearman_cross_vs_all_found": round(stats.spearman(crosses, all_found), 3),
        "spearman_cross_vs_released_found": round(stats.spearman(crosses, released_found), 3),
        "table": table,
        "timing": {profile: per_seed_timing(profile) for profile in PROFILES},
        "never_found": {profile: never_found(profile) for profile in PROFILES},
        "median_detection_cycle": {profile: median_detection_cycle(profile) for profile in PROFILES},
        "points": points,
    }
    with open(os.path.join(RESULTS_FOLDER, "q1_summary.json"), "w") as summary_file:
        json.dump(summary, summary_file, indent=1)
    write_markdown_table(table, summary)
    draw_curves(table, summary["timing"])
    draw_scatter(points)

    printable = {key: value for key, value in summary.items() if key not in ("points", "table")}
    print(json.dumps(printable, indent=1))
    print(open(os.path.join(RESULTS_FOLDER, "q1_table.md")).read())


if __name__ == "__main__":
    main()
