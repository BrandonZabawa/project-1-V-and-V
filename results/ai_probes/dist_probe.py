import random, vsc
@vsc.randobj
class T:
    def __init__(self):
        self.wr_en = vsc.rand_bit_t(1); self.rd_en = vsc.rand_bit_t(1)
        self.count = vsc.uint32_t(0)
    @vsc.constraint
    def c(self):
        with vsc.if_then(self.count <= 1):
            vsc.dist(self.wr_en, [vsc.weight(1, 90), vsc.weight(0, 10)])
            vsc.dist(self.rd_en, [vsc.weight(0, 80), vsc.weight(1, 20)])
        with vsc.else_if(self.count >= 7):
            vsc.dist(self.wr_en, [vsc.weight(0, 80), vsc.weight(1, 20)])
            vsc.dist(self.rd_en, [vsc.weight(1, 90), vsc.weight(0, 10)])
        with vsc.else_then:
            vsc.dist(self.wr_en, [vsc.weight(1, 80), vsc.weight(0, 20)])
            vsc.dist(self.rd_en, [vsc.weight(1, 80), vsc.weight(0, 20)])
random.seed(1); t=T()
for c in (0,4,8):
    t.count=c; w=r=0
    for _ in range(600):
        t.randomize(); w+=int(t.wr_en); r+=int(t.rd_en)
    print(c, w/600, r/600)
