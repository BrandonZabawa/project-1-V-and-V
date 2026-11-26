#!/usr/bin/env python3
"""Seeded regression runner. The seed list and these command lines are the
source of truth for every coverage number in the report.

    python3 crv/regress.py                      # sign-off: profile v4, seeds in crv/seeds.txt
    python3 crv/regress.py --convergence        # profiles v1..v4 on seeds 1-5 (closure history)
    python3 crv/regress.py --profile v2 --seeds 1,2,3 --cycles 4000

Each run is one `make SIM=icarus` with SEED, PROFILE, CYCLES and COV_OUT set.
Its log goes to results/<mode>/<profile>/seed_<n>.log and its coverage to
seed_<n>.yml (both regenerable, so .gitignore keeps them out of the repo).
Two small files ARE committed:
  results/<mode>/summary.md       per-seed results and merged coverage per profile
  results/<mode>/occupancy.json   occupancy counts per seed (the histogram's input)
The exit status is non-zero if any run fails.
"""
import argparse
import concurrent.futures as futures
import json
import os
import re
import subprocess
import sys

import yaml

CRV_FOLDER = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(CRV_FOLDER)
sys.path.insert(0, REPO_ROOT)
from coverage_model.model import ITEMS  # noqa: E402

CONVERGENCE_PROFILES = ["v1", "v2", "v3", "v4"]
CONVERGENCE_SEEDS = [1, 2, 3, 4, 5]


def run_one_seed(profile, seed, cycles, output_folder):
    """Run the constrained-random test once and pull its numbers out of the log."""
    os.makedirs(output_folder, exist_ok=True)
    log_path = os.path.join(output_folder, f"seed_{seed}.log")
    coverage_path = os.path.join(output_folder, f"seed_{seed}.yml")
    build_folder = os.path.join(output_folder, f"sim_build_{seed}")
    results_file = os.path.join(output_folder, f"results_{seed}.xml")

    environment = dict(os.environ, SEED=str(seed), PROFILE=profile, CYCLES=str(cycles),
                       COV_OUT=coverage_path, COV_GATE="0")
    command = ["make", "-s", "-C", REPO_ROOT, "SIM=icarus", f"SIM_BUILD={build_folder}",
               f"COCOTB_RESULTS_FILE={results_file}", "TESTCASE=test_t3_crv_signoff"]
    output = subprocess.run(command, env=environment, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT).stdout.decode()

    with open(log_path, "w") as log_file:
        log_file.write(" ".join(command) + "\n")
        log_file.write(f"SEED={seed}\nPROFILE={profile}\nCYCLES={cycles}\n")
        log_file.write(output)
    subprocess.run(["rm", "-rf", build_folder, results_file])

    passed = "FAIL=0" in output and "TESTS=1" in output
    total_coverage = re.search(r"COVER TOTAL ([\d.]+)%", output)
    occupancy_line = re.search(r"OCC  (.*?)   empty ([\d.]+) full ([\d.]+)", output)
    digest = re.search(r"digest=([0-9a-f]+)", output)

    occupancy_counts = None
    if occupancy_line:
        occupancy_counts = [int(pair.split(":")[1]) for pair in occupancy_line.group(1).split()]

    return {
        "profile": profile,
        "seed": seed,
        "passed": passed,
        "coverage": float(total_coverage.group(1)) if total_coverage else None,
        "empty_mass": float(occupancy_line.group(2)) if occupancy_line else None,
        "full_mass": float(occupancy_line.group(3)) if occupancy_line else None,
        "occupancy_counts": occupancy_counts,
        "digest": digest.group(1) if digest else None,
        "coverage_file": coverage_path,
    }


def merge_coverage(coverage_files):
    """Union of bin hits across runs. Returns {item: (covered, size, holes)}."""
    hits_per_item = {}
    for path in coverage_files:
        if not os.path.exists(path):
            continue
        database = yaml.safe_load(open(path))
        for name in ITEMS:
            node = database.get(name)
            if not node or "bins:_hits" not in node:
                continue
            item_hits = hits_per_item.setdefault(name, {})
            for bin_name, hit_count in node["bins:_hits"].items():
                item_hits[bin_name] = item_hits.get(bin_name, 0) + hit_count

    merged = {}
    for name in ITEMS:
        item_hits = hits_per_item.get(name, {})
        covered = sum(1 for count in item_hits.values() if count > 0)
        holes = [bin_name for bin_name, count in item_hits.items() if count == 0]
        merged[name] = (covered, len(item_hits), holes)
    return merged


