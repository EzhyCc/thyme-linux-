#!/usr/bin/env python3
"""fdt_symbols.py — 打印 DTB 的 __symbols__ 标签名。"""
import struct
import sys
from pathlib import Path

MAGIC = 0xD00DFEED
BEGIN, ENDN, PROP, NOP, END = 1, 2, 3, 4, 9


def be32(d, o):
    return struct.unpack_from(">I", d, o)[0]


def main(path):
    d = Path(path).read_bytes()
    assert be32(d, 0) == MAGIC, "not fdt"
    os_ = be32(d, 8)
    ostr = be32(d, 12)
    p = os_
    in_sym = False
    names = []
    while True:
        tok = be32(d, p); p += 4
        if tok == BEGIN:
            e = d.index(b"\0", p)
            name = d[p:e].decode("ascii", "replace")
            p = (e + 1 + 3) & ~3
            in_sym = (name == "__symbols__")
        elif tok == ENDN:
            in_sym = False
        elif tok == PROP:
            ln = be32(d, p); p += 4
            noff = be32(d, p); p += 4
            p = (p + 3) & ~3
            if in_sym:
                e = d.index(b"\0", ostr + noff)
                names.append(d[ostr + noff:e].decode("ascii", "replace"))
            p = (p + ln + 3) & ~3
        elif tok == NOP:
            pass
        elif tok == END:
            break
        else:
            raise SystemExit("bad token")
    for n in sorted(names):
        print(n)


if __name__ == "__main__":
    main(sys.argv[1])
