#!/usr/bin/env python3
"""gen_stubs.py — 为缺失的 label 生成 dtbo stub dtsi。

用法：python tools/gen_stubs.py <needed_labels.txt> <existing_symbols.txt> <out.dtsi>
"""
import sys
from pathlib import Path


def valid_label(name):
    return name and (name[0].isalpha() or name[0] == "_") and all(
        c.isalnum() or c == "_" for c in name)


def main(needed_path, existing_path, out_path):
    needed = [l.strip() for l in Path(needed_path).read_text().splitlines() if l.strip()]
    existing = set(l.strip() for l in Path(existing_path).read_text().splitlines() if l.strip())
    missing = [l for l in needed if l not in existing]
    bad = [l for l in missing if not valid_label(l)]
    missing = [l for l in missing if valid_label(l)]

    lines = [
        "// SPDX-License-Identifier: BSD-3-Clause",
        "/* 自动生成：ABL dtbo overlay 所需的占位 label（仅补 base DTB 缺失项）。 */",
        "/ {",
        "\tdtbo_stubs: dtbo-stubs {",
        "\t\t#address-cells = <1>;",
        "\t\t#size-cells = <0>;",
        "\t\t/* 无 compatible：避免 of_platform_populate 创建设备 */",
    ]
    for i, name in enumerate(missing):
        lines.append("\t\t%s: stub-%d { reg = <%d>; };" % (name, i, i))
    lines.append("\t};")
    lines.append("};")
    Path(out_path).write_text("\n".join(lines) + "\n")
    print("needed=%d existing=%d missing=%d generated=%d invalid_skipped=%d"
          % (len(needed), len(existing), len(missing), len(missing), len(bad)))
    if bad:
        print("skipped invalid:", bad[:10])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
