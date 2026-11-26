#!/usr/bin/env python3
"""Check the graduate-study method against the course harness itself.

detection_runner.py reads every budget off ONE long run per mutant (a run with
budget B is a prefix of the longest run). Two checks make sure that shortcut
gives the same verdicts the course harness gives:

  Check A (the prefix claim). Run `python -m craft_mutate.mutate` in study mode
  with the budget actually set to B, for budgets 100 and 800 on one seed.
  Each mutant's harness verdict must equal "first failure <= B" from the data.

  Check B (the whole suite, as graded). Run the harness in its default
  configuration (all three tests, seed 1, 2,500 cycles, final drain, gates).
  Its verdicts must equal "found by the directed tests OR found by the CRV
  test within 2,500 cycles", which is how Q2 scores the whole suite. The
  harness output of this check is also the found/total that FINDINGS.md
  reports, so it is saved under results/mutation/.

    python3 extension/crosscheck_with_harness.py            # both checks, seed 1
    python3 extension/crosscheck_with_harness.py --only A --seed 3

Output: extension/results/crosscheck.json, results/mutation/{released,stress}.{txt,json}
"""
import argparse
import json
import os
import subprocess
import sys

EXTENSION_FOLDER = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(EXTENSION_FOLDER)
sys.path.insert(0, EXTENSION_FOLDER)
import detection_runner as runner  # noqa: E402

RESULTS_FOLDER = os.path.join(EXTENSION_FOLDER, "results")
MUTATION_RESULTS_FOLDER = os.path.join(REPO_ROOT, "results", "mutation")
POOL_FILE_STEMS = {"released": "released", "own": "stress"}
STUDY_BUDGETS_TO_CHECK = (100, 800)
SIGN_OFF_BUDGET = 2500


def run_harness(pool_name, extra_environment, json_path, text_path=None):
    """Run the course harness on one pool. Returns {mutant id: found?}."""
    pool_path = os.path.join(EXTENSION_FOLDER, runner.SETTINGS["mutant_pools"][pool_name])
    environment = dict(os.environ, **extra_environment)
    environment["PYTHONPATH"] = os.path.join(runner.packet_code_folder(), "lib")
    command = [sys.executable, "-m", "craft_mutate.mutate", "--tb", runner.suite_folder(),
               "--dut", runner.clean_dut_path(), "--pool", pool_path, "--sim", "icarus",
               "--json", json_path]
    finished = subprocess.run(command, env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    output = finished.stdout.decode(errors="replace")
    if text_path:
        with open(text_path, "w") as text_file:
            text_file.write(output)
    if not os.path.exists(json_path):
        raise RuntimeError(f"harness wrote no JSON for {pool_name}:\n{output[-1500:]}")
    return {row["id"]: row["found"] for row in json.load(open(json_path))["mutants"]}


def compare(predicted, measured):
    disagreements = [mutant_id for mutant_id in predicted if predicted[mutant_id] != measured[mutant_id]]
    return {"mutants_compared": len(predicted), "agree": len(predicted) - len(disagreements),
            "disagreements": disagreements}


def check_a_prefix_claim(seed, budgets, report, save):
    seed_result = runner.load_seed_result("v4", seed)
    rows_by_id = {row["id"]: row for row in seed_result["mutants"]}
    for budget in budgets:
        study_environment = {"STUDY": "1", "CHECKPOINTS": str(budget), "SEED": str(seed),
                             "PROFILE": "v4", "COV_GATE": "0", "TESTCASE": "test_t3_crv_signoff"}
        measured, predicted = {}, {}
        for pool_name in runner.SETTINGS["mutant_pools"]:
            scratch_json = os.path.join(RESULTS_FOLDER, f"_harness_{pool_name}_{budget}.json")
            measured.update(run_harness(pool_name, study_environment, scratch_json))
            os.remove(scratch_json)
        for mutant_id in measured:
            predicted[mutant_id] = runner.is_found_within(rows_by_id[mutant_id], budget)
        report[str(budget)] = compare(predicted, measured)
        print(f"check A, seed {seed}, budget {budget}: {report[str(budget)]}", flush=True)
        save()                                 # keep each budget's result even if a later one is stopped
    return report


def check_b_whole_suite(seed):
    seed_result = runner.load_seed_result("v4", seed)
    directed = json.load(open(os.path.join(runner.DATA_FOLDER, "directed_tests.json")))
    os.makedirs(MUTATION_RESULTS_FOLDER, exist_ok=True)
    measured, predicted = {}, {}
    for pool_name, stem in POOL_FILE_STEMS.items():
        json_path = os.path.join(MUTATION_RESULTS_FOLDER, f"{stem}.json")
        text_path = os.path.join(MUTATION_RESULTS_FOLDER, f"{stem}.txt")
        measured.update(run_harness(pool_name, {"SEED": str(seed)}, json_path, text_path))
    for row in seed_result["mutants"]:
        found_by_crv = runner.is_found_within(row, SIGN_OFF_BUDGET)
        predicted[row["id"]] = found_by_crv or directed[row["id"]]["found_by_directed_tests"]
    report = compare(predicted, measured)
    report["harness_found"] = sum(measured.values())
    print(f"check B, seed {seed}, whole suite: {report}", flush=True)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--only", choices=["A", "B"], default=None)
    parser.add_argument("--budgets", default=",".join(str(b) for b in STUDY_BUDGETS_TO_CHECK),
                        help="check A budgets, comma-separated")
    args = parser.parse_args()
    os.makedirs(RESULTS_FOLDER, exist_ok=True)

    output_path = os.path.join(RESULTS_FOLDER, "crosscheck.json")
    report = json.load(open(output_path)) if os.path.exists(output_path) else {}

    def save():
        with open(output_path, "w") as output_file:
            json.dump(report, output_file, indent=1)

    if args.only in (None, "A"):
        check_a = report.setdefault("check_a_prefix_claim", {"seed": args.seed, "budgets": {}})
        check_a["seed"] = args.seed
        budgets = [int(text) for text in args.budgets.split(",")]
        check_a_prefix_claim(args.seed, budgets, check_a["budgets"], save)
    if args.only in (None, "B"):
        report["check_b_whole_suite"] = {"seed": args.seed, **check_b_whole_suite(args.seed)}
        save()


if __name__ == "__main__":
    main()
