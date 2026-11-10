#!/usr/bin/env python3
"""dtbo_targets.py — 分析 dtbo.img 每个 overlay 片段的定位方式（target-phandle / target-path）。"""
import struct
import sys
from pathlib import Path

MAGIC = 0xD00DFEED
BEGIN, ENDN, PROP, NOP, END = 1, 2, 3, 4, 9


def be32(d, o):
    return struct.unpack_from(">I", d, o)[0]


def sname(d, off_strings, noff):
    e = d.index(b"\0", off_strings + noff)
    return d[off_strings + noff:e].decode("ascii", "replace")


def walk(d, off_struct, off_strings):
    """返回 {node_path: {prop: value}} 简化结构。"""
    p = off_struct
    stack = []
    out = {}
    node_props = {}
    while True:
        tok = be32(d, p); p += 4
        if tok == BEGIN:
            e = d.index(b"\0", p)
            name = d[p:e].decode("ascii", "replace")
            p = (e + 1 + 3) & ~3
            stack.append(name if name else "/")
            node_props["/".join(stack)] = {}
        elif tok == ENDN:
            stack.pop()
        elif tok == PROP:
            ln = be32(d, p); p += 4
            noff = be32(d, p); p += 4
            p = (p + 3) & ~3
            val = d[p:p + ln]
            path = "/".join(stack)
            node_props.setdefault(path, {})[sname(d, off_strings, noff)] = val
            p = (p + ln + 3) & ~3
        elif tok == NOP:
            pass
        elif tok == END:
            break
        else:
            raise SystemExit("bad token %d" % tok)
    return node_props


def main(dtbo_path):
    d = Path(dtbo_path).read_bytes()
    assert d[:4] == bytes.fromhex("d7b7ab1e"), "not dtbo"
    esz = be32(d, 12)
    cnt = be32(d, 16)
    eoff = be32(d, 20)
    tgt_label = tgt_path = 0
    paths = {}
    for i in range(cnt):
        o = eoff + i * esz
        sz = be32(d, o); off = be32(d, o + 4)
        frag = d[off:off + sz]
        if be32(frag, 0) != MAGIC:
            continue
        nodes = walk(frag, be32(frag, 8), be32(frag, 12))
        for path, props in nodes.items():
            if "target-path" in props:
                tgt_path += 1
                tp = props["target-path"].rstrip(b"\0").decode()
                paths.setdefault(tp, []).append(i)
            if "target" in props:
                tgt_label += 1
    print("fragments: %d  target(phandle): %d  target-path: %d" % (cnt, tgt_label, tgt_path))
    print("\n== target-path 使用列表 ==")
    for tp in sorted(paths):
        print("  %-50s frags=%s" % (tp, paths[tp][:6]))


if __name__ == "__main__":
    main(sys.argv[1])
