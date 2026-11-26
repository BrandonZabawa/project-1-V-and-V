#!/usr/bin/env bash
# demo.sh -- play the DEMO.md recording script one step at a time.
#
# Start your screen recorder, run this, and press Enter to move to each step.
# It moves to the repo folder (code/tb/fifo_p1) by itself, so run it from anywhere.
#
#   scripts/demo.sh --check          # preflight in a few seconds: tools, DUT, figures (runs no simulation)
#   scripts/demo.sh                  # the demo: pauses for Enter between the 10 steps
#   scripts/demo.sh --from 6         # start at step 6 (re-record one part)
#   scripts/demo.sh --only 4         # run only step 4
#   scripts/demo.sh --live-mutation  # step 6 reruns the released pool (about 4 minutes) instead of showing the saved run
#   scripts/demo.sh --cues           # also print what to say at each step (for a rehearsal, not the recording)
#   scripts/demo.sh --auto           # no Enter prompts: a 4-second pause between steps
#
# Figures open in VS Code when this runs in a VS Code terminal (Remote-SSH to
# eustis included); otherwise the script prints the path to open.
# Every command's full output is also saved under demo_logs/ (ignored by git).

set -uo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo"
lib_dir="$(cd "$repo/../.." 2>/dev/null && pwd)/lib"
dut_path="${DUT:-$repo/../../dut/fifo.sv}"
export PYTHONPATH="$repo:$lib_dir${PYTHONPATH:+:$PYTHONPATH}"
# pyvsc prints Python deprecation warnings on newer Python versions; they are noise on camera.
export PYTHONWARNINGS="${PYTHONWARNINGS:-ignore::DeprecationWarning}"
log_dir="$repo/demo_logs"
mkdir -p "$log_dir"

# ---------------------------------------------------------------- options
first_step=1
last_step=10
pause_mode="enter"
show_cues=0
live_mutation=0
check_only=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --from)          first_step="$2"; shift 2 ;;
        --only)          first_step="$2"; last_step="$2"; shift 2 ;;
        --auto)          pause_mode="auto"; shift ;;
        --cues)          show_cues=1; shift ;;
        --live-mutation) live_mutation=1; shift ;;
        --check)         check_only=1; shift ;;
        -h|--help)       sed -n '2,17p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *)               echo "unknown option: $1 (try --help)"; exit 2 ;;
    esac
done

# ---------------------------------------------------------------- output helpers
if [[ -t 1 ]]; then
    bold=$'\e[1m'; dim=$'\e[2m'; green=$'\e[32m'; yellow=$'\e[33m'; red=$'\e[31m'; cyan=$'\e[36m'; reset=$'\e[0m'
else
    bold=""; dim=""; green=""; yellow=""; red=""; cyan=""; reset=""
fi
note()    { printf '%s\n' "${dim}$*${reset}"; }
good()    { printf '%s\n' "${green}$*${reset}"; }
warn()    { printf '%s\n' "${yellow}$*${reset}"; }
bad()     { printf '%s\n' "${red}$*${reset}"; }
command_line() { printf '\n%s\n' "${cyan}\$ $*${reset}"; }

recording_start=$(date +%s)
elapsed() { local s=$(( $(date +%s) - recording_start )); printf '%d:%02d' $((s / 60)) $((s % 60)); }

pause_before_next() {
    if [[ "$pause_mode" == "auto" ]]; then
        sleep 4
    else
        printf '\n%s' "${dim}[Enter] next step${reset}"
        read -r _ </dev/tty || true
    fi
}

