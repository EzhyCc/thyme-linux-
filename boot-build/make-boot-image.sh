#!/usr/bin/env bash
# make-boot-image.sh —— 打包可被本机 ABL 接受的 v2 boot 镜像
#
# 用法:
#   bash boot-build/make-boot-image.sh \
#     --kernel    kernel/Image.gz \
#     --initramfs boot-build/initramfs.cpio.gz \
#     --dtb       dts/thyme-dtb-abl.dtb \
#     --cmdline   "console=ttyMSM0,115200n8 console=tty0 loglevel=7" \
#     --out       out/boot-thyme.img
#
# --initramfs 既可以给 cpio.gz 文件，也可以给目录（会自动打包）
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"

KERNEL=""
INITRAMFS=""
DTB=""
OUT="out/boot-thyme.img"
CMDLINE="console=ttyMSM0,115200n8 console=tty0 loglevel=7 ignore_loglevel clk_ignore_unused pd_ignore_unused regulator_ignore_unused"

while [ $# -gt 0 ]; do
	case "$1" in
		--kernel)    KERNEL="$2"; shift 2;;
		--initramfs) INITRAMFS="$2"; shift 2;;
		--dtb)       DTB="$2"; shift 2;;
		--out)       OUT="$2"; shift 2;;
		--cmdline)   CMDLINE="$2"; shift 2;;
		-h|--help)   sed -n '2,16p' "$0"; exit 0;;
		*) echo "unknown arg: $1" >&2; exit 1;;
	esac
done

[ -n "$KERNEL" ]    || { echo "--kernel 必填"; exit 1; }
[ -n "$INITRAMFS" ] || { echo "--initramfs 必填"; exit 1; }
[ -n "$DTB" ]       || { echo "--dtb 必填"; exit 1; }

# 目录 → cpio.gz
if [ -d "$INITRAMFS" ]; then
	echo "[*] 打包 initramfs 目录: $INITRAMFS"
	TMP="$(mktemp -d)"
	( cd "$INITRAMFS" && find . -print0 | cpio --null -o -H newc --owner=0:0 2>/dev/null | gzip -9 > "$TMP/initramfs.cpio.gz" )
	INITRAMFS="$TMP/initramfs.cpio.gz"
fi

mkdir -p "$(dirname "$OUT")"

echo "[*] kernel    = $KERNEL"
echo "[*] initramfs = $INITRAMFS"
echo "[*] dtb       = $DTB"
echo "[*] cmdline   = $CMDLINE"

python3 "$REPO/tools/pack_v2_dtb.py" "$KERNEL" "$INITRAMFS" "$DTB" "$OUT" $CMDLINE

echo "[*] 校验:"
python3 "$REPO/tools/bootimg2.py" info "$OUT" | grep -E 'header_version|page_size|kernel_size|ramdisk_size|dtb_size|cmdline'
echo "[*] 输出: $OUT"
echo "[*] 刷入: fastboot flash boot_a $OUT && fastboot --set-active=a && fastboot reboot"
