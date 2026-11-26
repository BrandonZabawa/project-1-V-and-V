"""Functional coverage model (cocotb-coverage). Mirrors vplan.md section 3.

It is sampled once per checked cycle from the scoreboard's CycleRecord, which
is the same prediction that was just compared against the DUT.

Coverpoints
  C1  fifo.occ           occupancy after the edge, one bin per value 0..DEPTH
  C2  fifo.op            requested operation (non-reset cycles): idle / write / read / simul
  C3  fifo.pre_occ       occupancy class before the edge: empty / one / mid / almost_full / full
  C4  fifo.outcome       what the edge actually did: none / push / pop / push_pop /
                         drop_write / ignore_read / simul_drop_write / simul_ignore_read
  C5  fifo.data          class of an accepted write's data: zero / ones / p55 / paa / other
  C6  fifo.wrap          pointer wrap on this edge: wr_wrap / rd_wrap
  C7  fifo.wrap_occ_cls  occupancy class after the edge, sampled only on wrap edges
  C8  fifo.rst_occ       occupancy class when a reset edge hits: empty / partial / full
  C9  fifo.rst_en        enables asserted during that reset edge: none / wr / rd / both
  C10 fifo.march         (slot, bit, value) of every word popped and compared

Crosses
  X1  fifo.occ_x_op      C3 x C2: 20 bins, NO ignore bins. (full, write) and
                         (empty, read) are legal corners the spec defines
                         (dropped / ignored), so they must be covered.
  X2  fifo.wrap_x_occ    C6 x C7: 10 tuples, 2 ignore bins (unreachable, see vplan A4)
  X3  fifo.rst_x_en      C8 x C9: 12 bins. The security thread: (any, wr/both)
                         is a write asserted during reset.

Illegal bins (CoverCheck; each one also raises in assert_no_illegal_bins)
  I1  a count change the spec does not allow for that (occupancy, operation)
  I2  full and empty both true       (impossible by rule 5 when DEPTH >= 1)
  I3  both pointers wrap on one edge (the pointers are equal only at empty or
      full, where a true simultaneous read and write cannot happen)
  I4  occupancy outside 0..DEPTH

The item names ("fifo.occ" and so on) are the identifiers used in closure.md,
the YAML coverage exports and crv/regress.py, so they stay as they are.
"""
from cocotb_coverage.coverage import CoverCheck, CoverCross, CoverPoint, coverage_db

DO_NOT_SAMPLE = "__no_sample__"   # a value outside every bin list: the point skips this cycle

OCCUPANCY_CLASSES = ["empty", "one", "mid", "almost_full", "full"]
OPERATIONS = ["idle", "write", "read", "simul"]
OUTCOMES = ["none", "push", "pop", "push_pop", "drop_write", "ignore_read",
            "simul_drop_write", "simul_ignore_read"]
DATA_CLASSES = ["zero", "ones", "p55", "paa", "other"]
RESET_OCCUPANCY_CLASSES = ["empty", "partial", "full"]
RESET_ENABLES = ["none", "wr", "rd", "both"]


# ---------------------------------------------------------------- classifiers
def occupancy_class(occupancy, depth):
    if occupancy == 0:
        return "empty"
    if occupancy == depth:
        return "full"
    if occupancy == 1:
        return "one"
    if occupancy == depth - 1:
        return "almost_full"
    return "mid"


def operation_name(write_enable, read_enable):
    names = {(0, 0): "idle", (1, 0): "write", (0, 1): "read", (1, 1): "simul"}
    return names[(int(write_enable), int(read_enable))]


def edge_outcome(record):
    """What the edge did, separating what was requested from what happened."""
    if not record.rst_n:
        return DO_NOT_SAMPLE
    requested = operation_name(record.wr_en, record.rd_en)
    if requested == "idle":
        return "none"
    if requested == "write":
        return "push" if record.write_happened else "drop_write"
    if requested == "read":
        return "pop" if record.read_happened else "ignore_read"
    if record.write_happened and record.read_happened:
        return "push_pop"
    return "simul_drop_write" if record.read_happened else "simul_ignore_read"