# Print a markdown table (read from stdin) aligned for a terminal. Optional column
# numbers (1-based) pick which columns to keep; long cells are cut to fit the width.
# The program goes in with -c, so stdin stays free for the table.
show_table() {
    python3 -c "$show_table_program" "$@"
}
read -r -d '' show_table_program <<'PYTHON'
import re, shutil, sys
columns_wanted = [int(c) - 1 for c in sys.argv[1:]]
rows = []
for line in sys.stdin:
    line = line.rstrip("\n")
    if not line.startswith("|"):
        continue
    cells = [c.strip().replace("**", "").replace("`", "") for c in line.strip("|").split("|")]
    if all(re.fullmatch(r":?-+:?", c) for c in cells if c):
        continue
    if columns_wanted:
        cells = [cells[i] if i < len(cells) else "" for i in columns_wanted]
    rows.append(cells)
if not rows:
    sys.exit(0)
width = shutil.get_terminal_size((120, 40)).columns
column_count = max(len(r) for r in rows)
widths = [max(len(r[i]) if i < len(r) else 0 for r in rows) for i in range(column_count)]
budget = width - 3 * (column_count - 1)
while sum(widths) > budget and max(widths) > 12:
    widest = widths.index(max(widths))
    widths[widest] -= 1
for index, row in enumerate(rows):
    cells = []
    for i in range(column_count):
        text = row[i] if i < len(row) else ""
        if len(text) > widths[i]:
            text = text[: widths[i] - 1] + "…"
        cells.append(text.ljust(widths[i]))
    print("   ".join(cells).rstrip())
    if index == 0:
        print("   ".join("-" * w for w in widths))
PYTHON

open_file() {
    local file="$1"
    if [[ ! -f "$file" ]]; then
        bad "missing: $file"
        return 1
    fi
    if [[ "${TERM_PROGRAM:-}" == "vscode" ]] && command -v code >/dev/null 2>&1; then
        code -r "$file" && good "opened $file in VS Code"
    elif [[ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]] && command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$file" >/dev/null 2>&1 &
        good "opened $file"
    else
        warn "open this figure on screen: $repo/$file"
    fi
}

# Lines worth pointing at in a cocotb run.
highlight_run() {
    grep -E "SEED [0-9]+ PROFILE|OCC |COVER TOTAL|TESTS=|FAIL " "$1" | sed -E 's/^ *[0-9.]+ns +INFO +cocotb\.[a-z_]+ +//; s/^ +\*\* +//; s/ +\*\*$//'
}

# ---------------------------------------------------------------- preflight
preflight() {
    local problems=0
    printf '%s\n' "${bold}Preflight${reset} ${dim}($repo)${reset}"
    for tool in python3 make iverilog cocotb-config; do
        if command -v "$tool" >/dev/null 2>&1; then
            good "  ok       $tool"
        else
            bad  "  MISSING  $tool"; problems=1
        fi
    done
    if [[ -f "$dut_path" ]]; then good "  ok       DUT $dut_path"; else bad "  MISSING  DUT $dut_path (put this repo at code/tb/fifo_p1 inside the packet)"; problems=1; fi
    if python3 -c "import models.fifo_model" 2>/dev/null; then good "  ok       golden model (code/lib/models)"; else bad "  MISSING  golden model: code/lib is not importable"; problems=1; fi
    if python3 -c "import craft_mutate.mutate" 2>/dev/null; then good "  ok       mutation harness (code/lib/craft_mutate)"; else warn "  missing  mutation harness (only needed for --live-mutation)"; fi
    for figure in extension/figures/occupancy_hist.png extension/figures/q1_curves.png extension/figures/q2_seed_spread.png; do
        if [[ -f "$figure" ]]; then good "  ok       $figure"; else bad "  MISSING  $figure"; problems=1; fi
    done
    if [[ "${TERM_PROGRAM:-}" == "vscode" ]] && command -v code >/dev/null 2>&1; then
        good "  ok       figures will open in VS Code"
    else
        warn "  note     not a VS Code terminal: figure paths are printed instead of opened"
    fi
    if [[ $problems -ne 0 ]]; then
        bad "Fix the items above first. On eustis: source /opt/course/cocotb-env/bin/activate"
        return 1
    fi
    good "Ready to record."
}

