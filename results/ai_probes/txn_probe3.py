import random, time, vsc
DEPTH=8; FILL, DRAIN = 0, 1
@vsc.randobj
class FifoTxn:
    def __init__(self, width=8, depth=DEPTH):
        self.depth = depth
        self.wr_en = vsc.rand_bit_t(1)
        self.rd_en = vsc.rand_bit_t(1)
        self.wr_data = vsc.rand_bit_t(width)
        self.roll = vsc.rand_uint8_t()
        self.count = vsc.uint32_t(0)
        self.phase = vsc.uint8_t(FILL)
    def _mix(self, w_only, both, r_only):
        a, b, c = w_only, w_only + both, w_only + both + r_only
        with vsc.if_then(self.roll < a):
            self.wr_en == 1; self.rd_en == 0
        with vsc.else_if(self.roll < b):
            self.wr_en == 1; self.rd_en == 1
        with vsc.else_if(self.roll < c):
            self.wr_en == 0; self.rd_en == 1
        with vsc.else_then:
            self.wr_en == 0; self.rd_en == 0
    @vsc.constraint
    def c_roll(self):
        vsc.dist(self.roll, [vsc.weight(i, 1) for i in range(20)])
    @vsc.constraint
    def c_data(self):
        vsc.dist(self.wr_data, [vsc.weight(0x00, 10), vsc.weight(0xFF, 10), vsc.weight(0x55, 10),
                                vsc.weight(0xAA, 10), vsc.weight(vsc.rng(0x01, 0xFE), 60)])
    @vsc.constraint
    def c_shape(self):
        with vsc.if_then(self.count <= 1):
            with vsc.if_then(self.phase == FILL):
                self._mix(12, 5, 2)
            with vsc.else_then:
                self._mix(2, 4, 11)
        with vsc.else_if(self.count >= self.depth - 1):
            with vsc.if_then(self.phase == DRAIN):
                self._mix(2, 5, 12)
            with vsc.else_then:
                self._mix(11, 4, 2)
        with vsc.else_then:
            with vsc.if_then(self.phase == FILL):
                self._mix(8, 9, 2)
            with vsc.else_then:
                self._mix(2, 9, 8)
random.seed(1); t=FifoTxn()
for c,p in ((0,0),(0,1),(4,0),(4,1),(8,0),(8,1)):
    t.count=c; t.phase=p; tally={}
    t0=time.time()
    for _ in range(1000):
        t.randomize(); k=(int(t.wr_en),int(t.rd_en)); tally[k]=tally.get(k,0)+1
    dt=time.time()-t0
    print(c,p,{f"{k}":v/1000 for k,v in sorted(tally.items())}, f"{dt*1000/1000:.2f} ms/draw")
from collections import Counter
d=Counter()
for _ in range(2000):
    t.randomize(); v=int(t.wr_data); d['00' if v==0 else 'FF' if v==255 else '55' if v==0x55 else 'AA' if v==0xAA else 'other']+=1
print(d)
r=Counter()
for _ in range(3000):
    t.randomize(); r[int(t.roll)]+=1
print(sorted(r.items()))
