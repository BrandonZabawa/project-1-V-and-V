"""Small statistics helpers for the graduate extension (no SciPy needed, so the
scripts also run in the plain course environment)."""
import math

# Two-sided 95% critical values of Student's t, by degrees of freedom.
T_CRITICAL_95 = {
    1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306,
    9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131,
    16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086, 21: 2.080, 22: 2.074,
    23: 2.069, 24: 2.064, 25: 2.060, 26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045,
    30: 2.042, 40: 2.021, 60: 2.000, 120: 1.980,
}


def t_critical_95(degrees_of_freedom):
    if degrees_of_freedom in T_CRITICAL_95:
        return T_CRITICAL_95[degrees_of_freedom]
    larger = [df for df in T_CRITICAL_95 if df >= degrees_of_freedom]
    return T_CRITICAL_95[min(larger)] if larger else 1.960


def mean(values):
    return sum(values) / len(values)


def sample_standard_deviation(values):
    if len(values) < 2:
        return 0.0
    average = mean(values)
    return math.sqrt(sum((value - average) ** 2 for value in values) / (len(values) - 1))


def confidence_interval_95(values):
    """95% t-interval for the mean: mean +/- t * s / sqrt(n)."""
    average = mean(values)
    half_width = t_critical_95(len(values) - 1) * sample_standard_deviation(values) / math.sqrt(len(values))
    return average - half_width, average + half_width


def percentile(values, fraction):
    """Linear-interpolation percentile, fraction in [0, 1]."""
    ordered = sorted(values)
    position = fraction * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def describe(values):
    """Everything Q2 reports about one distribution."""
    low, high = confidence_interval_95(values)
    return {
        "n": len(values),
        "mean": round(mean(values), 4),
        "standard_deviation": round(sample_standard_deviation(values), 4),
        "ci95_low": round(low, 4),
        "ci95_high": round(high, 4),
        "min": min(values),
        "median": percentile(values, 0.5),
        "max": max(values),
        "p2_5": round(percentile(values, 0.025), 4),
        "p97_5": round(percentile(values, 0.975), 4),
        "distinct_values": sorted(set(values)),
    }


def pearson(xs, ys):
    average_x, average_y = mean(xs), mean(ys)
    covariance = sum((x - average_x) * (y - average_y) for x, y in zip(xs, ys))
    spread_x = math.sqrt(sum((x - average_x) ** 2 for x in xs))
    spread_y = math.sqrt(sum((y - average_y) ** 2 for y in ys))
    return covariance / (spread_x * spread_y)


def ranks_with_ties_averaged(values):
    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    position = 0
    while position < len(order):
        tie_end = position
        while tie_end + 1 < len(order) and values[order[tie_end + 1]] == values[order[position]]:
            tie_end += 1
        shared_rank = (position + tie_end) / 2 + 1
        for index in order[position:tie_end + 1]:
            ranks[index] = shared_rank
        position = tie_end + 1
    return ranks


def spearman(xs, ys):
    return pearson(ranks_with_ties_averaged(xs), ranks_with_ties_averaged(ys))