def write_data_class(record):
    if not (record.rst_n and record.write_happened):
        return DO_NOT_SAMPLE
    all_ones = (1 << record.width) - 1
    alternating_01 = int("01" * record.width, 2) & all_ones
    value = record.wr_data & all_ones
    named_patterns = {0: "zero", all_ones: "ones",
                      alternating_01: "p55", alternating_01 ^ all_ones: "paa"}
    return named_patterns.get(value, "other")


def wrap_kind(record):
    if not record.rst_n:
        return DO_NOT_SAMPLE
    if record.write_pointer_wrapped:
        return "wr_wrap"
    if record.read_pointer_wrapped:
        return "rd_wrap"
    return DO_NOT_SAMPLE


def occupancy_class_on_wrap(record):
    wrapped = record.write_pointer_wrapped or record.read_pointer_wrapped
    if record.rst_n and wrapped:
        return occupancy_class(record.occupancy_after, record.depth)
    return DO_NOT_SAMPLE


def occupancy_class_at_reset(record):
    if record.rst_n:
        return DO_NOT_SAMPLE
    if record.occupancy_before == 0:
        return "empty"
    if record.occupancy_before == record.depth:
        return "full"
    return "partial"


def enables_during_reset(record):
    if record.rst_n:
        return DO_NOT_SAMPLE
    names = {(0, 0): "none", (1, 0): "wr", (0, 1): "rd", (1, 1): "both"}
    return names[(record.wr_en, record.rd_en)]


def popped_word(record):
    """(slot, value) of the word that left the FIFO, for the bit march."""
    if record.popped_value is None:
        return None
    return (record.popped_from_slot, record.popped_value)


def popped_word_matches_march_bin(popped, march_bin):
    """A march bin is (slot, bit, value): this word came from `slot` and its
    `bit` equals `value`."""
    if popped is None:
        return False
    slot, word = popped
    bin_slot, bin_bit, bin_value = march_bin
    return slot == bin_slot and ((word >> bin_bit) & 1) == bin_value


# -------------------------------------------------------------- illegal bins
def count_change_the_spec_allows(record):
    """Spec rules 2-4: the count change each (occupancy, operation) may make."""
    depth, before = record.depth, record.occupancy_before
    a_write_can_happen = bool(record.wr_en) and before < depth
    a_read_can_happen = bool(record.rd_en) and before > 0
    return int(a_write_can_happen) - int(a_read_can_happen)


def illegal_count_change(record):
    actual_change = record.occupancy_after - record.occupancy_before
    return bool(record.rst_n) and actual_change != count_change_the_spec_allows(record)


def illegal_full_and_empty(record):
    return record.occupancy_after == 0 and record.occupancy_after == record.depth


def illegal_double_wrap(record):
    return bool(record.rst_n) and record.write_pointer_wrapped and record.read_pointer_wrapped


def illegal_occupancy(record):
    return not (0 <= record.occupancy_after <= record.depth)


def assert_no_illegal_bins(record):
    operation = operation_name(record.wr_en, record.rd_en)
    assert not illegal_count_change(record), \
        f"illegal bin I1: count {record.occupancy_before}->{record.occupancy_after} on {operation}"
    assert not illegal_full_and_empty(record), "illegal bin I2: full and empty together"
    assert not illegal_double_wrap(record), "illegal bin I3: both pointers wrapped on one edge"
    assert not illegal_occupancy(record), f"illegal bin I4: occupancy {record.occupancy_after}"


def always_passes(record):
    return True


# ------------------------------------------------------------------- the model
_SAMPLERS_BY_SHAPE = {}


