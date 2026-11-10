#!/usr/bin/env python3
"""bootimg2.py — Android boot/vendor_boot/dtbo/vbmeta 解析与 v2 打包工具（thyme 取证用）。

用法：
  python tools/bootimg2.py info  <img> [<img> ...]         # 解析并打印完整头部/段信息
  python tools/bootimg2.py extract <img> <outdir>          # 拆分各段为文件
  python tools/bootimg2.py pack-v2 <template> <kernel.gz> <dtb> <out.img> [cmdline]
  python tools/bootimg2.py roundtrip <img> <outdir>        # 解包→按 v2 重包→逐段对比

支持：boot v0/v1/v2/v3/v4、vendor_boot v3/v4、dtbo 容器、AVB footer。
"""
import hashlib
import json
import struct
import sys
from pathlib import Path

BOOT_MAGIC = b"ANDROID!"
VENDOR_MAGIC = b"VNDRBOOT"
DTBO_MAGIC = 0xD7B7AB1E
AVB_MAGIC = b"AVBf"
PAGE = 4096


def sha(b):
    return hashlib.sha256(b).hexdigest()


def u32(d, o):
    return struct.unpack_from("<I", d, o)[0]


def u64(d, o):
    return struct.unpack_from("<Q", d, o)[0]


def parse_avb(d):
    """AVB footer 为大端；位于镜像末尾 64 字节。"""
    if len(d) < 64 or d[-64:-60] != AVB_MAGIC:
        return None
    return {
        "magic": "AVBf",
        "version": struct.unpack(">I", d[-60:-56])[0],
        "original_image_size": struct.unpack(">Q", d[-56:-48])[0],
        "vbmeta_offset": struct.unpack(">Q", d[-48:-40])[0],
        "vbmeta_size": struct.unpack(">Q", d[-40:-32])[0],
    }


def parse_boot(d):
    ver = u32(d, 40)
    info = {"type": "boot", "header_version": ver}
    page = None
    if ver >= 3:
        info.update({
            "header_size": u32(d, 20),
            "os_version": u32(d, 16),
            "kernel_size": u32(d, 8),
            "ramdisk_size": u32(d, 12),
            "cmdline": d[44:44 + 1536].split(b"\0", 1)[0].decode("utf-8", "replace"),
        })
        page = PAGE
        seg = [("kernel", info["kernel_size"]), ("ramdisk", info["ramdisk_size"])]
    else:
        kernel_size = u32(d, 8)
        kernel_addr = u32(d, 12)
        ramdisk_size = u32(d, 16)
        ramdisk_addr = u32(d, 20)
        second_size = u32(d, 24)
        second_addr = u32(d, 28)
        tags = u32(d, 32)
        page = u32(d, 36)
        osver = u32(d, 44)
        name = d[48:64].split(b"\0", 1)[0].decode("utf-8", "replace")
        cmdline = d[64:576].split(b"\0", 1)[0].decode("utf-8", "replace")
        extra = d[608:1632].split(b"\0", 1)[0].decode("utf-8", "replace")
        hdr_size = u32(d, 1644) if len(d) >= 1648 else None
        dtb_size = u32(d, 1648) if len(d) >= 1652 else 0
        dtb_addr = u64(d, 1652) if len(d) >= 1660 else 0
        rec_sz = u32(d, 1632) if len(d) >= 1636 else 0
        rec_off = u64(d, 1636) if len(d) >= 1644 else 0
        info.update({
            "header_size": hdr_size, "page_size": page,
            "kernel_size": kernel_size, "kernel_addr": kernel_addr,
            "ramdisk_size": ramdisk_size, "ramdisk_addr": ramdisk_addr,
            "second_size": second_size, "second_addr": second_addr,
            "tags_addr": tags, "os_version": osver, "name": name,
            "cmdline": cmdline, "extra_cmdline": extra,
            "recovery_dtbo_size": rec_sz, "recovery_dtbo_offset": rec_off,
            "dtb_size": dtb_size, "dtb_addr": dtb_addr,
        })
        seg = [("kernel", kernel_size), ("ramdisk", ramdisk_size),
               ("second", second_size), ("recovery_dtbo", rec_sz),
               ("dtb", dtb_size)]
    # 段布局：header 占一页，然后按 page 对齐排布
    off = page
    segs = []
    for name_, size in seg:
        if size == 0:
            continue
        segs.append({"name": name_, "offset": off, "size": size, "sha256": sha(d[off:off + size])})
        off = (off + size + page - 1) // page * page
    info["segments"] = segs
    info["avb"] = parse_avb(d)
    return info