# ---------------------------------------------------------------- the 10 steps (DEMO.md)
step_titles=(
    ""
    "Layering: driver, monitor, scoreboard, coverage"
    "Constraints shape, they never forbid (crv/transactions.py)"
    "Full suite: directed + security + constrained-random sign-off"
    "Same seed, same stimulus digest"
    "Coverage convergence across profiles v1 to v4"
    "Mutation score on the released pool"
    "Our own 24-mutant pool and its survivors"
    "Graduate extension: occupancy histogram against uniform"
    "Q1 (Brandon): does closing coverage track finding bugs?"
    "Q2 (Leo): how much does the seed matter?"
)
step_targets=("" "0:00" "0:40" "1:30" "2:15" "2:45" "3:30" "4:00" "4:40" "5:00" "5:30")
step_cues=(
    ""
    "Driver drives on the falling edge, the monitor reads pins back, the scoreboard is a reference queue that checks count, full, empty and the head every cycle at two sample points; coverage is sampled from the scoreboard's own prediction."
    "Every enable pair is legal, so constraints only shape. Occupancy and phase are non-random fields fed each cycle. We do not use dist inside the branches, because we measured that pyvsc applies it unconditionally."
    "Point at TESTS=3 PASS=3, the OCC histogram (U-shaped: about 0.10 at empty, about 0.2 at full, against 0.0625 for uniform), and COVER TOTAL 100.00%."
    "Same seed, same digest. The seed and the command line are the source of truth."
    "v1 uniform stalls at 92.49% (no resets). v2 and v3 leave reset-cross holes; v3 even opened new ones at partial occupancy. v4 fixed them with a constraint change, not a directed test."
    "8 of 8 on the released pool."
    "On our own 24-mutant pool we find 21. Two survivors drive rd_data while empty, which the spec leaves undefined. One is logically equivalent. The one we fixed lived between our sample points."
    "The histogram against uniform, and the corner bound."
    "Both curves on one budget axis. Every findable bug falls in the first few hundred cycles, while the cross keeps closing for thousands more. A coverage hole predicted a miss; coverage growth did not predict finds."
    "20 seeds at two budgets. The seed changes the constrained-random score at 100 cycles and not at all at 2,500, and seed 1 is not a lucky seed."
)

step_1() {
    command_line "sed -n '/Layering in one picture/,\$p' README.md"
    awk '/^## Layering in one picture/{found=1; next} found && /^## /{exit} found' README.md | sed '/^```/d'
}

step_2() {
    command_line "sed -n '/^OPERATION_MIX/,/^}/p' crv/transactions.py"
    sed -n '/^OPERATION_MIX = {/,/^}/p' crv/transactions.py
    command_line "sed -n '/def shape_operation_by_occupancy/,/^\$/p' crv/transactions.py"
    sed -n '/def shape_operation_by_occupancy/,/^$/p' crv/transactions.py
}

step_3() {
    local log="$log_dir/full_suite.log"
    command_line "make SIM=icarus"
    local started=$(date +%s)
    make SIM=icarus 2>&1 | tee "$log"
    local status=${PIPESTATUS[0]}
    printf '\n%s\n' "${bold}What to point at${reset} ${dim}($(( $(date +%s) - started )) s)${reset}"
    highlight_run "$log"
    if [[ $status -eq 0 ]] && grep -q "FAIL=0" "$log"; then good "suite passed"; else bad "suite did NOT pass (exit $status), see $log"; fi
}

step_4() {
    local digests=()
    for run in 1 2; do
        local log="$log_dir/seed7_run$run.log"
        command_line "SEED=7 make SIM=icarus TESTCASE=test_t3_crv_signoff     # run $run of 2"
        SEED=7 make SIM=icarus TESTCASE=test_t3_crv_signoff 2>&1 | tee "$log" | grep --line-buffered -E "digest=|TESTS=" | sed -E 's/^ *[0-9.]+ns +INFO +cocotb\.[a-z_]+ +//; s/^ +\*\* +//; s/ +\*\*$//'
        digests+=("$(grep -o 'digest=[0-9a-f]*' "$log" | head -1)")
    done
    printf '\n'
    if [[ -n "${digests[0]}" && "${digests[0]}" == "${digests[1]}" ]]; then
        good "run 1 ${digests[0]}   run 2 ${digests[1]}   identical"
    else
        bad "digests differ: '${digests[0]}' vs '${digests[1]}'"
    fi
}

