"""Exact Markov-chain model of the FIFO stimulus.

A state is (occupancy, phase). One step is one cycle of the sequence, exactly
as crv/sequences.py runs it:
  1. Phase flip: FILL -> DRAIN with probability `flip_chance` when occupancy
     is DEPTH; DRAIN -> FILL with probability `flip_chance` when it is 0.
  2. With probability reset_chance(occupancy) the cycle is a reset, and the
     next state is (0, FILL).
  3. Otherwise the operation mix for (region, phase) picks write-only, both,
     read-only or idle, and the FIFO rules (drop at full, ignore at empty,
     count unchanged on a true simultaneous read and write) give the next
     occupancy.
The "uniform" stimulus is the same chain with every operation at 1/4 and no
phase at all.

Because the chain uses the same table as crv/transactions.py, its predictions
can be checked against measured runs (Fig. 1 of the report).
"""
import numpy as np

FILL, DRAIN = 0, 1
ROLL_RANGE = 20
OPERATION_MIX = {    # same table as crv/transactions.py: (write-only, both, read-only) out of 20
    ("near_empty", FILL): (12, 5, 2), ("near_empty", DRAIN): (2, 4, 11),
    ("mid", FILL): (8, 9, 2),         ("mid", DRAIN): (2, 9, 8),
    ("near_full", DRAIN): (2, 5, 12), ("near_full", FILL): (11, 4, 2),
}


def occupancy_region(occupancy, depth):
    if occupancy <= 1:
        return "near_empty"
    if occupancy >= depth - 1:
        return "near_full"
    return "mid"


def operation_probabilities(occupancy, phase, depth, stimulus_kind):
    """{(write_enable, read_enable): probability} for one cycle."""
    if stimulus_kind == "uniform":
        return {(1, 0): 0.25, (1, 1): 0.25, (0, 1): 0.25, (0, 0): 0.25}
    write_only, both, read_only = OPERATION_MIX[(occupancy_region(occupancy, depth), phase)]
    idle = ROLL_RANGE - write_only - both - read_only
    return {(1, 0): write_only / ROLL_RANGE, (1, 1): both / ROLL_RANGE,
            (0, 1): read_only / ROLL_RANGE, (0, 0): idle / ROLL_RANGE}


def state_index(occupancy, phase):
    return 2 * occupancy + phase


def state_name(index):
    phase = "FILL" if index % 2 == 0 else "DRAIN"
    return f"(count={index // 2}, {phase})"


def build_transition_matrix(depth=8, stimulus_kind="shaped", flip_chance=0.05,
                            reset_chance=lambda occupancy, depth: 0.0, corner=None):
    """Transition matrix over 2*(DEPTH+1) states.

    When `corner(occupancy, write_enable, read_enable)` is given, one extra
    absorbing HIT state is added: entering it means the corner was reached.
    """
    transient_states = 2 * (depth + 1)
    state_count = transient_states + (1 if corner else 0)
    hit_state = transient_states
    matrix = np.zeros((state_count, state_count))

    for occupancy in range(depth + 1):
        for phase in (FILL, DRAIN):
            # Step 1: possible phase flips and their probabilities.
            if stimulus_kind == "uniform":
                phase_outcomes = [(phase, 1.0)]
            elif phase == FILL and occupancy >= depth:
                phase_outcomes = [(DRAIN, flip_chance), (FILL, 1 - flip_chance)]
            elif phase == DRAIN and occupancy == 0:
                phase_outcomes = [(FILL, flip_chance), (DRAIN, 1 - flip_chance)]
            else:
                phase_outcomes = [(phase, 1.0)]

            from_state = state_index(occupancy, phase)
            chance_of_reset = reset_chance(occupancy, depth)
            for next_phase, phase_probability in phase_outcomes:
                # Step 2: a reset sends us to (0, FILL).
                if chance_of_reset:
                    matrix[from_state, state_index(0, FILL)] += phase_probability * chance_of_reset
                # Step 3: an ordinary operation.
                operations = operation_probabilities(occupancy, next_phase, depth, stimulus_kind)
                for (write_enable, read_enable), operation_probability in operations.items():
                    probability = phase_probability * (1 - chance_of_reset) * operation_probability
                    if corner and corner(occupancy, write_enable, read_enable):
                        matrix[from_state, hit_state] += probability
                        continue
                    write_happens = bool(write_enable) and occupancy < depth
                    read_happens = bool(read_enable) and occupancy > 0
                    next_occupancy = occupancy + int(write_happens) - int(read_happens)
                    matrix[from_state, state_index(next_occupancy, next_phase)] += probability

    if corner:
        matrix[hit_state, hit_state] = 1.0
    assert np.allclose(matrix.sum(axis=1), 1.0), "every row of a transition matrix must sum to 1"
    return matrix


def long_run_occupancy(matrix, depth=8):
    """Fraction of cycles spent at each occupancy in the long run."""
    eigenvalues, eigenvectors = np.linalg.eig(matrix.T)
    stationary = np.real(eigenvectors[:, np.argmin(abs(eigenvalues - 1))])
    stationary = stationary / stationary.sum()
    return stationary.reshape(depth + 1, 2).sum(axis=1)


def chance_of_hit_by_step(matrix, start_state, steps):
    """P(the corner is hit within k steps), for k = 1..steps."""
    distribution = np.zeros(matrix.shape[0])
    distribution[start_state] = 1.0
    chances = []
    for _ in range(steps):
        distribution = distribution @ matrix
        chances.append(distribution[-1])
    return np.array(chances)


def worst_start_chance(matrix, window):
    """q_L: the smallest P(hit within `window` steps) over every start state.
    Returns (q_L, index of that worst start state)."""
    after_window = np.linalg.matrix_power(matrix, window)
    chance_from_each_start = after_window[:-1, -1]
    return chance_from_each_start.min(), int(np.argmin(chance_from_each_start))