def parse_vendor_boot(d):
    info = {
        "type": "vendor_boot",
        "header_version": u32(d, 8),
        "page_size": u32(d, 12),
        "kernel_addr": u32(d, 16),
        "ramdisk_addr": u32(d, 20),
        "vendor_ramdisk_size": u32(d, 24),
        "cmdline": d[28:2076].split(b"\0", 1)[0].decode("utf-8", "replace"),
        "tags_addr": u32(d, 2076),
        "name": d[2080:2096].split(b"\0", 1)[0].decode("utf-8", "replace"),
        "header_size": u32(d, 2096),
        "dtb_size": u32(d, 2100),
        "dtb_addr": u64(d, 2104),
        "vendor_ramdisk_table_size": u32(d, 2112),
        "vendor_ramdisk_table_entry_num": u32(d, 2116),
        "vendor_ramdisk_table_entry_size": u32(d, 2120),
        "bootconfig_size": u32(d, 2124),
    }
    page = info["page_size"]
    off = page
    segs = []
    for name_, size in [("vendor_ramdisk", info["vendor_ramdisk_size"]),
                        ("dtb", info["dtb_size"]),
                        ("vendor_ramdisk_table", info["vendor_ramdisk_table_size"]),
                        ("bootconfig", info["bootconfig_size"])]:
        if size == 0:
            continue
        segs.append({"name": name_, "offset": off, "size": size, "sha256": sha(d[off:off + size])})
        off = (off + size + page - 1) // page * page
    info["segments"] = segs
    info["avb"] = parse_avb(d)
    return info


def parse_dtbo(d):
    """DTBO 头为大端。"""
    def be32(o):
        return struct.unpack_from(">I", d, o)[0]
    info = {
        "type": "dtbo",
        "magic": hex(be32(0)),
        "total_size": be32(4),
        "header_size": be32(8),
        "dt_entry_size": be32(12),
        "dt_entry_count": be32(16),
        "dt_entries_offset": be32(20),
        "page_size": be32(24),
        "version": be32(28),
    }
    es = info["dt_entry_size"]
    ents = []
    for i in range(info["dt_entry_count"]):
        o = info["dt_entries_offset"] + i * es
        ents.append({"index": i, "dt_size": be32(o), "dt_offset": be32(o + 4),
                     "id": be32(o + 8), "rev": be32(o + 12)})
    info["entries"] = ents
    info["avb"] = parse_avb(d)
    return info


def analyze(path):
    d = Path(path).read_bytes()
    if d[:8] == BOOT_MAGIC:
        info = parse_boot(d)
    elif d[:8] == VENDOR_MAGIC:
        info = parse_vendor_boot(d)
    elif len(d) >= 4 and d[:4] == bytes.fromhex("d7b7ab1e"):
        info = parse_dtbo(d)
    else:
        return {"error": "unknown image magic", "magic": d[:8].hex(), "size": len(d)}
    info["file"] = str(path)
    info["file_size"] = len(d)
    info["file_sha256"] = sha(d)
    return info


def dump(info):
    print(json.dumps(info, indent=2, ensure_ascii=False))


def extract(path, outdir):
    info = analyze(path)
    if "error" in info:
        raise SystemExit(f"{path}: {info['error']}")
    d = Path(path).read_bytes()
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    for s in info.get("segments", []):
        p = out / f"{s['name']}.bin"
        p.write_bytes(d[s["offset"]:s["offset"] + s["size"]])
        print(f"  {p}  {s['size']}  {s['sha256']}")
    (out / "info.json").write_text(json.dumps(info, indent=2, ensure_ascii=False))


