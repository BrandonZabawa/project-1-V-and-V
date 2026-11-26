#!/usr/bin/env python3
"""Graduate extension, parts 1 and 2: the distribution the constraints induce.

  1. Occupancy histogram of the sign-off constraints (profile v4) against the
     uniform baseline (profile v1), measured over 5 seeds x 2,500 cycles and
     predicted by the exact Markov chain (chain.py).
  2. A constraint that reaches a named corner (full, with a read and a write
     requested together) with probability above p = 0.99 within N draws:
     from reset, and from the worst possible starting state.

Input : results/convergence/occupancy.json   (written by crv/regress.py --convergence)
Output: extension/results/stimulus_distribution.json
        extension/figures/occupancy_hist.png (and .pdf)

    python3 extension/stimulus_distribution.py
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

EXTENSION_FOLDER = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(EXTENSION_FOLDER)
sys.path.insert(0, EXTENSION_FOLDER)
import chain  # noqa: E402

DEPTH = 8
TARGET_PROBABILITY = 0.99
RESULTS_FOLDER = os.path.join(EXTENSION_FOLDER, "results")
FIGURES_FOLDER = os.path.join(EXTENSION_FOLDER, "figures")


def v4_reset_chance(occupancy, depth):
    """Same reset policy as crv/sequences.py, profile v4."""
    return 1 / 30 if occupancy in (0, depth) else 1 / 120


def measured_occupancy(profile):
    """Pooled fraction of cycles at each occupancy, plus per-seed boundary mass."""
    occupancy_file = os.path.join(REPO_ROOT, "results", "convergence", "occupancy.json")
    runs = [run for run in json.load(open(occupancy_file))["runs"] if run["profile"] == profile]
    pooled = np.sum([run["counts"] for run in runs], axis=0)
    total = pooled.sum()
    return {
        "fraction": [round(float(count / total), 4) for count in pooled],
        "cycles": int(total),
        "empty_per_seed": [round(run["counts"][0] / sum(run["counts"]), 3) for run in runs],
        "full_per_seed": [round(run["counts"][DEPTH] / sum(run["counts"]), 3) for run in runs],
    }


def total_variation_from_flat(fractions):
    flat = 1 / (DEPTH + 1)
    return round(0.5 * sum(abs(fraction - flat) for fraction in fractions), 4)


def draw_histogram(numbers):
    figure, axes = plt.subplots(figsize=(6, 3), dpi=150)
    levels = np.arange(DEPTH + 1)
    bar_width = 0.38
    axes.bar(levels - bar_width / 2, numbers["hist_v4"]["fraction"], bar_width, color="#c0392b",
             label="v4 (sign-off constraints), measured")
    axes.bar(levels + bar_width / 2, numbers["hist_v1"]["fraction"], bar_width, color="#7f8c8d",
             label="v1 (uniform), measured")
    axes.plot(levels, numbers["chain_v4"], "k^--", ms=4, lw=0.8, label="v4, exact chain")
    axes.plot(levels, numbers["chain_uniform"], "ko:", ms=3, lw=0.8, label="uniform, exact chain")
    axes.axhline(1 / (DEPTH + 1), color="#2980b9", lw=0.8, ls="-.", label="flat (1/9)")
    axes.set_ylim(0, 0.29)
    axes.set_xticks(levels)
    axes.set_xlabel("occupancy after the edge")
    axes.set_ylabel("fraction of cycles")
    axes.set_title("Occupancy induced by the constraints, 5 seeds x 2,500 cycles", fontsize=9)
    axes.legend(fontsize=6.5, ncol=2, frameon=False, loc="upper center")
    figure.tight_layout()
    for extension in ("png", "pdf"):
        figure.savefig(os.path.join(FIGURES_FOLDER, f"occupancy_hist.{extension}"))


def corner_bound(matrix):
    """P(corner within N) from reset, and the smallest N that is safe from ANY start."""
    from_reset = chain.chance_of_hit_by_step(matrix, start_state=0, steps=600)
    reaches_target = from_reset >= TARGET_PROBABILITY
    result = {
        "from_reset": {steps: round(float(from_reset[steps - 1]), 4)
                       for steps in (25, 50, 100, 200, 300, 400, 600)},
        "draws_to_99_from_reset": int(np.argmax(reaches_target) + 1) if reaches_target.any() else None,
    }
    # Split a run into windows of L draws. If q_L is the worst-start chance of
    # a hit inside one window, then P(hit within N) >= 1 - (1 - q_L)^floor(N/L)
    # from any start. Search L for the smallest such N.
    best = None
    for window in range(10, 301, 5):
        worst_chance, worst_state = chain.worst_start_chance(matrix, window)
        for draws in range(window, 4001):
            if 1 - (1 - worst_chance) ** (draws // window) > TARGET_PROBABILITY:
                if best is None or draws < best["draws"]:
                    best = {"draws": draws, "window": window, "worst_chance": round(float(worst_chance), 4),
                            "worst_start": chain.state_name(worst_state)}
                break
    result["bound_99_from_any_start"] = best
    return result


def main():
    os.makedirs(RESULTS_FOLDER, exist_ok=True)
    os.makedirs(FIGURES_FOLDER, exist_ok=True)
    numbers = {}

    # ---- 1. occupancy histogram ----
    shaped_chain = chain.build_transition_matrix(DEPTH, "shaped", 0.05, v4_reset_chance)
    uniform_chain = chain.build_transition_matrix(DEPTH, "uniform")
    for profile in ("v1", "v4"):
        numbers[f"hist_{profile}"] = measured_occupancy(profile)
    numbers["chain_v4"] = chain.long_run_occupancy(shaped_chain, DEPTH).round(4).tolist()
    numbers["chain_uniform"] = chain.long_run_occupancy(uniform_chain, DEPTH).round(4).tolist()
    for profile in ("v1", "v4"):
        numbers[f"total_variation_from_flat_{profile}"] = \
            total_variation_from_flat(numbers[f"hist_{profile}"]["fraction"])
    numbers["largest_gap_measured_vs_chain_v4"] = round(max(
        abs(measured - predicted)
        for measured, predicted in zip(numbers["hist_v4"]["fraction"], numbers["chain_v4"])), 4)
    draw_histogram(numbers)

    # ---- 2. corner: full, with a read and a write requested together ----
    def full_with_read_and_write(occupancy, write_enable, read_enable):
        return occupancy == DEPTH and write_enable == 1 and read_enable == 1

    numbers["corner_full_and_simul"] = {
        "v4": corner_bound(chain.build_transition_matrix(
            DEPTH, "shaped", 0.05, v4_reset_chance, corner=full_with_read_and_write)),
        "uniform": corner_bound(chain.build_transition_matrix(
            DEPTH, "uniform", corner=full_with_read_and_write)),
    }

    with open(os.path.join(RESULTS_FOLDER, "stimulus_distribution.json"), "w") as output_file:
        json.dump(numbers, output_file, indent=1)
    print(json.dumps(numbers, indent=1))


if __name__ == "__main__":
    main()
