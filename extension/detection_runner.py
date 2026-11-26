#!/usr/bin/env python3
"""Shared measurement engine for the graduate extension (Q1 and Q2).

For one (profile, seed) it answers two questions:
  * How does coverage grow? One clean run records total and cross coverage at
    every checkpoint in config.json ("coverage_checkpoints").
  * When is each mutant caught? One run per mutant records the constrained-
    random (CRV) cycle of the first failing check, or that nothing failed.

Why one long run is enough for every budget
-------------------------------------------
Study mode (STUDY=1 in test_fifo_p1.py) has no final drain and no gates, so a
run with budget B is a cycle-for-cycle prefix of the longest run with the
same seed and the same DUT. A mutant is therefore found at budget B exactly
when its first failure happens at a CRV cycle <= B. crosscheck_with_harness.py
confirms this against the course harness itself.

Only the constrained-random test runs here, because only it depends on the
seed and the budget. The two directed tests are measured once per mutant by
`measure_directed_tests()`; Q2 adds them back to score the whole suite.

Output (committed; one small JSON per seed):
  extension/data/<profile>/seed_<n>.json
  extension/data/directed_tests.json
Per-mutant scratch files go to a temporary folder that is deleted afterwards.

    python3 extension/detection_runner.py --profile v4 --seeds 1-20
    python3 extension/detection_runner.py --profile v1 --seeds 1-5
    python3 extension/detection_runner.py --directed-only
"""
import argparse
import concurrent.futures as futures
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

import yaml

EXTENSION_FOLDER = os.path.dirname(os.path.abspath(__file__))
SETTINGS = json.load(open(os.path.join(EXTENSION_FOLDER, "config.json")))
DATA_FOLDER = os.path.join(EXTENSION_FOLDER, "data")

FOUND_VERDICTS = ("found", "build/crash", "hang")


# ------------------------------------------------------------------ locations
def packet_code_folder():
    """The packet's code/ folder (holds dut/ and lib/). CRAFT_CODE overrides it."""
    default = os.path.join(EXTENSION_FOLDER, SETTINGS["packet_code_folder"])
    return os.path.abspath(os.environ.get("CRAFT_CODE", default))


def suite_folder():
    return os.path.abspath(os.path.join(EXTENSION_FOLDER, SETTINGS["suite_folder"]))


def clean_dut_path():
    return os.path.join(packet_code_folder(), "dut", "fifo.sv")


def load_all_mutants():
    """[(pool name, mutant dict)] for every pool listed in config.json."""
    mutants = []
    for pool_name, relative_path in SETTINGS["mutant_pools"].items():
        pool = yaml.safe_load(open(os.path.join(EXTENSION_FOLDER, relative_path)))
        for mutant in pool["mutants"]:
            mutants.append((pool_name, mutant))
    return mutants


def write_mutated_dut(mutant, folder):
    """Apply one find/replace to the clean DUT, the same way the harness does."""
    clean_source = open(clean_dut_path()).read()
    assert clean_source.count(mutant["find"]) == 1, f"{mutant['id']}: find-string must occur once"
    mutated_path = os.path.join(folder, mutant["id"], "fifo.sv")
    os.makedirs(os.path.dirname(mutated_path), exist_ok=True)
    with open(mutated_path, "w") as mutated_file:
        mutated_file.write(clean_source.replace(mutant["find"], mutant["replace"], 1))
    return mutated_path