def pack_v2(template, kernel_gz, dtb, out_img, cmdline=None):
    """按 v2 头打包（umi 已验证的路径）：dtb 段独立、header_size=1660、os_version 继承模板。"""
    d = Path(template).read_bytes()
    t = parse_boot(d)
    page = t["page_size"]
    kaddr = t["kernel_addr"]
    raddr = t["ramdisk_addr"]
    tags = t["tags_addr"]
    osver = t["os_version"]
    dtb_addr = t["dtb_addr"] or 0x01F00000
    if cmdline is None:
        cmdline = t["cmdline"].encode()
    else:
        cmdline = cmdline.encode()
    if len(cmdline) > 512:
        raise SystemExit("cmdline > 512")

    kgz = Path(kernel_gz).read_bytes()
    dt = Path(dtb).read_bytes()
    if kgz[:2] != b"\x1f\x8b":
        raise SystemExit("kernel 段不是 gzip（ABL 会当 32 位内核）")
    import gzip
    img = gzip.decompress(kgz)
    if img[56:60] != b"ARM\x64":
        raise SystemExit("kernel 解压后 offset 56 不是 ARM\\x64")
    if dt[:4] != b"\xd0\x0d\xfe\xed":
        raise SystemExit("dtb 不是 FDT")
    if len(dt) >= 2 * 1024 * 1024:
        raise SystemExit("dtb >= 2MiB")

    hdr = struct.pack(
        "<8s10I16s512s32s1024sIQIIIQ",
        BOOT_MAGIC,
        len(kgz), kaddr,
        0, raddr,
        0, 0,
        tags, page,
        2, osver,
        b"",
        cmdline,
        b"\0" * 32,
        b"",
        0, 0,
        1660, len(dt), dtb_addr,
    )
    assert len(hdr) == 1660, len(hdr)
    def pad(f):
        o = f.tell() % page
        if o:
            f.write(b"\0" * (page - o))
    with open(out_img, "wb") as f:
        f.write(hdr)
        pad(f)
        f.write(kgz)
        pad(f)
        f.write(dt)
        pad(f)
    v = parse_boot(Path(out_img).read_bytes())
    print(f"packed {out_img}: page={page} kaddr=0x{kaddr:x} raddr=0x{raddr:x} "
          f"tags=0x{tags:x} osver={osver} dtb_size={len(dt)} kernel_size={len(kgz)}")
    assert v["kernel_size"] == len(kgz) and v["dtb_size"] == len(dt)
    assert v["header_size"] == 1660 and v["header_version"] == 2
    print("verify OK")


def pack_v3(template, kernel, ramdisk, out_img, cmdline=None):
    """按 boot v3 打包（原厂同款）：header 1580，kernel 段 + ramdisk 段，page 对齐。"""
    t = parse_boot(Path(template).read_bytes())
    if t["header_version"] < 3:
        raise SystemExit("模板不是 v3")
    page = PAGE
    k = Path(kernel).read_bytes()
    r = Path(ramdisk).read_bytes()
    osver = t["os_version"]
    cmd = t["cmdline"] if cmdline is None else cmdline
    cmd = cmd.encode() if isinstance(cmd, str) else cmd
    if len(cmd) > 1536:
        raise SystemExit("cmdline > 1536")
    hdr = struct.pack("<8sIIII16sI1536s",
                      BOOT_MAGIC, len(k), len(r), osver, 1580,
                      b"\0" * 16, 3, cmd)
    assert len(hdr) == 1580, len(hdr)

    def pad(f):
        o = f.tell() % page
        if o:
            f.write(b"\0" * (page - o))
    with open(out_img, "wb") as f:
        f.write(hdr)
        pad(f)
        f.write(k)
        pad(f)
        f.write(r)
        pad(f)
    v = parse_boot(Path(out_img).read_bytes())
    assert v["kernel_size"] == len(k) and v["ramdisk_size"] == len(r)
    print(f"packed v3 {out_img}: page={page} osver={osver} kernel={len(k)} ramdisk={len(r)}")


