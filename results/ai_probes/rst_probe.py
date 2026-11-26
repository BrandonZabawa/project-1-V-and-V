import random, time, vsc
from collections import Counter
@vsc.randobj
class T:
    def __init__(self, depth=8):
        self.depth=depth
        self.wr_en=vsc.rand_bit_t(1); self.rd_en=vsc.rand_bit_t(1)
        self.rst=vsc.rand_bit_t(1); self.rroll=vsc.rand_bit_t(7)
        self.count=vsc.uint32_t(0)
    @vsc.constraint
    def c_rst(self):
        with vsc.if_then((self.count == 0) | (self.count == self.depth)):
            self.rst == (self.rroll < 2)
        with vsc.else_then:
            self.rst == (self.rroll < 1)
random.seed(3); t=T()
for c in (0,4,8):
    t.count=c; n=4000; k=0; t0=time.time()
    for _ in range(n): t.randomize(); k+=int(t.rst)
    print(c, k/n, (time.time()-t0)/n*1000,'ms')