def write_summary(mode, cycles, profiles, results, output_folder):
    lines = [f"# Regression `{mode}` -- {cycles} cycles per run, Icarus", "",
             "Command: `python3 crv/regress.py " + " ".join(sys.argv[1:]) + "`", "",
             "| profile | seed | pass | coverage % | empty mass | full mass | stimulus digest |",
             "|---|---:|---|---:|---:|---:|---|"]
    for run in results:
        lines.append(f"| {run['profile']} | {run['seed']} | {'yes' if run['passed'] else 'NO'} | "
                     f"{run['coverage']} | {run['empty_mass']} | {run['full_mass']} | `{run['digest']}` |")

    lines += ["", "## Merged coverage per profile (union over seeds)", ""]
    for profile in profiles:
        profile_runs = [run for run in results if run["profile"] == profile]
        merged = merge_coverage([run["coverage_file"] for run in profile_runs])
        covered = sum(item[0] for item in merged.values())
        size = sum(item[1] for item in merged.values())
        if size:
            lines.append(f"### {profile}: {covered}/{size} bins = {100.0 * covered / size:.2f}%")
        else:
            lines.append(f"### {profile}: no data")
        lines += ["", "| item | covered | holes |", "|---|---:|---|"]
        for name, (item_covered, item_size, holes) in merged.items():
            shown = ", ".join(str(hole) for hole in holes[:6]) + (" ..." if len(holes) > 6 else "")
            lines.append(f"| `{name}` | {item_covered}/{item_size} | {shown} |")
        lines.append("")
        per_seed = [run["coverage"] for run in profile_runs if run["coverage"] is not None]
        closed_alone = sum(1 for value in per_seed if value >= 100.0)
        lines += [f"Seeds closing 100% on their own: **{closed_alone}/{len(per_seed)}**", ""]

    with open(os.path.join(output_folder, "summary.md"), "w") as summary_file:
        summary_file.write("\n".join(lines) + "\n")
    print("\n".join(lines))


def write_occupancy(cycles, results, output_folder):
    occupancy = {"cycles_per_run": cycles, "runs": [
        {"profile": run["profile"], "seed": run["seed"], "counts": run["occupancy_counts"]}
        for run in results]}
    with open(os.path.join(output_folder, "occupancy.json"), "w") as occupancy_file:
        json.dump(occupancy, occupancy_file, indent=1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--convergence", action="store_true")
    parser.add_argument("--profile", default="v4")
    parser.add_argument("--seeds", default=None, help="comma-separated, e.g. 1,2,3")
    parser.add_argument("--cycles", type=int, default=2500)
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--mode", default=None, help="output folder name under results/")
    args = parser.parse_args()

    if args.convergence:
        profiles, seeds = CONVERGENCE_PROFILES, CONVERGENCE_SEEDS
        mode = args.mode or "convergence"
    else:
        if args.seeds:
            seeds = [int(text) for text in args.seeds.split(",")]
        else:
            seeds = [int(text) for text in open(os.path.join(CRV_FOLDER, "seeds.txt")).read().split()]
        profiles = [args.profile]
        mode = args.mode or "signoff"

    output_folder = os.path.join(REPO_ROOT, "results", mode)
    jobs = [(profile, seed) for profile in profiles for seed in seeds]
    with futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        results = list(pool.map(
            lambda job: run_one_seed(job[0], job[1], args.cycles, os.path.join(output_folder, job[0])),
            jobs))

    write_summary(mode, args.cycles, profiles, results, output_folder)
    write_occupancy(args.cycles, results, output_folder)
    sys.exit(0 if all(run["passed"] for run in results) else 1)


if __name__ == "__main__":
    main()
