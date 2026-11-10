#!/bin/bash
# usb-gadget.sh —— 在已启动的系统里重建 USB gadget（ACM 串口 + NCM 网卡）
# 注意：ACM 与 NCM 必须在同一个 config 里建好，最后一次性写 UDC。
set -e

G=/sys/kernel/config/usb_gadget/thyme
CONFIGFS=/sys/kernel/config

modprobe libcomposite 2>/dev/null || true
mountpoint -q "$CONFIGFS" || mount -t configfs none "$CONFIGFS"

# 清理旧实例（写空 UDC 再删目录）
if [ -d "$G" ]; then
	[ -d "$G/UDC" ] && echo "" > "$G/UDC" 2>/dev/null || true
	find "$G" -maxdepth 1 -mindepth 1 -type l -delete 2>/dev/null || true
	rm -rf "$G" 2>/dev/null || true
fi

mkdir -p "$G"
echo 0x18d1 > "$G/idVendor"
echo 0x4ee8 > "$G/idProduct"
mkdir -p "$G/strings/0x409" "$G/configs/c.1/strings/0x409"
echo "thyme"       > "$G/strings/0x409/manufacturer"
echo "thyme-linux" > "$G/strings/0x409/product"
echo "0001"        > "$G/strings/0x409/serialnumber"
echo "ACM+NCM"     > "$G/configs/c.1/strings/0x409/configuration"

mkdir -p "$G/functions/acm.gs0" "$G/functions/ncm.usb0"
echo 02:11:22:33:44:55 > "$G/functions/ncm.usb0/dev_addr"  || true
echo 66:55:44:33:22:11 > "$G/functions/ncm.usb0/host_addr" || true
ln -sf "$G/functions/acm.gs0" "$G/configs/c.1/"
ln -sf "$G/functions/ncm.usb0" "$G/configs/c.1/"

UDC=$(ls /sys/class/udc | head -1)
[ -n "$UDC" ] || { echo "没有可用 UDC（dwc3 没 probe？）"; exit 1; }
echo "$UDC" > "$G/UDC"

for i in $(seq 1 10); do [ -c /dev/ttyGS0 ] && break; sleep 1; done
[ -c /dev/ttyGS0 ] || { echo "ttyGS0 未出现"; exit 1; }

ip link set usb0 up 2>/dev/null || true
ip addr add 172.16.42.1/24 dev usb0 2>/dev/null || true
echo "OK: UDC=$UDC ttyGS0 就绪, usb0=172.16.42.1"