# ---------------------------------------------------------------- one sim run
def run_simulation(dut_path, extra_environment, timeout_seconds):
    """One `make SIM=icarus` of the suite against `dut_path`.
    Returns (passed, output_text, wall_seconds)."""
    build_folder = tempfile.mkdtemp(prefix="study_build_")
    results_file = os.path.join(build_folder, "results.xml")
    environment = dict(os.environ, **extra_environment)
    environment["PYTHONPATH"] = os.path.join(packet_code_folder(), "lib") + os.pathsep + suite_folder()
    command = ["make", "-s", "-C", suite_folder(), "SIM=icarus", f"DUT={dut_path}",
               f"SIM_BUILD={build_folder}", f"COCOTB_RESULTS_FILE={results_file}"]

    started = time.time()
    try:
        finished = subprocess.run(command, env=environment, timeout=timeout_seconds,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        output = finished.stdout.decode(errors="replace")
        passed = finished.returncode == 0 and "FAIL=0" in output
    except subprocess.TimeoutExpired:
        output, passed = "TIMEOUT", False
    wall_seconds = round(time.time() - started, 2)
    shutil.rmtree(build_folder, ignore_errors=True)
    return passed, output, wall_seconds


def run_study_mode(dut_path, profile, seed, scratch_json):
    """Run only the CRV test in study mode; return (study record or None, output, wall)."""
    checkpoints = SETTINGS["coverage_checkpoints"]
    study_environment = {
        "STUDY": "1", "STUDY_OUT": scratch_json, "SEED": str(seed), "PROFILE": profile,
        "CHECKPOINTS": ",".join(str(cycles) for cycles in checkpoints),
        "COV_GATE": "0", "TESTCASE": "test_t3_crv_signoff",
    }
    if os.path.exists(scratch_json):
        os.remove(scratch_json)
    _, output, wall_seconds = run_simulation(dut_path, study_environment,
                                             SETTINGS["run_timeout_seconds"])
    record = json.load(open(scratch_json)) if os.path.exists(scratch_json) else None
    return record, output, wall_seconds


# ------------------------------------------------------------ one whole seed
def measure_one_mutant(pool_name, mutant, profile, seed, scratch):
    """Run one mutant in study mode and turn the outcome into a data row."""
    mutated_dut = write_mutated_dut(mutant, scratch)
    record, output, wall = run_study_mode(mutated_dut, profile, seed,
                                          os.path.join(scratch, f"{mutant['id']}.json"))
    if record is None:
        # No study file: the mutant broke the build, crashed, or hung. The
        # harness counts all three as found, before any CRV cycle.
        verdict = "hang" if output == "TIMEOUT" else "build/crash"
        first_failure_cycle, message = 0, output[-200:]
    elif record["fail"] is None:
        verdict, first_failure_cycle, message = "survived", None, ""
    else:
        verdict = "found"
        first_failure_cycle = record["fail"]["cycle"]
        message = record["fail"]["msg"][:200]
    return {"pool": pool_name, "id": mutant["id"], "class": mutant.get("class", "released"),
            "verdict": verdict, "first_failure_cycle": first_failure_cycle,
            "message": message, "wall_seconds": wall}


def remeasure_some_mutants(profile, seed, mutant_ids):
    """Re-run only the named mutants for a seed that was already measured, and
    replace their rows in place (used after a fix to the suite's study mode)."""
    output_path = os.path.join(DATA_FOLDER, profile, f"seed_{seed}.json")
    measured = json.load(open(output_path))
    scratch = tempfile.mkdtemp(prefix=f"study_{profile}_{seed}_")
    for pool_name, mutant in load_all_mutants():
        if mutant["id"] in mutant_ids:
            new_row = measure_one_mutant(pool_name, mutant, profile, seed, scratch)
            measured["mutants"] = [new_row if row["id"] == mutant["id"] else row
                                   for row in measured["mutants"]]
    shutil.rmtree(scratch, ignore_errors=True)
    with open(output_path, "w") as output_file:
        json.dump(measured, output_file, indent=1)
    changed = [row for row in measured["mutants"] if row["id"] in mutant_ids]
    return f"{profile} seed {seed}: re-measured " + ", ".join(
        f"{row['id']}={row['verdict']}@{row['first_failure_cycle']}" for row in changed)


def measure_one_seed(profile, seed, force=False):
    """Clean run plus one run per mutant for this (profile, seed)."""
    output_path = os.path.join(DATA_FOLDER, profile, f"seed_{seed}.json")
    if os.path.exists(output_path) and not force:
        return f"{profile} seed {seed}: already measured (use --force to redo)"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    scratch = tempfile.mkdtemp(prefix=f"study_{profile}_{seed}_")

    clean_record, clean_output, clean_wall = run_study_mode(
        clean_dut_path(), profile, seed, os.path.join(scratch, "clean.json"))
    if not clean_record or clean_record["fail"] is not None:
        print(clean_output[-2000:])
        raise RuntimeError(f"the clean DUT failed for {profile} seed {seed}; fix the suite first")

    measured = {
        "profile": profile,
        "seed": seed,
        "coverage_checkpoints": SETTINGS["coverage_checkpoints"],
        "clean_run": {"coverage_curve": clean_record["curve"], "wall_seconds": clean_wall},
        "mutants": [],
    }

    for pool_name, mutant in load_all_mutants():
        measured["mutants"].append(measure_one_mutant(pool_name, mutant, profile, seed, scratch))

    shutil.rmtree(scratch, ignore_errors=True)
    with open(output_path, "w") as output_file:
        json.dump(measured, output_file, indent=1)
    caught = sum(1 for row in measured["mutants"] if row["verdict"] in FOUND_VERDICTS)
    return f"{profile} seed {seed}: {caught}/{len(measured['mutants'])} caught within the longest budget"


# --------------------------------------------------- directed tests (no seed)
def measure_directed_tests():
    """T1 and T2 use no randomness, so each mutant needs only one run of them."""
    output_path = os.path.join(DATA_FOLDER, "directed_tests.json")
    os.makedirs(DATA_FOLDER, exist_ok=True)
    scratch = tempfile.mkdtemp(prefix="directed_")
    directed_environment = {"TESTCASE": "test_t1_directed_smoke,test_t2_security_reset_race"}

    clean_passed, clean_output, _ = run_simulation(clean_dut_path(), directed_environment, 300)
    assert clean_passed and "TESTS=2" in clean_output, "directed tests must pass on the clean DUT"

    results = {}
    for pool_name, mutant in load_all_mutants():
        passed, output, _ = run_simulation(write_mutated_dut(mutant, scratch), directed_environment, 300)
        results[mutant["id"]] = {"pool": pool_name, "found_by_directed_tests": not passed}
    shutil.rmtree(scratch, ignore_errors=True)
    with open(output_path, "w") as output_file:
        json.dump(results, output_file, indent=1)
    found = sum(1 for row in results.values() if row["found_by_directed_tests"])
    return f"directed tests alone: {found}/{len(results)} mutants found"


# ----------------------------------------------------------- reading results
def load_seed_result(profile, seed):
    return json.load(open(os.path.join(DATA_FOLDER, profile, f"seed_{seed}.json")))


def is_found_within(mutant_row, budget):
    """Found at this budget: caught at a CRV cycle <= budget (cycle 0 means
    during the opening reset, a crash, or a build failure)."""
    if mutant_row["verdict"] not in FOUND_VERDICTS:
        return False
    return mutant_row["first_failure_cycle"] <= budget


def coverage_at(seed_result, budget, kind="cross"):
    """Coverage ('cross' or 'coverage' = total) recorded at a checkpoint."""
    for point in seed_result["clean_run"]["coverage_curve"]:
        if point["cycles"] == budget:
            return point[kind]
    raise KeyError(f"budget {budget} is not a coverage checkpoint")


def parse_seed_list(text):
    """'1-5' or '1,2,7' or '1-3,9' -> [1, 2, 3, 9]."""
    seeds = []
    for part in text.split(","):
        if "-" in part:
            first, last = part.split("-")
            seeds += list(range(int(first), int(last) + 1))
        elif part.strip():
            seeds.append(int(part))
    return seeds


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--profile", default="v4")
    parser.add_argument("--seeds", default="1-5")
    parser.add_argument("--jobs", type=int, default=SETTINGS["parallel_jobs"])
    parser.add_argument("--force", action="store_true", help="re-measure seeds that already have data")
    parser.add_argument("--directed-only", action="store_true")
    parser.add_argument("--mutants", default=None,
                        help="comma-separated ids: re-measure only these on seeds already measured")
    args = parser.parse_args()

    if args.directed_only:
        print(measure_directed_tests(), flush=True)
        return 0

    seeds = parse_seed_list(args.seeds)
    if args.mutants:
        mutant_ids = set(args.mutants.split(","))
        work = lambda seed: remeasure_some_mutants(args.profile, seed, mutant_ids)
    else:
        work = lambda seed: measure_one_seed(args.profile, seed, args.force)
    with futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        for message in pool.map(work, seeds):
            print(message, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
