#!/usr/bin/env python3
"""Write docs/numbers.tex: every measured number REPORT.tex prints, as LaTeX
macros, so no number in the report is typed by hand.

Inputs (all produced by scripts in extension/):
  extension/results/stimulus_distribution.json   histogram + corner bound
  extension/results/q1_summary.json              Q1, Brandon
  extension/results/q2_summary.json              Q2, Leo
  extension/results/crosscheck.json              method vs course harness

    python3 docs/make_numbers.py
"""
import json
import os

DOCS_FOLDER = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(DOCS_FOLDER)
RESULTS = os.path.join(REPO_ROOT, "extension", "results")


def load(name):
    return json.load(open(os.path.join(RESULTS, name)))


def as_count(value):
    """12.0 -> '12', 17.5 -> '17.5', 12.35 -> '12.35'."""
    return f"{float(value):.2f}".rstrip("0").rstrip(".")


macros = {}

# ---- stimulus distribution (graduate extension parts 1 and 2) ----
distribution = load("stimulus_distribution.json")
macros["HistShpEmpty"] = f"{distribution['hist_v4']['fraction'][0]:.3f}"
macros["HistShpFull"] = f"{distribution['hist_v4']['fraction'][-1]:.3f}"
macros["HistUniEmpty"] = f"{distribution['hist_v1']['fraction'][0]:.3f}"
macros["HistUniFull"] = f"{distribution['hist_v1']['fraction'][-1]:.3f}"
macros["HistChainGap"] = f"{distribution['largest_gap_measured_vs_chain_v4']:.3f}"
corner = distribution["corner_full_and_simul"]
macros["CornerShpNreset"] = str(corner["v4"]["draws_to_99_from_reset"])
macros["CornerUniSixHundred"] = f"{corner['uniform']['from_reset']['600']:.3f}"
any_start = corner["v4"]["bound_99_from_any_start"]
macros["CornerShpNany"] = str(any_start["draws"])
macros["CornerShpL"] = str(any_start["window"])
macros["CornerShpQ"] = f"{any_start['worst_chance']:.4f}"
macros["CornerShpWorst"] = any_start["worst_start"].strip("()").replace("count=", "count ")

# ---- Q1, Brandon: does closing coverage track finding bugs? ----
q1 = load("q1_summary.json")
macros["QoneSpearman"] = f"{q1['spearman_cross_vs_all_found']:.2f}"
macros["QonePearson"] = f"{q1['pearson_cross_vs_all_found']:.2f}"
macros["QonePoints"] = str(q1["point_count"])
v4_timing = q1["timing"]["v4"]
last_finds = [row["last_new_find_cycle"] for row in v4_timing]
macros["QoneVfourLastFindMax"] = str(max(last_finds))
macros["QoneVfourLastFindMin"] = str(min(last_finds))
closures = [row["cross_first_100_at_budget"] for row in v4_timing]
macros["QoneVfourCrossClosedAtOneSixHundred"] = str(sum(1 for budget in closures if budget == 1600))
macros["QoneVfourCrossClosedAtTwentyFiveHundred"] = str(sum(1 for budget in closures if budget == 2500))
macros["QoneVfourCrossClosedAtThreeTwoHundred"] = str(sum(1 for budget in closures if budget == 3200))
macros["QoneVfourCrossClosedLater"] = str(sum(1 for budget in closures if budget is None))
macros["QoneFindsAfterClosure"] = str(sum(row["finds_after_cross_closed"] for row in v4_timing))
macros["QoneVfourCaught"] = str(v4_timing[0]["caught_at_longest_budget"])
macros["QoneVoneCaught"] = str(max(row["caught_at_longest_budget"] for row in q1["timing"]["v1"]))
reachable_misses = [mutant for mutant in q1["never_found"]["v1"]["mutants"]
                    if mutant not in q1["never_found"]["v4"]["mutants"]]
