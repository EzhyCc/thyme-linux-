#!/usr/bin/env bash
# install-rootfs.sh —— 把 rootfs 镜像/压缩包写进 userdata 并扩容
#
# 用法（在手机的 initramfs 救援 shell 里执行）:
#   1) 电脑上起 HTTP 服务：  python -m http.server 8000
#   2) 手机侧：
#        bash install-rootfs.sh http://<PC-IP>:8000/rootfs.img     # raw 镜像，推荐
#        bash install-rootfs.sh http://<PC-IP>:8000/rootfs.tar.gz  # tar 包
#
# 破坏性：会覆盖 /dev/sda35（userdata）全部内容。
set -euo pipefail

URL="${1:?用法: install-rootfs.sh <url> [设备, 默认 /dev/sda35]}"
DEV="${2:-/dev/sda35}"

echo "[*] 目标设备: $DEV"
[ -b "$DEV" ] || { echo "错误: $DEV 不是块设备"; exit 1; }

case "$URL" in
	*.tar.gz|*.tgz)
		echo "[*] 模式: tar 解包（需要有已格式化的 ext4）"
		mkdir -p /mnt
		mount "$DEV" /mnt || { echo "错误: 无法挂载 $DEV，请先 mkfs.ext4"; exit 1; }
		rm -rf /mnt/* /mnt/.[!.]* 2>/dev/null || true
		echo "[*] 下载并解包（约 2GB，请耐心等待）..."
		wget -O - "$URL" | tar xz -C /mnt --numeric-owner -p
		sync
		umount /mnt
		;;
	*)
		echo "[*] 模式: raw 镜像直写（推荐）"
		echo "[*] 下载中（6.4GB 约 6 分钟，USB2 会更久）..."
		wget -O "$DEV" "$URL"
		sync
		;;
esac

echo "[*] 扩容文件系统到整块 UFS ..."
mount "$DEV" /mnt 2>/dev/null || { mkdir -p /mnt && mount "$DEV" /mnt; }
head -1 /mnt/etc/os-release || echo "警告: 未找到 os-release"
umount /mnt
resize2fs "$DEV" || echo "警告: resize2fs 失败，进入系统后可再执行"

echo "[*] 完成。检查 fstab / machine-id:"
mount "$DEV" /mnt
sed -n '1,5p' /mnt/etc/fstab || true
[ -s /mnt/etc/machine-id ] || echo "7fd098aafe8f445ea0a39ff6c3eb85f6" > /mnt/etc/machine-id
umount /mnt
echo "[*] 现在可以切根: mount --move /dev /mnt/dev ... && exec switch_root /mnt /sbin/init"
