#!/usr/bin/env python3
"""pack_v2_dtb.py — 构造 Android boot v2 镜像（kernel+ramdisk+DTB 段，page 4096，qcom 地址）。

用法：python tools/pack_v2_dtb.py <Image.gz> <ramdisk> <dtb> <out.img> [cmdline]
布局（page 4096）：header(1660) | kernel | ramdisk | (second) | (recovery_dtbo) | dtb
地址按本机 vendor_boot 实测：kernel 0x8000, ramdisk 0x1000000, tags 0x100, dtb 0x1F00000
os_version 取原厂 436208004（Android 13.0, 2024-04）
"""
import struct
import sys
from pathlib import Path

PAGE = 4096
KADDR = 0x8000
RADDR = int(__import__("os").environ.get("RADDR", "0x10000000"), 16)
TAGS = 0x100
DTB_ADDR = 0x1F00000
OSVER = 436208004
HDR_SIZE = 1660
HDR = struct.Struct("<8s10I16s512s32s1024sIQIIQ")


def main(kernel_path, ramdisk_path, dtb_path, out_path, cmdline=None):
    k = Path(kernel_path).read_bytes()
    r = Path(ramdisk_path).read_bytes()
    d = Path(dtb_path).read_bytes()
    assert k[:2] == b"\x1f\x8b", "kernel 不是 gzip"
    import gzip
    img = gzip.decompress(k)
    assert img[56:60] == b"ARM\x64", "kernel 解压后无 ARM\\x64"
    assert d[:4] == b"\xd0\x0d\xfe\xed", "dtb 不是 FDT"
    assert len(d) < 2 * 1024 * 1024
    cmd = (cmdline or "").encode()
    assert len(cmd) <= 512

    hdr = HDR.pack(
        b"ANDROID!",
        len(k), KADDR,
        len(r), RADDR,
        0, 0,
        TAGS, PAGE,
        2, OSVER,
        b"",
        cmd,
        b"\0" * 32,
        b"",
        0, 0,
        HDR_SIZE, len(d), DTB_ADDR,
    )
    assert len(hdr) == HDR_SIZE, len(hdr)

    def pad(f):
        o = f.tell() % PAGE
        if o:
            f.write(b"\0" * (PAGE - o))

    with open(out_path, "wb") as f:
        f.write(hdr)
        pad(f)
        f.write(k)
        pad(f)
        f.write(r)
        pad(f)
        f.write(d)
        pad(f)
    print("packed v2 %s: page=%d kernel=%d ramdisk=%d dtb=%d osver=%d cmdline=%r"
          % (out_path, PAGE, len(k), len(r), len(d), OSVER, cmd))


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0], a[1], a[2], a[3], a[4] if len(a) > 4 else None)
