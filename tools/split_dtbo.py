#!/usr/bin/env python3
"""split_dtbo.py — 把 dtbo.img 拆成 29 个片段文件。"""
import struct
import sys
from pathlib import Path

d = Path(sys.argv[1]).read_bytes()
outdir = Path(sys.argv[2]); outdir.mkdir(parents=True, exist_ok=True)
assert d[:4] == bytes.fromhex("d7b7ab1e")
esz = struct.unpack_from(">I", d, 12)[0]
cnt = struct.unpack_from(">I", d, 16)[0]
eoff = struct.unpack_from(">I", d, 20)[0]
for i in range(cnt):
    o = eoff + i * esz
    sz, off = struct.unpack_from(">II", d, o)
    (outdir / ("frag-%02d.dtbo" % i)).write_bytes(d[off:off + sz])
print("wrote %d fragments to %s" % (cnt, outdir))