def build(depth, data_width):
    """Define the coverage items once per (depth, data_width); return the sampler."""
    shape = (depth, data_width)
    if shape in _SAMPLERS_BY_SHAPE:
        return _SAMPLERS_BY_SHAPE[shape]
    assert depth >= 4, "the occupancy classes assume DEPTH >= 4"

    march_bins = [(slot, bit, value)
                  for slot in range(depth)
                  for bit in range(data_width)
                  for value in (0, 1)]

    @CoverPoint("fifo.occ", xf=lambda record: record.occupancy_after, bins=list(range(depth + 1)))
    @CoverPoint("fifo.op",
                xf=lambda record: operation_name(record.wr_en, record.rd_en) if record.rst_n else DO_NOT_SAMPLE,
                bins=OPERATIONS)
    @CoverPoint("fifo.pre_occ",
                xf=lambda record: occupancy_class(record.occupancy_before, depth) if record.rst_n else DO_NOT_SAMPLE,
                bins=OCCUPANCY_CLASSES)
    @CoverPoint("fifo.outcome", xf=edge_outcome, bins=OUTCOMES)
    @CoverPoint("fifo.data", xf=write_data_class, bins=DATA_CLASSES)
    @CoverPoint("fifo.wrap", xf=wrap_kind, bins=["wr_wrap", "rd_wrap"])
    @CoverPoint("fifo.wrap_occ_cls", xf=occupancy_class_on_wrap, bins=OCCUPANCY_CLASSES)
    @CoverPoint("fifo.rst_occ", xf=occupancy_class_at_reset, bins=RESET_OCCUPANCY_CLASSES)
    @CoverPoint("fifo.rst_en", xf=enables_during_reset, bins=RESET_ENABLES)
    @CoverPoint("fifo.march", xf=popped_word, rel=popped_word_matches_march_bin,
                bins=march_bins, inj=False)
    @CoverCross("fifo.occ_x_op", items=["fifo.pre_occ", "fifo.op"])
    @CoverCross("fifo.wrap_x_occ", items=["fifo.wrap", "fifo.wrap_occ_cls"],
                ign_bins=[("rd_wrap", "full"), ("wr_wrap", "empty")])
    @CoverCross("fifo.rst_x_en", items=["fifo.rst_occ", "fifo.rst_en"])
    @CoverCheck("fifo.illegal.I1_count_delta", f_fail=illegal_count_change, f_pass=always_passes)
    @CoverCheck("fifo.illegal.I2_full_and_empty", f_fail=illegal_full_and_empty, f_pass=always_passes)
    @CoverCheck("fifo.illegal.I3_double_wrap", f_fail=illegal_double_wrap, f_pass=always_passes)
    @CoverCheck("fifo.illegal.I4_range", f_fail=illegal_occupancy, f_pass=always_passes)
    def _sample_every_item(record):
        pass

    def sample(record):
        assert_no_illegal_bins(record)
        _sample_every_item(record)

    _SAMPLERS_BY_SHAPE[shape] = sample
    return sample


# ------------------------------------------------------------------- reporting
ITEMS = ["fifo.occ", "fifo.op", "fifo.pre_occ", "fifo.outcome", "fifo.data", "fifo.wrap",
         "fifo.wrap_occ_cls", "fifo.rst_occ", "fifo.rst_en", "fifo.march",
         "fifo.occ_x_op", "fifo.wrap_x_occ", "fifo.rst_x_en"]
CHECKS = ["fifo.illegal.I1_count_delta", "fifo.illegal.I2_full_and_empty",
          "fifo.illegal.I3_double_wrap", "fifo.illegal.I4_range"]
CROSSES = ["fifo.occ_x_op", "fifo.wrap_x_occ", "fifo.rst_x_en"]


def summary():
    """[(name, covered_bins, total_bins, percent)] for every item and check."""
    rows = []
    for name in ITEMS + CHECKS:
        item = coverage_db[name]
        rows.append((name, item.coverage, item.size, item.cover_percentage))
    return rows


def holes():
    """{item name: [bins never hit]} for every item below 100%."""
    unfilled = {}
    for name in ITEMS:
        item = coverage_db[name]
        if item.cover_percentage < 100:
            hits = item.detailed_coverage
            if isinstance(hits, dict):
                unfilled[name] = [bin_ for bin_, count in hits.items() if count < item._at_least]
            else:
                unfilled[name] = "?"
    return unfilled


def _percent_of(names):
    covered = sum(coverage_db[name].coverage for name in names)
    size = sum(coverage_db[name].size for name in names)
    return 100.0 * covered / size


def cross_percent():
    return _percent_of(CROSSES)


def percent_of_each_cross():
    """{cross name: percent covered}, e.g. {"fifo.rst_x_en": 75.0, ...}."""
    return {name: round(coverage_db[name].cover_percentage, 3) for name in CROSSES}


def total_percent():
    return _percent_of(ITEMS)