macros["QoneVoneMissed"] = ", ".join(reachable_misses).replace("_", "\\_")
v4_rows = {row["budget"]: row for row in q1["table"]["v4"]}
v1_rows = {row["budget"]: row for row in q1["table"]["v1"]}
macros["QoneVfourCrossAtFourHundred"] = f"{v4_rows[400]['cross']['mean']:.1f}"
macros["QoneVfourCrossAtFifty"] = f"{v4_rows[50]['cross']['mean']:.1f}"
macros["QoneVfourAllAtFifty"] = as_count(v4_rows[50]["all_found"]["mean"])
macros["QoneVoneCrossMax"] = f"{max(row['cross']['max'] for row in q1['table']['v1']):.1f}"
macros["QoneVoneAllAtFifty"] = as_count(v1_rows[50]["all_found"]["mean"])
macros["QoneMedianVone"] = as_count(q1["median_detection_cycle"]["v1"]["all_found"])
macros["QoneMedianVfour"] = as_count(q1["median_detection_cycle"]["v4"]["all_found"])
macros["QoneMedianBoundaryVone"] = as_count(q1["median_detection_cycle"]["v1"]["by_class"].get("boundary", 0))
macros["QoneMedianBoundaryVfour"] = as_count(q1["median_detection_cycle"]["v4"]["by_class"].get("boundary", 0))

# ---- Q2, Leo: how much does the seed matter? ----
q2 = load("q2_summary.json")
macros["QtwoSeeds"] = str(len(q2["seeds"]))
macros["QtwoBudgetShort"] = f"{q2['budgets'][0]:,}"
macros["QtwoBudgetLong"] = f"{q2['budgets'][1]:,}"
macros["QtwoDirectedFind"] = str(q2["directed_tests_alone_find"])
for label, budget in (("Short", str(q2["budgets"][0])), ("Long", str(q2["budgets"][1]))):
    block = q2["by_budget"][budget]
    for view, view_label in (("crv_all", "Crv"), ("suite_all", "Suite"), ("crv_released", "CrvRel"),
                             ("total_coverage", "Cov")):
        described = block["stats"][view]
        prefix = f"Qtwo{label}{view_label}"
        macros[prefix + "Mean"] = f"{described['mean']:.2f}"
        macros[prefix + "Low"] = f"{described['ci95_low']:.2f}"
        macros[prefix + "High"] = f"{described['ci95_high']:.2f}"
        macros[prefix + "Min"] = as_count(described["min"])
        macros[prefix + "Max"] = as_count(described["max"])
        macros[prefix + "Sd"] = f"{described['standard_deviation']:.2f}"
        macros[prefix + "SeedOne"] = as_count(block["sign_off_seed"][view]["score"])
        macros[prefix + "SeedOneHigher"] = str(block["sign_off_seed"][view]["seeds_higher"])
        macros[prefix + "SeedOneLower"] = str(block["sign_off_seed"][view]["seeds_lower"])
    macros[f"Qtwo{label}SeedsClosing"] = str(block["seeds_closing_100_percent"])
    macros[f"Qtwo{label}SeedDependent"] = str(len(block["mutants_that_depend_on_the_seed"]))
agree = q2["every_seed_agrees_from_budget"]
macros["QtwoCrvAgreeFrom"] = f"{agree['crv_all']:,}" if agree["crv_all"] else "never"
macros["QtwoSuiteAgreeFrom"] = f"{agree['suite_all']:,}" if agree["suite_all"] else "never"

# ---- method check against the course harness ----
crosscheck = load("crosscheck.json")
check_a = crosscheck["check_a_prefix_claim"]["budgets"]
macros["CrossAagree"] = str(sum(block["agree"] for block in check_a.values()))
macros["CrossAtotal"] = str(sum(block["mutants_compared"] for block in check_a.values()))
check_b = crosscheck["check_b_whole_suite"]
macros["CrossBagree"] = str(check_b["agree"])
macros["CrossBtotal"] = str(check_b["mutants_compared"])

with open(os.path.join(DOCS_FOLDER, "numbers.tex"), "w") as numbers_file:
    numbers_file.write("% generated by docs/make_numbers.py -- do not edit by hand\n")
    for name, value in macros.items():
        numbers_file.write("\\newcommand{\\%s}{%s}\n" % (name, value))
for name, value in macros.items():
    print(f"{name:40s} {value}")