step_5() {
    command_line "cat results/convergence/summary.md"
    sed -n '/^| profile/,/^$/p' results/convergence/summary.md | show_table 1 2 3 4 5 6
    printf '\n'
    grep -E '^### v[0-9]' results/convergence/summary.md
}

step_6() {
    if [[ $live_mutation -eq 1 ]]; then
        local log="$log_dir/released_pool.log"
        command_line "python -m craft_mutate.mutate --tb . --dut ../../dut/fifo.sv --pool mutants_released.yaml --sim icarus"
        python3 -m craft_mutate.mutate --tb . --dut "$dut_path" --pool mutants_released.yaml --sim icarus 2>&1 | tee "$log"
    else
        command_line "cat results/mutation/released.txt     # saved run of: python -m craft_mutate.mutate --tb . --pool mutants_released.yaml --sim icarus"
        grep -E "^\s*\[|found/total" results/mutation/released.txt
    fi
}

step_7() {
    command_line "tail -n 6 results/mutation/stress.txt"
    grep -E "SURVIVED|found/total|surviving" results/mutation/stress.txt
    command_line "FINDINGS.md: survivors"
    awk '/^## Survivors/{found=1; next} found && /^## /{exit} found' FINDINGS.md \
        | sed -E 's/^\| `([A-Za-z0-9_]+)` \([^|]*\|/| \1 |/' | show_table 1 5
}

step_8() {
    open_file extension/figures/occupancy_hist.png
    python3 - <<'PYTHON'
import json
data = json.load(open("extension/results/stimulus_distribution.json"))
print(f"distance from a flat histogram (total variation): v1 {data['total_variation_from_flat_v1']}, v4 {data['total_variation_from_flat_v4']}")
print(f"largest gap between measured v4 and the Markov chain prediction: {data['largest_gap_measured_vs_chain_v4']}")
corner = data.get("corner_full_and_simul")
if isinstance(corner, dict):
    for key, value in corner.items():
        if not isinstance(value, (list, dict)):
            print(f"full with a simultaneous read and write, {key}: {value}")
PYTHON
}

step_9() {
    open_file extension/figures/q1_curves.png
    command_line "cat extension/results/q1_table.md"
    show_table 1 2 3 6 < extension/results/q1_table.md
    grep -E "^(Pearson|Spearman)" extension/results/q1_table.md
}

step_10() {
    open_file extension/figures/q2_seed_spread.png
    command_line "cat extension/results/q2_table.md"
    show_table < extension/results/q2_table.md
}

# ---------------------------------------------------------------- run
preflight || exit 1
[[ $check_only -eq 1 ]] && exit 0
if [[ "$pause_mode" == "enter" ]]; then
    printf '\n%s' "${dim}Start your screen recorder, then press Enter to begin.${reset}"
    read -r _ </dev/tty || true
fi
clear 2>/dev/null || true
recording_start=$(date +%s)

for (( step = first_step; step <= last_step; step++ )); do
    printf '\n%s\n' "${bold}━━ Step $step/10 · ${step_titles[$step]}${reset}  ${dim}(script ${step_targets[$step]} · now $(elapsed))${reset}"
    if [[ $show_cues -eq 1 ]]; then printf '%s\n' "${yellow}Say: ${step_cues[$step]}${reset}"; fi
    "step_$step"
    if (( step < last_step )); then pause_before_next; fi
done
printf '\n%s\n' "${bold}Done${reset} ${dim}(total $(elapsed)). Logs: demo_logs/${reset}"
