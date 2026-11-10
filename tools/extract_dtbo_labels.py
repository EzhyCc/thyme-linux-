#!/usr/bin/env python3
"""extract_dtbo_labels.py — 从原厂 dtbo.img 提取 29 个 overlay 的 __fixups__ label 引用。

用法：python tools/extract_dtbo_labels.py <dtbo.img> <out_labels.txt>
输出每行一个 label（去重排序），并打印统计。
"""
import struct
import sys
from pathlib import Path

FDT_MAGIC = 0xD00DFEED
FDT_BEGIN_NODE = 1
FDT_END_NODE = 2
FDT_PROP = 3
FDT_NOP = 4
FDT_END = 9


def be32(d, o):
    return struct.unpack_from(">I", d, o)[0]


def parse_fdt_labels(frag):
    """返回该 overlay 片段 __fixups__ 中引用的 label 集合。"""
    if len(frag) < 40 or be32(frag, 0) != FDT_MAGIC:
        return set()
    off_struct = be32(frag, 8)
    off_strings = be32(frag, 12)
    p = off_struct
    in_fixups = False
    labels = set()
    while True:
        tok = be32(frag, p)
        p += 4
        if tok == FDT_BEGIN_NODE:
            end = frag.index(b"\0", p)
            name = frag[p:end].decode("ascii", "replace")
            p = end + 1
            p = (p + 3) & ~3
            in_fixups = (name == "__fixups__")
        elif tok == FDT_END_NODE:
            in_fixups = False
        elif tok == FDT_PROP:
            ln = be32(frag, p); p += 4
            nameoff = be32(frag, p); p += 4
            p = (p + 3) & ~3
            if in_fixups:
                end = frag.index(b"\0", off_strings + nameoff)
                labels.add(frag[off_strings + nameoff:end].decode("ascii", "replace"))
            p = (p + ln + 3) & ~3
        elif tok == FDT_NOP:
            pass
        elif tok == FDT_END:
            break
        else:
            raise SystemExit("bad fdt token %d at %d" % (tok, p))
    return labels


def main(dtbo_path, out_path):
    d = Path(dtbo_path).read_bytes()
    magic = be32(d, 0)
    assert magic == 0x0D7B7AB1E or d[:4] == bytes.fromhex("d7b7ab1e"), "不是 dtbo 容器"
    total = be32(d, 4)
    hdr = be32(d, 8)
    esz = be32(d, 12)
    cnt = be32(d, 16)
    eoff = be32(d, 20)
    print("dtbo: total=%d hdr=%d entry_size=%d count=%d entries_off=%d" % (total, hdr, esz, cnt, eoff))
    all_labels = set()
    for i in range(cnt):
        o = eoff + i * esz
        sz = be32(d, o)
        off = be32(d, o + 4)
        frag = d[off:off + sz]
        labels = parse_fdt_labels(frag)
        all_labels |= labels
        print("  frag %2d: size=%6d labels=%d" % (i, sz, len(labels)))
    labels = sorted(all_labels)
    Path(out_path).write_text("\n".join(labels) + "\n")
    print("unique labels: %d -> %s" % (len(labels), out_path))
    # 简单合法性检查
    bad = [l for l in labels if not l.replace("_", "").replace("-", "").isalnum()]
    if bad:
        print("WARN invalid label chars:", bad[:10])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
