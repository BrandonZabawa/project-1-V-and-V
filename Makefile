# Project 1 -- constrained-random verification of the synchronous FWFT FIFO.
# Same shape as the course Makefiles (code/tb/<lab>/Makefile). Place this repo at
# code/tb/fifo_p1 inside the student packet so the default DUT path resolves.
#
#   make SIM=icarus                         # full suite: directed + security + CRV sign-off
#   SEED=7 make SIM=icarus                  # replay one seed (the seed is the source of truth)
#   PROFILE=v1 CYCLES=4000 make SIM=icarus  # another stimulus profile / budget
#   make SIM=icarus DEPTH=5 WIDTH=4         # another parameter set (Icarus only)
#   make DUT=/path/to/fifo.sv               # override the DUT (used by the mutation harness)
TOPLEVEL_LANG ?= verilog
SIM           ?= icarus

DUT ?= $(CURDIR)/../../dut/fifo.sv
VERILOG_SOURCES = $(DUT)
TOPLEVEL = fifo
MODULE   = test_fifo_p1

WIDTH ?= 8
DEPTH ?= 8
export FIFO_WIDTH := $(WIDTH)
export FIFO_DEPTH := $(DEPTH)
ifeq ($(SIM),icarus)
COMPILE_ARGS += -Pfifo.WIDTH=$(WIDTH) -Pfifo.DEPTH=$(DEPTH)
endif
ifeq ($(SIM),verilator)
# the provided fifo.sv trips a WIDTHEXPAND lint warning (line 27) that is fatal by default
EXTRA_ARGS += -Wno-fatal -GWIDTH=$(WIDTH) -GDEPTH=$(DEPTH)
endif

export PYTHONPATH := $(CURDIR):$(CURDIR)/../../lib:$(PYTHONPATH)

include $(shell cocotb-config --makefiles)/Makefile.sim
