# Regression `convergence` -- 2500 cycles per run, Icarus

Command: `python3 crv/regress.py --convergence --jobs 2`

| profile | seed | pass | coverage % | empty mass | full mass | stimulus digest |
|---|---:|---|---:|---:|---:|---|
| v1 | 1 | NO | 92.49 | 0.071 | 0.068 | `a57d63778dfd1fb1` |
| v1 | 2 | NO | 92.49 | 0.053 | 0.07 | `201160e41f5f3a3a` |
| v1 | 3 | NO | 92.49 | 0.024 | 0.078 | `3e8b0346d488ba28` |
| v1 | 4 | NO | 92.49 | 0.079 | 0.043 | `9dddcf5c7ab5af13` |
| v1 | 5 | NO | 92.49 | 0.045 | 0.052 | `026bafcdb9f187d1` |
| v2 | 1 | yes | 96.71 | 0.182 | 0.155 | `ec88edaa6c673b14` |
| v2 | 2 | yes | 93.9 | 0.194 | 0.161 | `d83be3aa2bcf4627` |
| v2 | 3 | yes | 97.65 | 0.169 | 0.212 | `9db82b1383d584d2` |
| v2 | 4 | yes | 96.24 | 0.176 | 0.188 | `a7b9301c4071da7e` |
| v2 | 5 | yes | 98.12 | 0.152 | 0.194 | `2e4c329c036ff509` |
| v3 | 1 | yes | 98.59 | 0.149 | 0.177 | `748b9ead37e6df27` |
| v3 | 2 | yes | 98.59 | 0.114 | 0.202 | `4714a42f79eec1bb` |
| v3 | 3 | yes | 98.12 | 0.135 | 0.202 | `346f30cc6234db0d` |
| v3 | 4 | yes | 98.59 | 0.15 | 0.192 | `6cdc8b7296dac4ff` |
| v3 | 5 | yes | 99.06 | 0.151 | 0.193 | `ea2e9990851dd324` |
| v4 | 1 | yes | 100.0 | 0.103 | 0.199 | `9f792b79f86b6cf1` |
| v4 | 2 | yes | 100.0 | 0.126 | 0.196 | `4e653f12dcf88e8c` |
| v4 | 3 | yes | 100.0 | 0.129 | 0.181 | `7bae7d49b2f6bf66` |
| v4 | 4 | yes | 99.53 | 0.099 | 0.186 | `c2711bc0b601aea6` |
| v4 | 5 | yes | 100.0 | 0.105 | 0.163 | `837b7ae9ab53ea1b` |

## Merged coverage per profile (union over seeds)

### v1: 197/213 bins = 92.49%

| item | covered | holes |
|---|---:|---|
| `fifo.occ` | 9/9 |  |
| `fifo.op` | 4/4 |  |
| `fifo.pre_occ` | 5/5 |  |
| `fifo.outcome` | 8/8 |  |
| `fifo.data` | 5/5 |  |
| `fifo.wrap` | 2/2 |  |
| `fifo.wrap_occ_cls` | 5/5 |  |
| `fifo.rst_occ` | 1/3 | full, partial |
| `fifo.rst_en` | 1/4 | both, rd, wr |
| `fifo.march` | 128/128 |  |
| `fifo.occ_x_op` | 20/20 |  |
| `fifo.wrap_x_occ` | 8/8 |  |
| `fifo.rst_x_en` | 1/12 | ('empty', 'both'), ('empty', 'rd'), ('empty', 'wr'), ('full', 'both'), ('full', 'none'), ('full', 'rd') ... |

Seeds closing 100% on their own: **0/5**

### v2: 211/213 bins = 99.06%

| item | covered | holes |
|---|---:|---|
| `fifo.occ` | 9/9 |  |
| `fifo.op` | 4/4 |  |
| `fifo.pre_occ` | 5/5 |  |
| `fifo.outcome` | 8/8 |  |
| `fifo.data` | 5/5 |  |
| `fifo.wrap` | 2/2 |  |
| `fifo.wrap_occ_cls` | 5/5 |  |
| `fifo.rst_occ` | 3/3 |  |
| `fifo.rst_en` | 4/4 |  |
| `fifo.march` | 128/128 |  |
| `fifo.occ_x_op` | 20/20 |  |
| `fifo.wrap_x_occ` | 8/8 |  |
| `fifo.rst_x_en` | 10/12 | ('empty', 'both'), ('empty', 'wr') |

Seeds closing 100% on their own: **0/5**

### v3: 213/213 bins = 100.00%

| item | covered | holes |
|---|---:|---|
| `fifo.occ` | 9/9 |  |
| `fifo.op` | 4/4 |  |
| `fifo.pre_occ` | 5/5 |  |
| `fifo.outcome` | 8/8 |  |
| `fifo.data` | 5/5 |  |
| `fifo.wrap` | 2/2 |  |
| `fifo.wrap_occ_cls` | 5/5 |  |
| `fifo.rst_occ` | 3/3 |  |
| `fifo.rst_en` | 4/4 |  |
| `fifo.march` | 128/128 |  |
| `fifo.occ_x_op` | 20/20 |  |
| `fifo.wrap_x_occ` | 8/8 |  |
| `fifo.rst_x_en` | 12/12 |  |

Seeds closing 100% on their own: **0/5**

### v4: 213/213 bins = 100.00%

| item | covered | holes |
|---|---:|---|
| `fifo.occ` | 9/9 |  |
| `fifo.op` | 4/4 |  |
| `fifo.pre_occ` | 5/5 |  |
| `fifo.outcome` | 8/8 |  |
| `fifo.data` | 5/5 |  |
| `fifo.wrap` | 2/2 |  |
| `fifo.wrap_occ_cls` | 5/5 |  |
| `fifo.rst_occ` | 3/3 |  |
| `fifo.rst_en` | 4/4 |  |
| `fifo.march` | 128/128 |  |
| `fifo.occ_x_op` | 20/20 |  |
| `fifo.wrap_x_occ` | 8/8 |  |
| `fifo.rst_x_en` | 12/12 |  |

Seeds closing 100% on their own: **4/5**