def pack_vendor(template, dtb, out_img, cmdline=None):
    """按 vendor_boot v3 打包（保留模板 vendor_ramdisk，替换 DTB；cmdline 可覆盖）。"""
    d = Path(template).read_bytes()
    t = parse_vendor_boot(d)
    page = t["page_size"]
    dt = Path(dtb).read_bytes()
    if dt[:4] != b"\xd0\x0d\xfe\xed":
        raise SystemExit("dtb 不是 FDT")
    if len(dt) >= 2 * 1024 * 1024:
        raise SystemExit("dtb >= 2MiB")
    vrd = d[t["segments"][0]["offset"]:t["segments"][0]["offset"] + t["vendor_ramdisk_size"]] \
        if t["vendor_ramdisk_size"] else b""
    cmd = t["cmdline"] if cmdline is None else cmdline
    cmd = cmd.encode() if isinstance(cmd, str) else cmd
    if len(cmd) > 2048:
        raise SystemExit("cmdline > 2048")
    name = t["name"].encode()
    hdr = struct.pack("<8sIIIII2048sI16sIIQ",
                      VENDOR_MAGIC, t["header_version"], page,
                      t["kernel_addr"], t["ramdisk_addr"],
                      len(vrd),
                      cmd,
                      t["tags_addr"], name, 2112,
                      len(dt), t["dtb_addr"])
    assert len(hdr) == 2112, len(hdr)

    def pad(f):
        o = f.tell() % page
        if o:
            f.write(b"\0" * (page - o))
    with open(out_img, "wb") as f:
        f.write(hdr)
        pad(f)
        f.write(vrd)
        pad(f)
        f.write(dt)
        pad(f)
    v = parse_vendor_boot(Path(out_img).read_bytes())
    assert v["vendor_ramdisk_size"] == len(vrd) and v["dtb_size"] == len(dt)
    print(f"packed vendor_boot {out_img}: page={page} dtb={len(dt)} vramdisk={len(vrd)}")


def roundtrip_v3(path, outdir):
    """原厂 boot v3 解包→重包→逐段对比。"""
    info = analyze(path)
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    d = Path(path).read_bytes()
    ks = info["segments"][0]
    rs = info["segments"][1]
    k = d[ks["offset"]:ks["offset"] + ks["size"]]
    r = d[rs["offset"]:rs["offset"] + rs["size"]]
    (out / "kernel.bin").write_bytes(k)
    (out / "ramdisk.bin").write_bytes(r)
    rep = out / "repacked.img"
    pack_v3(path, out / "kernel.bin", out / "ramdisk.bin", rep, cmdline=info["cmdline"])
    rd = rep.read_bytes()
    rv = parse_boot(rd)
    ok = True
    for name_, orig, got in (("kernel", k, rd[rv["segments"][0]["offset"]:rv["segments"][0]["offset"] + len(k)]),
                             ("ramdisk", r, rd[rv["segments"][1]["offset"]:rv["segments"][1]["offset"] + len(r)])):
        same = orig == got
        ok = ok and same
        print(f"  {name_}: {'IDENTICAL' if same else 'DIFF'}  sha256={sha(got)}")
    print(f"  cmdline: {rv['cmdline']!r}")
    print(f"  header: version={rv['header_version']} size={rv['header_size']} page={PAGE} osver={rv['os_version']}")
    print("roundtrip v3:", "PASS" if ok else "FAIL")





if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        raise SystemExit(__doc__)
    cmd = a[0]
    if cmd == "info":
        for p in a[1:]:
            dump(analyze(p))
    elif cmd == "extract":
        extract(a[1], a[2])
    elif cmd == "pack-v2":
        pack_v2(a[1], a[2], a[3], a[4], a[5] if len(a) > 5 else None)
    elif cmd == "roundtrip":
        roundtrip(a[1], a[2])
    elif cmd == "pack-v3":
        pack_v3(a[1], a[2], a[3], a[4], a[5] if len(a) > 5 else None)
    elif cmd == "pack-vendor":
        pack_vendor(a[1], a[2], a[3], a[4] if len(a) > 4 else None)
    elif cmd == "roundtrip-v3":
        roundtrip_v3(a[1], a[2])
    else:
        raise SystemExit(__doc__)
